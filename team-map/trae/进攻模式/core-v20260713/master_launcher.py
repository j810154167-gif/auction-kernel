#!/usr/bin/env python3
"""
20260618 主控脚本 — 9:15 一键全流程
  Phase 1: 竞价监控 (WebSocket, 9:15-9:25)
  Phase 2: 决策引擎 (两次模拟开仓, 9:25-10:00)
  Phase 3: 终端报告 (10:00)
"""
import argparse
import json
import os
import subprocess, sys, time
from datetime import datetime, timezone, timedelta
from pathlib import Path

from runtime_loop import handle_trigger
from legacy_handoff_adapter import bridge_legacy_handoff

SCRIPT_DIR = Path(__file__).resolve().parent

def cst_now():
    return datetime.now(timezone(timedelta(hours=8)))

def ts():
    return cst_now().strftime("%H:%M:%S")

def _prepare_loop_env(mode="live", bridge_legacy_flag=False, legacy_dir=None, dry_run=False):
    trade_date = os.environ.get("HERMES_TRADE_DATE", cst_now().strftime("%Y-%m-%d"))
    run_id = os.environ.get("HERMES_RUN_ID", f"master-{cst_now().strftime('%H%M%S')}")
    current_time = os.environ.get("HERMES_CURRENT_TIME", cst_now().strftime("%H:%M"))
    result = handle_trigger(
        "每日启动",
        repo_root=SCRIPT_DIR,
        trade_date=trade_date,
        run_id=run_id,
        current_time=current_time,
        is_trading_day=os.environ.get("HERMES_IS_TRADING_DAY", "1") != "0",
        dry_run=dry_run,
        mode=mode,
        bridge_legacy=bridge_legacy_flag,
        legacy_dir=legacy_dir,
    )
    if result.get("status") == "blocked":
        raise RuntimeError(f"Runtime loop blocked: {result.get('reason')}")
    env = os.environ.copy()
    env["HERMES_TRADE_DATE"] = trade_date
    env["HERMES_RUN_ID"] = run_id
    env["HERMES_RUN_HANDOFF_DIR"] = result["handoff_dir"]
    env["HERMES_NODE_HANDOFF_DIR"] = str(Path(result["handoff_dir"]) / "nodes")
    env["HERMES_HISTORY_HANDOFF_ROOT"] = str(SCRIPT_DIR / "handoff")
    return result, env


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--replay-date")
    parser.add_argument("--run-id")
    parser.add_argument("--no-ws", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--bridge-legacy", action="store_true")
    parser.add_argument("--legacy-dir")
    args = parser.parse_args(argv)

    if args.replay_date:
        os.environ["HERMES_TRADE_DATE"] = args.replay_date
    if args.run_id:
        os.environ["HERMES_RUN_ID"] = args.run_id
    mode = "acceptance" if args.validate_only else ("replay" if args.replay_date or args.bridge_legacy else "live")
    if mode != "live" and "HERMES_CURRENT_TIME" not in os.environ:
        os.environ["HERMES_CURRENT_TIME"] = "09:30"

    loop_result, child_env = _prepare_loop_env(
        mode=mode,
        bridge_legacy_flag=args.bridge_legacy,
        legacy_dir=args.legacy_dir,
        dry_run=args.dry_run or args.validate_only,
    )
    if args.dry_run or args.validate_only:
        result = {
            "status": "ok",
            "mode": mode,
            "handoff_dir": loop_result.get("handoff_dir"),
            "loop_result": loop_result,
            "would_run": [] if args.validate_only else ["data_preloader.py", "auction_monitor.py", "d2_engine.py", "decision_engine.py"],
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    print("=" * 60)
    print(f"  20260618 早盘全流程主控")
    print(f"  启动: {ts()}")
    print("=" * 60)

    now = cst_now()

    # ── Wait for 9:15 if early ──
    target = now.replace(hour=9, minute=15, second=0, microsecond=0)
    if now < target:
        wait = (target - now).total_seconds()
        print(f"\n[{ts()}] ⏳ 等待 9:15 竞价开启 ... ({wait:.0f}s)")
        time.sleep(wait)

    print(f"\n{'='*60}")
    print(f"[{ts()}] 📥 Phase 0: 启动数据预加载")
    print(f"{'='*60}")
    result0 = subprocess.run(
        [sys.executable, str(SCRIPT_DIR / "data_preloader.py")],
        cwd=str(SCRIPT_DIR),
        capture_output=False,
        timeout=600,
        env=child_env,
    )
    if result0.returncode != 0:
        print(f"\n[{ts()}] ⚠ data_preloader.py 异常退出 (code={result0.returncode})")

    print(f"\n{'='*60}")
    print(f"[{ts()}] 🔌 Phase 1: 启动竞价 WebSocket 监控")
    print(f"{'='*60}")
    result1 = subprocess.run(
        [sys.executable, str(SCRIPT_DIR / "auction_monitor.py")],
        cwd=str(SCRIPT_DIR),
        capture_output=False,
        timeout=700,
        env=child_env,
    )
    if result1.returncode != 0:
        print(f"\n[{ts()}] ⚠ auction_monitor.py 异常退出 (code={result1.returncode})")

    print(f"\n{'='*60}")
    print(f"[{ts()}] 🧭 Phase 2: 启动 D2 独立引擎")
    print(f"{'='*60}")
    result_d2 = subprocess.run(
        [sys.executable, str(SCRIPT_DIR / "d2_engine.py")],
        cwd=str(SCRIPT_DIR),
        capture_output=False,
        timeout=900,
        env=child_env,
    )
    if result_d2.returncode != 0:
        print(f"\n[{ts()}] ⚠ d2_engine.py 异常退出 (code={result_d2.returncode})")

    print(f"\n{'='*60}")
    print(f"[{ts()}] 🎯 Phase 3: 启动决策/终端引擎")
    print(f"{'='*60}")
    result2 = subprocess.run(
        [sys.executable, str(SCRIPT_DIR / "decision_engine.py")],
        cwd=str(SCRIPT_DIR),
        capture_output=False,
        timeout=2400,
        env=child_env,
    )
    if result2.returncode != 0:
        print(f"\n[{ts()}] ⚠ decision_engine.py 异常退出 (code={result2.returncode})")


    print(f"\n{'='*60}")
    print(f"[{ts()}] 🏁 全流程结束")
    print(f"{'='*60}")

    if result2.returncode == 0:
        print(f"\n  📁 结果文件:")
        nodes_dir = Path(loop_result["handoff_dir"]) / "nodes"
        for f in sorted(nodes_dir.glob("*.json")):
            print(f"     {f.name}")


if __name__ == "__main__":
    raise SystemExit(main())
