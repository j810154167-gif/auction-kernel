"""
版本链式管理 — 防守体系
读取 core/VERSION → 校验日期对齐 → 检查模块完整性 → 产出 run_status
"""
import os, json, hashlib
from pathlib import Path
from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))
ROOT = Path(__file__).resolve().parent.parent.parent
from core.defense.auth import load_tickflow_api_key


def read_version() -> dict:
    """解析 core/VERSION"""
    vf = ROOT / "core" / "VERSION"
    if not vf.exists():
        return {"error": "VERSION file missing"}
    
    lines = vf.read_text().strip().split("\n")
    ver = {}
    for line in lines:
        line = line.strip()
        if ":" in line:
            k, v = line.split(":", 1)
            ver[k.strip()] = v.strip()
    return ver


def compute_module_sigs() -> dict:
    """计算核心模块 md5 签名"""
    sigs = {}
    modules_dir = ROOT / "core" / "defense"
    for f in sorted(modules_dir.glob("*.py")):
        if f.name == "__init__.py":
            continue
        sigs[f.name] = hashlib.md5(f.read_bytes()).hexdigest()[:8]
    return sigs


def date_align_check() -> dict:
    """日期校验: 今天 vs VERSION.date"""
    today = datetime.now(CST).strftime("%Y-%m-%d")
    ver = read_version()
    ver_date = ver.get("date", "")
    
    return {
        "today_cst": today,
        "version_date": ver_date,
        "aligned": today == ver_date,
        "drift_days": (datetime.strptime(today, "%Y-%m-%d") - 
                       datetime.strptime(ver_date, "%Y-%m-%d")).days if ver_date else None,
    }


def data_sources_check() -> dict:
    """数据源三路连通性检查"""
    import subprocess
    
    api_key = load_tickflow_api_key()
    results = {}
    
    # TickFlow REST
    try:
        r = subprocess.run([
            'curl', '-sS', '--max-time', '10', '--noproxy', '*',
            '-H', f'x-api-key: {api_key}',
            'https://api.tickflow.org/v1/quotes?symbols=600000.SH'
        ], capture_output=True, text=True)
        data = json.loads(r.stdout)
        results["tickflow_rest"] = "ok" if data.get("data") else "empty"
    except Exception as e:
        results["tickflow_rest"] = f"fail: {e}"
    
    # TickFlow WS (快速握手测试)
    # 跳过——WS 测试需要 async，preflight 不做深度测试
    results["tickflow_ws"] = "skipped (preflight)"
    
    # Config files
    for cfg in ["l1_map.json", "update_list.json"]:
        cfp = ROOT / "config" / cfg
        results[f"config_{cfg}"] = "ok" if cfp.exists() else "missing"
    
    return results


def module_integrity_check() -> dict:
    """模块完整性: 必需的 .py 文件是否存在"""
    required = ["zone.py", "breach.py", "sector.py"]
    modules_dir = ROOT / "core" / "defense"
    status = {}
    for mod in required:
        fp = modules_dir / mod
        status[mod] = "ok" if fp.exists() else "missing"
    return status


def preflight() -> dict:
    """
    startup_preflight — 防守引擎启动前执行。
    返回: {status: "PROCEED"|"BLOCKED", ...}
    """
    ver = read_version()
    sigs = compute_module_sigs()
    date = date_align_check()
    data = data_sources_check()
    modules = module_integrity_check()
    
    blockers = []
    
    if "error" in ver:
        blockers.append("VERSION file missing")
    
    if not date["aligned"]:
        blockers.append(f"date drift: version={date['version_date']} today={date['today_cst']}")
    
    missing_modules = [m for m, s in modules.items() if s != "ok"]
    if missing_modules:
        blockers.append(f"missing modules: {missing_modules}")
    
    config_issues = [k for k, v in data.items() if k.startswith("config_") and v != "ok"]
    if config_issues:
        blockers.append(f"config issues: {config_issues}")
    
    report = {
        "node": "startup_preflight",
        "cst_time": datetime.now(CST).isoformat(),
        "engine_version": ver.get("version", "unknown"),
        "parent_version": ver.get("parent", "unknown"),
        "module_signatures": sigs,
        "date_check": date,
        "data_sources": data,
        "module_integrity": modules,
        "blockers": blockers,
        "status": "PROCEED" if not blockers else "BLOCKED",
        "block_reason": "; ".join(blockers) if blockers else None,
    }
    
    # 写入 run_status
    out_dir = ROOT / "handoff" / datetime.now(CST).strftime("%Y-%m-%d")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "run_status.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    
    return report


if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "preflight"
    
    if cmd == "preflight":
        report = preflight()
        print(f"[{datetime.now(CST).strftime('%H:%M:%S')}] ⓪ preflight")
        print(f"  版本: {report['engine_version']} (parent: {report['parent_version']})")
        for k, v in report["data_sources"].items():
            print(f"  {k}: {v}")
        for k, v in report["module_integrity"].items():
            print(f"  {k}: {v}")
        print(f"  日期对齐: {'✅' if report['date_check']['aligned'] else '❌ ' + report['date_check']['version_date'] + ' vs ' + report['date_check']['today_cst']}")
        
        if report["status"] == "BLOCKED":
            print(f"  🚨 BLOCKED: {report['block_reason']}")
        else:
            print(f"  ✅ PROCEED")
    
    elif cmd == "version":
        ver = read_version()
        print(f"engine: {ver.get('version', '?')}")
        print(f"parent: {ver.get('parent', '?')}")
        print(f"mode: {ver.get('mode', '?')}")
    
    elif cmd == "sigs":
        sigs = compute_module_sigs()
        for mod, sig in sigs.items():
            print(f"  {mod}: {sig}")
