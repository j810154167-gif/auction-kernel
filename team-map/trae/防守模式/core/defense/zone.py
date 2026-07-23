"""
L0 防守区间 — 每日盘后从分钟K线提取
两点定区间: [当日最低价, 量能峰值分钟均价]
零参数，逐日重建。不滚动、不累积。
"""
import json, subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

CST = timezone(timedelta(hours=8))
from core.defense.auth import load_tickflow_api_key

API_KEY = load_tickflow_api_key()


def get_zone(sym: str, date_str: str) -> dict | None:
    """
    取指定交易日数据，返回防守区间。
    
    区间计算:
    - low: 日K最低价（含竞价，分钟K从09:31开始会漏09:25竞价）
    - peak_avg: 量能Top5分钟K的加权VWAP（防单分钟坍缩）
    
    Returns:
        {"low": float, "peak_avg": float, "peak_time": str, "peak_vol": int}
        或 None（数据缺失）
    """
    d = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=CST)
    start = int(d.replace(hour=9, minute=0).timestamp() * 1000)
    end = int(d.replace(hour=15, minute=0).timestamp() * 1000)
    
    # 1. 拉分钟K
    url_k = (f"https://api.tickflow.org/v1/klines"
             f"?symbol={sym}&period=1m&start_time={start}&end_time={end}&count=240")
    
    r = subprocess.run([
        'curl', '-sS', '--max-time', '15', '--noproxy', '*',
        '-H', f'x-api-key: {API_KEY}', url_k
    ], capture_output=True, text=True)
    
    try:
        bars = json.loads(r.stdout).get('data', {})
    except json.JSONDecodeError:
        return None
    
    ts = bars.get('timestamp', [])
    hi = bars.get('high', [])
    lo = bars.get('low', [])
    vo = bars.get('volume', [])
    
    if not ts:
        return None
    
    rows = sorted(zip(ts, hi, lo, vo), key=lambda x: x[0])
    
    # 密集成交均价：取量能Top5，排除开盘前3根（恐慌/跳空竞价不反映真实共识）
    # 为什么要排除前3根：09:31是竞价消化、09:32是跟风、09:33是余波
    top5_all = sorted(rows, key=lambda r: r[3], reverse=True)
    top5_filtered = [r for r in top5_all if rows.index(r) >= 3][:5]
    
    # 如果过滤后不足5根，回退到全量Top5
    if len(top5_filtered) < 3:
        top5_filtered = top5_all[:5]
    
    total_vol = sum(r[3] for r in top5_filtered)
    if total_vol > 0:
        consensus = round(sum((r[1]+r[2])/2 * r[3] for r in top5_filtered) / total_vol, 2)
    else:
        # 极端情况：全日VWAP
        all_vol = sum(r[3] for r in rows)
        consensus = round(sum((r[1]+r[2])/2 * r[3] for r in rows) / all_vol, 2) if all_vol > 0 else 0
    
    # 防守区间：密集均价 ±2%
    zone_low = round(consensus * 0.98, 2)
    zone_peak = round(consensus * 1.02, 2)
    
    peak_time = datetime.fromtimestamp(top5_filtered[0][0] / 1000, tz=CST).strftime('%H:%M')
    
    return {
        "symbol": sym,
        "date": date_str,
        "low": zone_low,
        "peak_avg": zone_peak,
        "peak_time": peak_time,
        "peak_vol": top5_filtered[0][3],
        "consensus": consensus,
    }


def opponent_analysis(sym: str, date_str: str, cost: float) -> dict:
    """
    入场时刻对手盘分析：成本在昨日区间的什么位置，脚底下有多少获利盘。
    只在入场时做一次，不滚动。
    """
    zone = get_zone(sym, date_str)
    if not zone:
        return {"error": "no data"}
    
    # 需要分钟K来算量能分布
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
        return {"error": "parse error"}
    
    ts = bars.get('timestamp', [])
    hi = bars.get('high', [])
    lo = bars.get('low', [])
    vol = bars.get('volume', [])
    
    rows = sorted(zip(ts, hi, lo, vol), key=lambda x: x[0])
    total_vol = sum(r[3] for r in rows)
    
    below_cost = sum(r[3] for r in rows if (r[1] + r[2]) / 2 < cost)
    above_cost = total_vol - below_cost
    
    position = ("below_zone" if cost < zone["low"] 
                else "above_peak" if cost > zone["peak_avg"] 
                else "in_zone")
    
    return {
        "zone": zone,
        "cost": cost,
        "position": position,
        "position_label": {
            "below_zone": "🔽 区下·接恐慌盘",
            "in_zone": "■ 区内·与主力同价",
            "above_peak": "🔼 区上·对手在下方"
        }.get(position, position),
        "volume_below_cost_pct": round(below_cost / total_vol * 100, 1) if total_vol > 0 else 0,
        "volume_above_cost_pct": round(above_cost / total_vol * 100, 1) if total_vol > 0 else 0,
    }
