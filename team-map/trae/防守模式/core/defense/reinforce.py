"""
强化防守模块 — 悬置状态深度分析
按需调用，分析多日量能结构、机构行为痕迹、外部催化剂依赖。
不连续监控，跑一次出一份报告。挂载方式: defense_engine.py reinforce SYM
"""
import json, subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

CST = timezone(timedelta(hours=8))
ROOT = Path(__file__).resolve().parent.parent.parent
from core.defense.auth import load_tickflow_api_key

API_KEY = load_tickflow_api_key()


def pull_day(sym: str, date_str: str) -> list | None:
    """拉指定交易日分钟K，返回 sorted(timestamp, open, high, low, close, volume, amount)"""
    d = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=CST)
    s = int(d.replace(hour=9, minute=0).timestamp() * 1000)
    e = int(d.replace(hour=15, minute=0).timestamp() * 1000)
    url = (f"https://api.tickflow.org/v1/klines"
           f"?symbol={sym}&period=1m&start_time={s}&end_time={e}&count=240")
    r = subprocess.run([
        'curl', '-sS', '--max-time', '15', '--noproxy', '*',
        '-H', f'x-api-key: {API_KEY}', url
    ], capture_output=True, text=True)
    try:
        bars = json.loads(r.stdout).get('data', {})
    except json.JSONDecodeError:
        return None
    ts = bars.get('timestamp', [])
    hi = bars.get('high', [])
    lo = bars.get('low', [])
    op = bars.get('open', [])
    cl = bars.get('close', [])
    vo = bars.get('volume', [])
    am = bars.get('amount', [])
    if not ts:
        return None
    return sorted(zip(ts, op, hi, lo, cl, vo, am), key=lambda x: x[0])


def pull_daily(sym: str, count: int = 40) -> list:
    """拉日K"""
    url = f"https://api.tickflow.org/v1/klines?symbol={sym}&period=1d&count={count}"
    r = subprocess.run([
        'curl', '-sS', '--max-time', '10', '--noproxy', '*',
        '-H', f'x-api-key: {API_KEY}', url
    ], capture_output=True, text=True)
    try:
        bars = json.loads(r.stdout).get('data', {})
    except json.JSONDecodeError:
        return []
    ts = bars.get('timestamp', [])
    cl = bars.get('close', [])
    vo = bars.get('volume', [])
    return list(zip(ts, cl, vo))


def analyze_big_blocks(rows: list) -> dict:
    """分析当日大单成交"""
    bigs = []
    for i, r in enumerate(rows):
        _, o, h, l, c, v, a = r
        trail = sum(r2[5] for r2 in rows[max(0, i - 20):i]) / max(1, min(20, i))
        if v > 3000 or (trail > 0 and v > trail * 3):
            price = round((h + l) / 2, 2)
            direction = "buy" if c >= o else "sell"
            bigs.append({
                "time": datetime.fromtimestamp(r[0] / 1000, tz=CST).strftime('%H:%M'),
                "price": price,
                "volume": v,
                "amount": round(a / 10000, 0),
                "direction": direction,
            })
    
    buys = [b for b in bigs if b["direction"] == "buy"]
    sells = [b for b in bigs if b["direction"] == "sell"]
    
    return {
        "count": len(bigs),
        "buy_count": len(buys),
        "buy_vol": sum(b["volume"] for b in buys),
        "sell_count": len(sells),
        "sell_vol": sum(b["volume"] for b in sells),
        "net_vol": sum(b["volume"] for b in buys) - sum(b["volume"] for b in sells),
        "afternoon_sells": [b for b in sells if b["time"] >= "13:00"],
        "blocks": bigs,
    }


def price_band_analysis(rows: list, bands: list) -> list:
    """按价格带统计买卖方向"""
    results = []
    for lo_p, hi_p, label in bands:
        br = [r for r in rows if lo_p <= (r[2] + r[3]) / 2 < hi_p]
        if not br:
            results.append({"band": label, "range": [lo_p, hi_p], "total_vol": 0, "buy_pct": 0, "note": "无成交"})
            continue
        bv = sum(r[5] for r in br)
        bu = sum(r[5] for r in br if r[4] >= r[1])
        bp = round(bu / bv * 100, 1) if bv > 0 else 0
        
        judge = "买盘主导" if bp > 55 else ("卖盘主导" if bp < 45 else "均衡")
        results.append({
            "band": label, "range": [lo_p, hi_p], "total_vol": bv,
            "buy_pct": bp, "buy_vol": bu, "sell_vol": bv - bu,
            "judge": judge,
        })
    return results


