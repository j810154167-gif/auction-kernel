#!/usr/bin/env python3
"""
Decision Engine — D1 auction entry + Terminal report.
D2 is now handled by independent d2_engine.py.
"""
import json, ssl, sys, time
import urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
from paths import HANDOFF, load_api_key, today_str
from data_source_governance import load_acceptance_metadata

PRELOAD  = HANDOFF / "data_preload.json"
FILTERED = HANDOFF / "filtered_pool.json"


class DecisionState:
    def __init__(self):
        self.decision_1: dict | None = None
        self.d1_result: dict | None = None
        self.d2_result: dict | None = None
        self.log: list[str] = []

    def log_event(self, msg: str):
        entry = f"[{ts()}] {msg}"
        self.log.append(entry)
        print(entry)


def cst_now() -> datetime:
    return datetime.now(timezone(timedelta(hours=8)))

def ts() -> str:
    return cst_now().strftime("%H:%M:%S")

def iso() -> str:
    return cst_now().isoformat()

def load_json(p: Path) -> dict:
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def fetch_quotes(symbols: list[str]) -> dict[str, dict]:
    api_key = load_api_key()
    quotes: dict[str, dict] = {}
    for i in range(0, len(symbols), 50):
        batch = symbols[i:i+50]
        url = f"https://api.tickflow.org/v1/quotes?symbols={','.join(batch)}"
        req = urllib.request.Request(url, headers={
            "x-api-key": api_key, "accept": "application/json",
            "user-agent": "TickFlowExpertGovernance/1.0",
        })
        try:
            with urllib.request.urlopen(req, timeout=10, context=ssl.create_default_context()) as resp:
                data = json.loads(resp.read())
                for it in data.get("data", []):
                    quotes[it["symbol"]] = it
        except Exception:
            pass
        time.sleep(0.15)
    return quotes


# ── Decision #1: Auction-based entry ───────────────────────────
def decision_1(state: DecisionState) -> dict | None:
    state.log_event("🎯 Decision#1: 竞价开仓决策")

    data_source_meta = load_acceptance_metadata(HANDOFF)
    if data_source_meta.get("data_source_acceptance_status") == "blocked":
        state.log_event(f"  🚨 TickFlow事实层阻断: {data_source_meta.get('blocked_reason', 'data_source_acceptance_blocked')}")
        return None

    candidates = load_json(FILTERED).get("candidates", [])
    if not candidates:
        state.log_event("  ❌ 候选池为空，不上报开仓")
        return None

    # Use pre-computed scores from auction_monitor, or compute inline
    for c in candidates:
        if "score" not in c or c["score"] is None:
            chg = abs(c.get("change_pct", 0))
            vwap_dist = abs(c.get("vwap_distance_pct", 100))
            mom_slope = c.get("momentum_slope", 0.0) or 0.0
            penalty = c.get("gate_penalty", 0.0) or 0.0
            vol = c.get("auction_volume", 0)
            s_chg = min(chg / 10.0, 1.0) * 30
            s_vwap = max(0, (7 - vwap_dist) / 7) * 20
            s_mom = max(0, min(mom_slope / 2.0, 1.0)) * 25
            s_price = min(c.get("auction_price", 0) / 100, 1.0) * 10
            s_vol = min(vol / 500000, 1.0) * 15
            c["score"] = round(s_chg + s_vwap + s_mom + s_price + s_vol - penalty * 0.4, 2)

    candidates.sort(key=lambda x: x.get("score", 0), reverse=True)
    top = candidates[0]

    state.decision_1 = {
        **data_source_meta,
        "symbol": top["symbol"],
        "name": top.get("name", ""),
        "entry_price": top["auction_price"],
        "entry_time": iso(),
        "reasoning": (
            f"竞价{top['change_pct']:+.2f}%, VWAP偏差{top['vwap_distance_pct']:+.1f}%, "
            f"罚分{top.get('gate_penalty',0):.0f}, 综合评分{top['score']:.1f}"
        ),
        "score": top["score"],
        "candidates_considered": len(candidates),
    }

    state.log_event(f"  ✅ Decision#1: {top['symbol']} {top.get('name','')} "
                    f"竞价价{top['auction_price']:.2f} 评分{top['score']:.1f}")
    state.log_event(f"  理由: {state.decision_1['reasoning']}")

    state.log_event(f"  ── 候选前5 ──")
    for i, c in enumerate(candidates[:5], 1):
        marker = "★" if i == 1 else " "
        penalty = c.get("gate_penalty", 0) or 0
        state.log_event(f"  {marker} {c['symbol']:12s} {c.get('name',''):8s}  "
                        f"价:{c['auction_price']:7.2f}  涨:{c['change_pct']:+.2f}%  "
                        f"VWAP:{c['vwap_distance_pct']:+.1f}%  罚:{penalty:.0f}  评:{c['score']:.1f}")

    return state.decision_1


