"""
Scoring Engine v20260713 — 进攻体系核心

独立建池(主板) → T-1涨停识别 → VWAP锚点 → Gate-as-Modifier → chg排序
人脑决策友好型。5000→74→10→人剃N。

用法:
  from core.v20260713.scoring_engine import build_t_minus_1_pool, score_pool
"""
import os, json, subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

CST = timezone(timedelta(hours=8))
TICKFLOW = "https://api.tickflow.org/v1"
API_KEY_FILE = Path(os.environ.get(
    "TICKFLOW_API_KEY_FILE",
    "/Users/fiona/.openclaw/workspace/skills/tickflow-expert-governance/tickflow expert api.txt",
)).expanduser()


def load_api_key() -> str:
    """环境变量优先，否则读取本机凭据文件；不把密钥写入代码或产物。"""
    key = os.environ.get("TICKFLOW_API_KEY", "").strip()
    if key:
        return key
    try:
        return API_KEY_FILE.read_text().strip()
    except Exception:
        return ""

# ── Stock list ──

def fetch_stock_list() -> list[str]:
    """
    从 TickFlow 实时拉取 A 股主板标的列表。
    排除: 000开头(指数)、688(科创)、300/301(创业)、8/4(北交)
    """
    symbols = []
    
    for exchange in ["SH", "SZ"]:
        r = subprocess.run([
            'curl', '-sS', '--max-time', '15', '--noproxy', '*',
            '-H', f'x-api-key: {load_api_key()}',
            f"{TICKFLOW}/exchanges/{exchange}/instruments?type=stock"
        ], capture_output=True, text=True)
        
        try:
            items = json.loads(r.stdout).get('data', [])
        except json.JSONDecodeError:
            continue
        
        for item in items:
            sym = item.get('symbol', '')
            name = item.get('name', '')
            code = sym.split('.')[0] if '.' in sym else ''
            item_type = item.get('type', 'stock')
            
            if not code or len(code) != 6:
                continue
            # 排除指数/ETF/基金
            if item_type not in ('stock',):
                continue
            # ST 过滤
            if 'ST' in name.upper():
                continue
            # SH: 000xxx 是指数
            if exchange == 'SH' and code.startswith('000'):
                continue
            # SZ: 000-003 是主板（保留）；排除北交/创业/科创
            if code.startswith('8') or code.startswith('4'):
                continue  # 北交
            if code.startswith('688') or code.startswith('300') or code.startswith('301'):
                continue  # 科创/创业
            if exchange == 'SH' and not (code.startswith('60') or code.startswith('5')):
                continue  # SH 只保留 60/5 开头的主板
            if exchange == 'SZ' and not (code.startswith('00') or code.startswith('002') or code.startswith('003')):
                continue  # SZ 只保留 00/002/003 主板
            
            symbols.append(sym)
    
    return symbols


# ── Pool building ──

def build_t_minus_1_pool(trading_date: str, symbols: Optional[list[str]] = None) -> list[dict]:
    """
    拉 5 日 K 线 → 识别 T-1 涨停(≥9.5%) → 计算 VWAP 锚点。
    返回候选池列表。
    """
    if symbols is None:
        symbols = fetch_stock_list()
    
    BATCH = 50
    limit_up = []
    total = len(symbols)
    
    for i in range(0, total, BATCH):
        batch = symbols[i:i + BATCH]
        r = subprocess.run([
            'curl', '-sS', '--max-time', '30', '--noproxy', '*',
            '-H', f'x-api-key: {load_api_key()}',
            f"{TICKFLOW}/klines/batch?symbols={','.join(batch)}&period=1d&count=10"
        ], capture_output=True, text=True)
        
        try:
            data = json.loads(r.stdout).get('data', {})
        except json.JSONDecodeError:
            continue
        
        for sym, bars in data.items():
            closes = bars.get('close', [])
            volumes = bars.get('volume', [])
            amounts = bars.get('amount', [])
            highs = bars.get('high', [])
            timestamps = bars.get('timestamp', [])
            
            if len(closes) < 2:
                continue
            
            # 解码时间戳 → 日期索引 (不依赖固定位置)
            date_idx = {}
            for i, t in enumerate(timestamps):
                d = datetime.fromtimestamp(t / 1000, tz=CST).strftime("%Y-%m-%d")
                date_idx[d] = i
            
            # 找 T-1 和 T-2
            if trading_date not in date_idx:
                continue
            
            idx_t1 = date_idx[trading_date]
            # T-2: 前一个交易日
            d2 = datetime.strptime(trading_date, "%Y-%m-%d") - timedelta(days=1)
            while d2.strftime("%Y-%m-%d") not in date_idx and d2 > datetime(2026, 1, 1):
                d2 -= timedelta(days=1)
            t2_str = d2.strftime("%Y-%m-%d")
            if t2_str not in date_idx:
                continue
            idx_t2 = date_idx[t2_str]
            
            close_t1 = closes[idx_t1]
            close_t2 = closes[idx_t2]
            
            if close_t1 <= 0 or close_t2 <= 0:
                continue
            
            chg = (close_t1 - close_t2) / close_t2 * 100
            if chg < 9.5:
                continue
            
            # 5 日 VWAP
            valid = [c for c in closes if c > 0]
            vwap5 = sum(valid) / len(valid) if valid else close_t1
            
            limit_up.append({
                "symbol": sym,
                "close_t1": close_t1,
                "prev_close": close_t2,
                "change_pct": round(chg, 2),
                "high_t1": highs[idx_t1] if len(highs) > idx_t1 else 0,
                "volume_t1": volumes[idx_t1] if len(volumes) > idx_t1 else 0,
                "amount_t1": amounts[idx_t1] if len(amounts) > idx_t1 else 0,
                "vwap": round(vwap5, 2),
                "vwap_floor": round(vwap5 * 0.85, 2),
            })
    
    return limit_up