def find_launch_point(sym: str) -> dict:
    """寻找起涨点 — 日K持续放量上涨的起点"""
    daily = pull_daily(sym, 40)
    if len(daily) < 20:
        return {"found": False, "reason": "数据不足"}
    
    # 找最低收盘
    lowest_idx = min(range(len(daily)), key=lambda i: daily[i][1])
    lowest_date = datetime.fromtimestamp(daily[lowest_idx][0] / 1000, tz=CST).strftime('%Y-%m-%d')
    lowest_price = daily[lowest_idx][1]
    
    # 从最低点向后找第一个放量(3x前期)上涨日
    launch_idx = None
    for i in range(lowest_idx + 1, len(daily)):
        if i >= 10:
            trail_vol = sum(daily[j][2] for j in range(i - 10, i)) / 10
            if daily[i][2] > trail_vol * 2.5 and daily[i][1] > daily[i - 1][1] * 1.05:
                launch_idx = i
                break
    
    if launch_idx:
        launch_date = datetime.fromtimestamp(daily[launch_idx][0] / 1000, tz=CST).strftime('%Y-%m-%d')
        return {
            "found": True,
            "lowest_date": lowest_date,
            "lowest_price": lowest_price,
            "launch_date": launch_date,
            "launch_price": daily[launch_idx][1],
            "rally_pct": round((daily[-1][1] - lowest_price) / lowest_price * 100, 1),
        }
    
    return {"found": False, "lowest_date": lowest_date, "lowest_price": lowest_price}


def reinforce(sym: str, cost: float = None, days: list = None) -> dict:
    """
    强化防守分析入口。
    
    Args:
        sym: 标的代码
        cost: 入场成本（可选）
        days: 要分析的关键日期列表（默认取最近5个交易日）
    
    Returns:
        结构化分析报告
    """
    if days is None:
        # 默认取最近5个交易日
        today = datetime.now(CST)
        days = []
        d = today
        while len(days) < 5:
            ds = d.strftime('%Y-%m-%d')
            test = pull_day(sym, ds)
            if test:
                days.insert(0, ds)
            d = d - timedelta(days=1)
    
    report = {
        "symbol": sym,
        "analyzed_at": datetime.now(CST).isoformat(),
        "cost": cost,
        "days_analyzed": days,
        "daily_breakdown": [],
        "trend": {},
        "structure": {},
        "advice": [],
    }
    
    # 逐日分析
    for ds in days:
        rows = pull_day(sym, ds)
        if not rows:
            continue
        
        close_p = rows[-1][4]
        total_v = sum(r[5] for r in rows)
        vwap = round(sum((r[2] + r[3]) / 2 * r[5] for r in rows) / total_v, 2) if total_v > 0 else 0
        
        bigs = analyze_big_blocks(rows)
        bands = price_band_analysis(rows, [
            (40, 42, "深水区"),
            (42, 44, "积累区"),
            (44, 45, "成本带"),
            (45, 47, "博弈下"),
            (47, 50, "博弈上"),
        ])
        
        day_report = {
            "date": ds,
            "open": rows[0][1],
            "high": max(r[2] for r in rows),
            "low": min(r[3] for r in rows),
            "close": close_p,
            "vwap": vwap,
            "total_vol": total_v,
            "close_vs_vwap": "above" if close_p > vwap else "below",
            "big_blocks": bigs,
            "price_bands": bands,
        }
        report["daily_breakdown"].append(day_report)
    
    # 趋势计算
    if len(report["daily_breakdown"]) >= 2:
        d0 = report["daily_breakdown"][-1]  # latest
        d1 = report["daily_breakdown"][-2]  # previous
        
        net_trend = [d["big_blocks"]["net_vol"] for d in report["daily_breakdown"]]
        vwap_trend = [d["close_vs_vwap"] for d in report["daily_breakdown"]]
        
        # 博弈带买盘趋势
        game_buy = []
        for d in report["daily_breakdown"]:
            for b in d["price_bands"]:
                if b["band"] == "博弈下":
                    game_buy.append(b["buy_pct"])
        
        report["trend"] = {
            "net_flows": net_trend,
            "net_trend": "declining" if len(net_trend) >= 2 and net_trend[-1] < net_trend[-2] else "stable",
            "game_zone_buy_pct": game_buy,
            "game_buy_trend": "weakening" if len(game_buy) >= 2 and game_buy[-1] < game_buy[-2] else "stable",
            "close_vs_vwap_trend": vwap_trend,
        }
    
    # 结构分析
    launch = find_launch_point(sym)
    report["structure"]["launch_point"] = launch
    
    # 真空区检测
    if cost:
        # 检查成本下方的价格带成交情况
        has_vacuum = False
        for d in report["daily_breakdown"]:
            for b in d["price_bands"]:
                if b["range"][1] <= cost and b["total_vol"] == 0:
                    has_vacuum = True
        
        report["structure"]["cost_anchor"] = cost
        report["structure"]["vacuum_below_cost"] = has_vacuum
    
    # 悬挂状态检测
    latest = report["daily_breakdown"][-1] if report["daily_breakdown"] else None
    if latest:
        is_suspended = False
        reasons = []
        
        # 条件1: 收在VWAP之下
        if latest["close_vs_vwap"] == "below":
            is_suspended = True
            reasons.append("收盘 < VWAP (高位量>低位量)")
        
        # 条件2: 博弈带买盘<55%
        for b in latest["price_bands"]:
            if b["band"] == "博弈下" and b["buy_pct"] < 55:
                is_suspended = True
                reasons.append(f"博弈带买盘{b['buy_pct']}% (弱)")
        
        # 条件3: 净买流量减速
        if report["trend"].get("net_trend") == "declining":
            reasons.append("机构买盘衰减")
        
        report["structure"]["suspended"] = is_suspended
        report["structure"]["suspended_reasons"] = reasons
    
    # 建议
    if report["structure"].get("suspended"):
        report["advice"].append("⚠ 悬置状态: 机构买盘衰减，等待外部催化")
        if cost:
            report["advice"].append(f"📏 建议收紧防守至成本附近 ({cost})")
    
    return report