# ── Terminal Report ────────────────────────────────────────────
def terminal_report(state: DecisionState):
    state.log_event("📊 终端报告 D1+D2 (10:00)")

    preload = load_json(PRELOAD)
    all_symbols = [s["symbol"] for s in preload.get("limit_up_stocks", [])]
    quotes = fetch_quotes(all_symbols)

    results = {"decisions": [], "summary": {}}

    # D1
    d1 = state.decision_1
    if d1:
        q = quotes.get(d1["symbol"], {})
        final_price = q.get("last_price", 0) or q.get("open", 0) or d1["entry_price"]
        pnl_pct = (final_price - d1["entry_price"]) / d1["entry_price"] * 100
        is_win = final_price >= d1["entry_price"]
        state.d1_result = {
            "symbol": d1["symbol"], "entry": d1["entry_price"],
            "exit": final_price, "pnl_pct": round(pnl_pct, 2),
            "result": "WIN" if is_win else "LOSS",
        }
        results["decisions"].append({**state.d1_result, "id": "d1", "type": "auction_entry"})
        state.log_event(f"  D1: {d1['symbol']} {d1['entry_price']:.2f}→{final_price:.2f} "
                        f"({pnl_pct:+.2f}%) [{state.d1_result['result']}]")

    # D2 (from independent d2_engine)
    d2_path = HANDOFF / "d2_decision.json"
    d2 = None
    if d2_path.exists():
        d2_data = load_json(d2_path)
        d2 = d2_data.get("s2_decision")
        if d2:
            q = quotes.get(d2["symbol"], {})
            final_price = q.get("last_price", 0) or q.get("open", 0) or d2["entry_price"]
            pnl_pct = (final_price - d2["entry_price"]) / d2["entry_price"] * 100
            is_win = final_price >= d2["entry_price"]
            state.d2_result = {
                "symbol": d2["symbol"], "entry": d2["entry_price"],
                "exit": final_price, "pnl_pct": round(pnl_pct, 2),
                "result": "WIN" if is_win else "LOSS",
            }
            results["decisions"].append({**state.d2_result, "id": "d2", "type": "reversal_confirm",
                                         "confidence": d2.get("confidence", "unknown")})
            state.log_event(f"  D2: {d2['symbol']} {d2['entry_price']:.2f}→{final_price:.2f} "
                            f"({pnl_pct:+.2f}%) [{state.d2_result['result']}] ({d2.get('confidence','')})")
    if not d2:
        state.log_event(f"  D2: 空仓 (无反转信号)")

    # Summary
    decs = results["decisions"]
    wins = [d for d in decs if d["result"] == "WIN"]
    losses = [d for d in decs if d["result"] == "LOSS"]
    total_pnl = sum(d["pnl_pct"] for d in decs) if decs else 0
    avg_win = sum(d["pnl_pct"] for d in wins) / len(wins) if wins else 0
    avg_loss = sum(abs(d["pnl_pct"]) for d in losses) / len(losses) if losses else 0
    pl_ratio = round(avg_win / max(avg_loss, 0.01), 1) if wins and losses else 0

    results["summary"] = {
        "total_decisions": len(decs), "wins": len(wins), "losses": len(losses),
        "win_rate": f"{len(wins)}/{len(decs)} ({round(len(wins)/max(len(decs),1)*100,1)}%)",
        "total_pnl_pct": round(total_pnl, 2),
        "avg_win_pct": round(avg_win, 2), "avg_loss_pct": round(avg_loss, 2),
        "profit_loss_ratio": pl_ratio,
    }

    report = {
        "meta": {
            "date": today_str(),
            "generated_at": iso(),
            "session": "morning_auction",
            **load_acceptance_metadata(HANDOFF),
        },
        **results,
        "log": state.log[-20:],
    }

    out_path = HANDOFF / "terminal_packet.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)

    s = results["summary"]
    state.log_event(f"")
    state.log_event(f"{'='*60}")
    state.log_event(f"  🏁 终端报告")
    state.log_event(f"{'='*60}")
    state.log_event(f"  交易次数: {s['total_decisions']}")
    state.log_event(f"  胜率:     {s['win_rate']}")
    state.log_event(f"  总盈亏:   {s['total_pnl_pct']:+.2f}%")
    state.log_event(f"  平均盈:   {s['avg_win_pct']:+.2f}%")
    state.log_event(f"  平均亏:   {s['avg_loss_pct']:+.2f}%")
    state.log_event(f"  盈亏比:   {s['profit_loss_ratio']}")
    state.log_event(f"  📁 {out_path}")
    state.log_event(f"{'='*60}")

    return report


# ── Main orchestrator ──────────────────────────────────────────
def run_decision_engine():
    state = DecisionState()
    state.log_event("═" * 60)
    state.log_event("  Decision Engine — D1 + Terminal")
    state.log_event("═" * 60)

    # Phase 1: Wait for 09:25, Decision#1
    now = cst_now()
    target_d1 = now.replace(hour=9, minute=25, second=10, microsecond=0)
    if now < target_d1:
        wait = (target_d1 - now).total_seconds()
        state.log_event(f"  ⏳ 等待 Decision#1 窗口 (09:25) ... ({wait:.0f}s)")
        time.sleep(min(wait, 900))

    decision_1(state)

    # Phase 2: D2 is handled by independent d2_engine (09:30-09:40)
    state.log_event(f"\n  D2: delegated to d2_engine (independent)")

    # Phase 3: Wait for 10:00, terminal report
    now = cst_now()
    target_term = now.replace(hour=10, minute=1, second=0, microsecond=0)
    if now < target_term:
        wait = (target_term - now).total_seconds()
        state.log_event(f"\n  ⏳ 等待终端报告窗口 (10:00) ... ({wait:.0f}s)")
        time.sleep(min(wait, 900))

    terminal_report(state)
    return state


if __name__ == "__main__":
    run_decision_engine()
