"""
L1 题材方向 — 人工标注输入，机器只做方向计算。
不自动推断、不编码、不固化题材叙事。
"""
import json, subprocess
from pathlib import Path

from core.defense.auth import load_tickflow_api_key

API_KEY = load_tickflow_api_key()


def load_l1_map(config_path: str = None) -> dict:
    """加载L1标注配置。格式: {"symbol": {"theme": "...", "peers": [...]}}"""
    if config_path is None:
        config_path = Path(__file__).parent.parent.parent / "config" / "l1_map.json"
    else:
        config_path = Path(config_path)
    
    if config_path.exists():
        return json.loads(config_path.read_text())
    return {}


def sector_signal(sym: str, l1_map: dict = None) -> dict:
    """
    基于人工标注的题材对标池，计算板块方向。
    
    Returns:
        {"signal": "bullish"|"bearish"|"mixed"|"unknown", 
         "detail": str, "theme": str}
    """
    if l1_map is None:
        l1_map = load_l1_map()
    
    info = l1_map.get(sym)
    if not info:
        return {"signal": "unknown", "detail": "未标注", "theme": "?"}
    
    peers = info.get("peers", [])
    if not peers:
        return {"signal": "unknown", "detail": "无对标", "theme": info.get("theme", "?")}
    
    ups = 0
    downs = 0
    details = []
    
    for p in peers:
        r = subprocess.run([
            'curl', '-sS', '--max-time', '8', '--noproxy', '*',
            '-H', f'x-api-key: {API_KEY}',
            f"https://api.tickflow.org/v1/klines?symbol={p}&period=1d&count=2"
        ], capture_output=True, text=True)
        
        try:
            bars = json.loads(r.stdout).get('data', {})
            cl = bars.get('close', [])
            if len(cl) < 2:
                continue
            chg = (cl[-1] - cl[-2]) / cl[-2] * 100
            if chg > 0.3:
                ups += 1
            elif chg < -0.3:
                downs += 1
            details.append(f"{p[-3:]}{chg:+.1f}%")
        except Exception:
            pass
    
    total = ups + downs
    if total == 0:
        return {"signal": "unknown", "detail": "对标无数据", "theme": info["theme"]}
    
    if ups >= total * 0.75:
        return {"signal": "bullish", "detail": f"{ups}/{total}↑ {' '.join(details)}", "theme": info["theme"]}
    if downs >= total * 0.75:
        return {"signal": "bearish", "detail": f"{downs}/{total}↓ {' '.join(details)}", "theme": info["theme"]}
    
    return {"signal": "mixed", "detail": f"{ups}↑{downs}↓ {' '.join(details)}", "theme": info["theme"]}