# ── Quotes ──

def fetch_pool_quotes(pool: list[dict]) -> list[dict]:
    """拉竞价/实时报价，附加到候选池每个标的。"""
    symbols = [s["symbol"] for s in pool]
    
    quotes = {}
    for i in range(0, len(symbols), 50):
        batch = symbols[i:i + 50]
        r = subprocess.run([
            'curl', '-sS', '--max-time', '15', '--noproxy', '*',
            '-H', f'x-api-key: {load_api_key()}',
            f"{TICKFLOW}/quotes?symbols={','.join(batch)}"
        ], capture_output=True, text=True)
        try:
            for item in json.loads(r.stdout).get('data', []):
                quotes[item['symbol']] = item
        except json.JSONDecodeError:
            pass
    
    for s in pool:
        q = quotes.get(s["symbol"], {})
        ext = q.get('ext', {}) if isinstance(q.get('ext'), dict) else {}
        s["open"] = q.get('open', 0) or 0  # 竞价开盘价
        s["last_price"] = q.get('last_price', 0) or 0
        s["volume_now"] = q.get('volume', 0) or 0
        s["amount_now"] = q.get('amount', 0) or 0
        s["name"] = ext.get('name', q.get('name', ''))
        
        if s["open"] > 0 and s.get("close_t1", s.get("prev_close", 0)) > 0:
            s["open_chg_pct"] = round((s["open"] - s.get("close_t1", s.get("prev_close", 0))) / s.get("close_t1", s.get("prev_close", 0)) * 100, 2)
        else:
            s["open_chg_pct"] = 0
    
    return [s for s in pool if s.get("open", 0) > 0]


# ── Gate-as-Modifier scoring ──