def format_report(report: dict) -> str:
    """格式化输出"""
    sym = report["symbol"]
    lines = []
    lines.append(f"\n[强化] {sym}  {report['analyzed_at'][:19]}")
    lines.append("=" * 55)
    
    # 起涨点
    lp = report["structure"].get("launch_point", {})
    if lp.get("found"):
        lines.append(f"起涨点: {lp['launch_date']}  底部: {lp['lowest_date']}@{lp['lowest_price']:.2f}")
        lines.append(f"涨幅: {lp['rally_pct']}%  (从{lp['lowest_price']}到现价)")
    
    # 逐日摘要
    lines.append(f"\n逐日追踪:")
    for d in report["daily_breakdown"]:
        net = d["big_blocks"]["net_vol"]
        net_s = f"+{net}" if net > 0 else str(net)
        vwap_s = "🔼" if d["close_vs_vwap"] == "above" else "🔽"
        lines.append(f"  {d['date'][-5:]} 收{d['close']:.2f} {vwap_s}VWAP{d['vwap']:.2f} 大单净{net_s}手")
    
    # 趋势
    t = report.get("trend", {})
    if t:
        lines.append(f"\n趋势:")
        lines.append(f"  买盘流量: {t.get('net_trend', '?')}")
        game = t.get("game_zone_buy_pct", [])
        if len(game) >= 2:
            lines.append(f"  博弈带买盘: {game[-2]}% → {game[-1]}% ({t.get('game_buy_trend', '?')})")
    
    # 悬置判定
    s = report["structure"]
    if s.get("suspended"):
        lines.append(f"\n⚠ 悬置状态")
        for r in s.get("suspended_reasons", []):
            lines.append(f"  • {r}")
    
    # 建议
    if report["advice"]:
        lines.append(f"\n建议:")
        for a in report["advice"]:
            lines.append(f"  {a}")
    
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("用法: reinforce SYM [cost]")
        sys.exit(1)
    
    sym = sys.argv[1]
    cost = float(sys.argv[2]) if len(sys.argv) > 2 else None
    
    report = reinforce(sym, cost)
    print(format_report(report))
