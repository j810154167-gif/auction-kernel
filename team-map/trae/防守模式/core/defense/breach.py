"""
L2 破位检测 — 盘中监控
跳空低开(开盘<区间下沿): 15分钟阈值
盘中破位: 5分钟阈值
"""
import json, subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

CST = timezone(timedelta(hours=8))
from core.defense.auth import load_tickflow_api_key

API_KEY = load_tickflow_api_key()


def check_breach(sym: str, date_str: str, zone_low: float) -> dict:
    """
    检测指定交易日价格是否持续跌破防守区间下沿。
    
    Returns:
        {"triggered": bool, "windows": [...], "is_gap": bool, "current_avg": float}
    """
    d = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=CST)
    start = int(d.replace(hour=9, minute=0).timestamp() * 1000)
    end = int(d.replace(hour=15, minute=0).timestamp() * 1000)
    
    url = (f"https://api.tickflow.org/v1/klines"
           f"?symbol={sym}&period=1m&start_time={start}&end_time={end}&count=240")
    
    r = subprocess.run([
        'curl', '-sS', '--max-time', '15', '--noproxy', '*',
        '-H', f'x-api-key: {API_KEY}', url
    ], capture_output=True, text=True)
    
    try:
        bars = json.loads(r.stdout).get('data', {})
    except json.JSONDecodeError:
        return {"triggered": False, "error": "no data"}
    
    ts = bars.get('timestamp', [])
    hi = bars.get('high', [])
    lo = bars.get('low', [])
    
    if not ts:
        return {"triggered": False, "error": "no data"}
    
    rows = sorted(zip(ts, hi, lo), key=lambda x: x[0])
    
    # 判断是否跳空低开
    first_avg = round((rows[0][1] + rows[0][2]) / 2, 2)
    is_gap = first_avg < zone_low
    min_duration = 15 if is_gap else 5
    
    # 扫描所有跌破窗口
    windows = []
    in_breach = False
    breach_start = None
    
    for i, r in enumerate(rows):
        avg = round((r[1] + r[2]) / 2, 2)
        t = datetime.fromtimestamp(r[0] / 1000, tz=CST).strftime('%H:%M')
        
        if avg < zone_low:
            if not in_breach:
                in_breach = True
                breach_start = (i, t)
        else:
            if in_breach:
                duration = i - breach_start[0]
                windows.append({
                    "start": breach_start[1],
                    "duration": duration,
                    "sustained": duration >= min_duration,
                    "type": "gap_down" if is_gap else "mid_session",
                })
                in_breach = False
    
    # 尾盘仍在破位中
    if in_breach:
        duration = len(rows) - breach_start[0]
        windows.append({
            "start": breach_start[1],
            "duration": duration,
            "sustained": duration >= min_duration,
            "type": "gap_down" if is_gap else "mid_session",
        })
    
    triggered = any(w["sustained"] for w in windows)
    current_avg = round((rows[-1][1] + rows[-1][2]) / 2, 2)
    
    return {
        "triggered": triggered,
        "windows": windows,
        "is_gap": is_gap,
        "current_avg": current_avg,
        "current_time": datetime.fromtimestamp(rows[-1][0] / 1000, tz=CST).strftime('%H:%M'),
    }