def score_pool(pool: list[dict]) -> list[dict]:
    """
    Gate-as-Modifier 评分 + chg 排序。
    公式: score = chg - max(0,dev-7) + min(vol/10000,5) + vol_bonus - penalty×0.4
    """
    if not pool:
        return []
    
    # ── Dynamic ceiling (P95 price/VWAP) ──
    ratios = []
    for s in pool:
        if s["vwap"] > 0 and s["open"] > 0:
            ratios.append(s["open"] / s["vwap"])
    
    ratios.sort()
    dynamic_ceil = round(max(1.09, min(1.15, ratios[min(int(len(ratios) * 0.95), len(ratios) - 1)])), 4)
    
    # ── Gate penalties ──
    passed = []
    for s in pool:
        price = s["open"]
        chg = s["open_chg_pct"]
        vwap_val = s["vwap"]
        vwap_floor = s.get("vwap_floor", 0)
        vol_now = s.get("volume_now", 0)
        amt_now = s.get("amount_now", 0)
        yest_vol = s.get("volume_t1", 0)
        yest_amt = s.get("amount_t1", 0)
        
        dev = round((price / vwap_val - 1) * 100, 2) if vwap_val > 0 else 0
        gate_penalty = 0.0
        penalties = []
        
        # Gate ①: Price
        vwap_ceiling = round(vwap_val * dynamic_ceil, 2)
        if price < vwap_floor and vwap_floor > 0:
            excess = (vwap_floor - price) / vwap_floor * 100
            gate_penalty += min(excess * 5, 30)
            penalties.append(f"①破底(-{min(excess*5,30):.0f})")
        elif price > vwap_ceiling:
            excess = (price - vwap_ceiling) / vwap_ceiling * 100
            gate_penalty += min(excess * 3, 20)
            penalties.append(f"①超天花板(-{min(excess*3,20):.0f})")
        
        # Gate ②: Volume (note: non-auction data → uniform -8)
        if vol_now <= 0 or amt_now <= 0:
            gate_penalty += 8
            penalties.append("②无竞价数据(-8)")
        
        # Gate ③: Tier (sector map not connected → uniform if chg≤0)
        if chg <= 0:
            gate_penalty += 10
            penalties.append("③涨幅≤0(-10)")
        
        passed.append({
            "symbol": s["symbol"],
            "name": s["name"],
            "price": price,
            "chg": chg,
            "dev": dev,
            "vol": vol_now,
            "vwap": vwap_val,
            "vwap_floor": vwap_floor,
            "gate_penalty": round(gate_penalty, 1),
            "penalties": penalties,
        })
    
    # Gate ①b: VWAP deviation P75
    devs = sorted([p["dev"] for p in passed])
    vols = sorted([p["vol"] for p in passed if p["vol"] > 0])
    n = len(devs)
    p75_dev = devs[min(int(n * 0.75), n - 1)]
    dcap = round(max(7.0, min(12.0, p75_dev)), 1)
    vmed = vols[len(vols) // 2] if vols else 20000
    
    for p in passed:
        if p["dev"] > dcap:
            if p["vol"] < vmed:
                p["gate_penalty"] += 15
                p["penalties"].append(f"①b:偏差{p['dev']:+.1f}%>P75({dcap}%)+薄量(-15)")
            else:
                p["gate_penalty"] += 3
                p["penalties"].append(f"①b:偏差{p['dev']:+.1f}%>P75({dcap}%)(-3)")
    
    # ── Composite score ──
    vols2 = [p["vol"] for p in passed if p["vol"] > 0]
    mvol = sorted(vols2)[len(vols2) // 2] if vols2 else 20000
    
    for p in passed:
        p["score"] = round(
            p["chg"]
            - max(0, p["dev"] - 7)
            + min(p["vol"] / 10000, 5)
            + (2 if p["vol"] >= mvol else 0)
            - p["gate_penalty"] * 0.4,
            1
        )
    
    passed.sort(key=lambda x: x["score"], reverse=True)
    return passed


# ── Full pipeline ──

def full_pipeline(trading_date: str) -> dict:
    """
    完整流水: 拉列表 → 识涨停 → 拉报价 → 评分 → 排序
    """
    print(f"[scoring] 拉取标的列表...")
    symbols = fetch_stock_list()
    print(f"[scoring] 主板标的: {len(symbols)} 只")
    
    print(f"[scoring] 扫描 T-1({trading_date}) 涨停...")
    pool = build_t_minus_1_pool(trading_date, symbols)
    print(f"[scoring] 涨停池: {len(pool)} 只")
    
    if not pool:
        return {"error": "无涨停标的", "pool": [], "ranking": []}
    
    print(f"[scoring] 拉取竞价报价...")
    pool = fetch_pool_quotes(pool)
    print(f"[scoring] 有效报价: {len(pool)} 只")
    
    print(f"[scoring] Gate-as-Modifier 评分...")
    ranked = score_pool(pool)
    
    return {
        "meta": {
            "date": trading_date,
            "scanned": len(symbols),
            "limit_up": len(pool),
            "ranked": len(ranked),
        },
        "pool": pool,
        "ranking": ranked,
    }


# CLI helper
if __name__ == "__main__":
    import sys
    date = sys.argv[1] if len(sys.argv) > 1 else datetime.now(CST).strftime("%Y-%m-%d")
    result = full_pipeline(date)
    
    if "error" in result:
        print(result["error"])
        sys.exit(1)
    
    ranking = result["ranking"]
    print(f"\n{'#':<3} {'标的':<14} {'名称':<8} {'竞':>7} {'竞涨':>7} {'偏差':>6} {'罚':>4} {'得分':>8}")
    print("-" * 68)
    for i, p in enumerate(ranking[:15], 1):
        top = "★" if i == 1 else ""
        print(f"{top}{i:<2} {p['symbol']:<14} {p['name']:<8} {p['price']:>7.2f} {p['chg']:>+6.1f}% {p['dev']:>+5.1f}% {p['gate_penalty']:>4.1f} {p['score']:>+8.1f}")
