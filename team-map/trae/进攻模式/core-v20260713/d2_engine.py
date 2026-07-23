#!/usr/bin/env python3
"""
D2 Engine — 两段式反转确认策略
- S1 (09:30-09:35): WebSocket观测 → VWAP+PA异常预警
- S2 (09:35-09:40): 判定决策 → 区分真反转 vs 震仓
- 标的池: Pool2(历史≤50) + Pool1(今日市场Top100) 串行去重
- 独立于D1过滤结果, 自身点火, 自身决策
"""
import asyncio, json, os, sys, time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any
from collections import defaultdict

for k in ("ALL_PROXY","all_proxy","HTTPS_PROXY","https_proxy","HTTP_PROXY","http_proxy"):
    os.environ.pop(k, None)
import websockets

# ── Paths ──────────────────────────────────────────────────────
SCRIPT_DIR  = Path(__file__).resolve().parent
from paths import HANDOFF, load_api_key
from data_source_governance import load_acceptance_metadata
WS_URI      = "wss://api.tickflow.org/v1/ws/stream"
MAX_SYMBOLS = 100
S1_DURATION = 300  # 5 minutes
S2_DURATION = 300  # 5 minutes

HANDOFF.mkdir(parents=True, exist_ok=True)

# ── Helpers ────────────────────────────────────────────────────
def load_key() -> str:
    return load_api_key()

def cst_now() -> datetime:
    return datetime.now(timezone(timedelta(hours=8)))

def ts() -> str:
    return cst_now().strftime("%H:%M:%S")

def iso() -> str:
    return cst_now().isoformat()


# ── D2 candidate pools ──────────────────────────────────────────
def _append_unique(symbols: list[str], symbol: str | None, limit: int | None = None) -> None:
    if not symbol or symbol in symbols:
        return
    if limit is not None and len(symbols) >= limit:
        return
    symbols.append(symbol)


def _handoff_root(handoff_root: Path | str | None = None) -> Path:
    if handoff_root is not None:
        return Path(handoff_root)
    return Path(os.environ.get("HERMES_HISTORY_HANDOFF_ROOT", SCRIPT_DIR / "handoff"))


def _trade_date(value: str | None = None) -> str:
    return value or cst_now().strftime("%Y-%m-%d")


def _score_market_item(item: dict[str, Any]) -> float:
    amount = item.get("amount") or item.get("auction_amount") or item.get("turnover") or 0
    if amount:
        return float(amount)
    price = item.get("last_price") or item.get("price") or item.get("open") or item.get("auction_price") or 0
    volume = item.get("volume") or item.get("volume_lots") or item.get("auction_volume") or 0
    return float(price or 0) * float(volume or 0)


def load_historical_pool(
    max_stocks: int = 50,
    *,
    trade_date: str | None = None,
    handoff_root: Path | str | None = None,
) -> list[str]:
    """Load Pool2: historical D1 Top25 + D2 decisions from T-1 to T-5.

    Pool2 remains historical context. It is not allowed to consume today's
    filtered_pool.json, because D2 must be logically independent from today's D1.
    """
    base = _handoff_root(handoff_root)
    today = datetime.strptime(_trade_date(trade_date), "%Y-%m-%d").replace(tzinfo=timezone(timedelta(hours=8)))
    pool: list[str] = []

    days_collected = 0
    check_date = today
    while days_collected < 5:
        check_date = check_date - timedelta(days=1)
        if check_date.weekday() >= 5:  # skip weekends
            continue
        date_str = check_date.strftime("%Y-%m-%d")
        dp = base / date_str

        # Pool2 historical D1 traces only, never today's D1 filtered pool.
        fp = dp / "filtered_pool.json"
        if fp.exists():
            data = json.loads(fp.read_text(encoding="utf-8"))
            for c in data.get("candidates", [])[:25]:
                _append_unique(pool, c.get("symbol"), max_stocks)

        # Pool2 historical D2 decisions.
        for decision_file in ("decision_2.json", "d2_decision.json", "terminal_packet.json"):
            tp = dp / decision_file
            if not tp.exists():
                continue
            data = json.loads(tp.read_text(encoding="utf-8"))
            if isinstance(data.get("decision"), dict):
                _append_unique(pool, data["decision"].get("symbol"), max_stocks)
            if isinstance(data.get("s2_decision"), dict):
                _append_unique(pool, data["s2_decision"].get("symbol"), max_stocks)
            for d in data.get("decisions", [])[:5]:
                _append_unique(pool, d.get("symbol"), max_stocks)

        days_collected += 1

    print(f"[{ts()}] 📋 D2 Pool2历史池: {len(pool)}只 (T-1~T-{days_collected})")
    return pool[:max_stocks]


def load_market_pool(
    max_stocks: int = 100,
    *,
    trade_date: str | None = None,
    handoff_root: Path | str | None = None,
) -> dict[str, Any]:
    """Load Pool1: today's market-driven candidates, independent of D1 filtered_pool."""
    base = _handoff_root(handoff_root)
    day_dir = base / _trade_date(trade_date)

    snapshot_path = day_dir / "auction_snapshot.json"
    if snapshot_path.exists():
        data = json.loads(snapshot_path.read_text(encoding="utf-8"))
        snapshot = data.get("snapshot", {})
        ranked = sorted(
            ((symbol, payload) for symbol, payload in snapshot.items() if isinstance(payload, dict)),
            key=lambda pair: _score_market_item(pair[1]),
            reverse=True,
        )
        symbols = [symbol for symbol, _ in ranked[:max_stocks]]
        if symbols:
            return {"symbols": symbols, "source": "auction_snapshot", "quality": "ok", "degraded_reasons": []}

    preload_path = day_dir / "data_preload.json"
    if preload_path.exists():
        data = json.loads(preload_path.read_text(encoding="utf-8"))
        ranked = sorted(
            (item for item in data.get("limit_up_stocks", []) if isinstance(item, dict) and item.get("symbol")),
            key=_score_market_item,
            reverse=True,
        )
        symbols = [item["symbol"] for item in ranked[:max_stocks]]
        if symbols:
            return {"symbols": symbols, "source": "data_preload", "quality": "ok", "degraded_reasons": []}

    return {"symbols": [], "source": "missing", "quality": "degraded", "degraded_reasons": ["missing_market_pool1"]}


def build_d2_candidate_pool(
    *,
    trade_date: str | None = None,
    handoff_root: Path | str | None = None,
    max_symbols: int = MAX_SYMBOLS,
    pool2_max: int = 50,
    pool1_max: int = 100,
) -> dict[str, Any]:
    """Build D2 subscription pool as Pool2 historical first, then Pool1 market.

    This fixes the 0701/复盘3.0 consensus error: D2 no longer treats today's
    D1 filtered_pool.json as its market pool.
    """
    date = _trade_date(trade_date)
    pool2 = load_historical_pool(pool2_max, trade_date=date, handoff_root=handoff_root)
    pool1_payload = load_market_pool(pool1_max, trade_date=date, handoff_root=handoff_root)
    pool1 = pool1_payload["symbols"]

    symbols: list[str] = []
    for sym in pool2 + pool1:
        _append_unique(symbols, sym, max_symbols)

    degraded_reasons = list(pool1_payload.get("degraded_reasons", []))
    if not pool2:
        degraded_reasons.append("missing_historical_pool2")
    quality = "degraded" if degraded_reasons else "ok"
    return {
        "schema_version": 1,
        "trade_date": date,
        "strategy": "pool2_historical_then_pool1_market",
        "symbols": symbols,
        "pool2_historical": pool2,
        "pool1_market": pool1,
        "pool1_source": pool1_payload["source"],
        "quality": quality,
        "degraded_reasons": degraded_reasons,
    }


# ── VWAP computer ──────────────────────────────────────────────
def compute_vwap_curve(quotes: list[dict]) -> list[float]:
    """Compute cumulative VWAP at each point in the quote series."""
    vwaps = []
    cv = 0.0; ca = 0.0
    for q in quotes:
        p = q.get("last_price", 0) or q.get("open", 0) or 0
        v = q.get("volume", 0) or 0
        cv += v
        ca += p * v
        vwaps.append(ca / cv if cv > 0 else p)
    return vwaps


# ── S1: Observation phase (09:30-09:35) ────────────────────────
def s1_analyze(stock_data: dict[str, list[dict]], open_prices: dict[str, float]) -> dict[str, dict]:
    """S1: Identify stocks showing reversal warning signs.
    Returns {symbol: {vwap5, pa5, vwap_below_open, pa_below_vwap, flagged}}
    """
    alerts = {}
    for sym, quotes in stock_data.items():
        if len(quotes) < 3:
            continue
        open_p = open_prices.get(sym)
        if not open_p or open_p <= 0:
            continue
        
        vwaps = compute_vwap_curve(quotes)
        vwap5 = vwaps[-1]
        
        # S1 criteria
        last_5 = quotes[-5:] if len(quotes) >= 5 else quotes
        pa_below_count = sum(1 for q in last_5 if (q.get("last_price",0) or q.get("open",0) or 0) < vwap5)
        
        pa5 = last_5[-1].get("last_price", 0) or last_5[-1].get("open", 0) or 0
        
        flagged = (vwap5 < open_p) and (pa_below_count >= 3)
        
        alerts[sym] = {
            "open_price": open_p,
            "vwap5": round(vwap5, 2),
            "pa5": pa5,
            "vwap_below_open": vwap5 < open_p,
            "pa_below_vwap_min": pa_below_count,
            "flagged": flagged,
        }
    
    flagged_count = sum(1 for a in alerts.values() if a["flagged"])
    print(f"[{ts()}] 🔔 S1预警: {flagged_count}/{len(alerts)} 只标的异常")
    return alerts


# ── S2: Decision phase (09:35-09:40) ───────────────────────────
def s2_decide(stock_data: dict[str, list[dict]], s1_alerts: dict[str, dict]) -> dict | None:
    """S2: Confirm reversal vs shake-out from S1 alerts.
    Returns D2 decision dict or None.
    """
    confirmed = []
    for sym, s1 in s1_alerts.items():
        if not s1["flagged"]:
            continue
        quotes = stock_data.get(sym, [])
        if len(quotes) < 10:
            continue
        
        vwaps = compute_vwap_curve(quotes)
        vwap10 = vwaps[-1]
        open_p = s1["open_price"]
        
        # S2 criteria: VWAP still below open AND PA still predominantly below VWAP
        last_5 = quotes[-5:]
        pa_below = sum(1 for q in last_5 if (q.get("last_price",0) or q.get("open",0) or 0) < vwap10)
        
        # VWAP direction: S1→S2
        vwap_trend = "↓" if vwap10 < s1["vwap5"] else "↑" if vwap10 > s1["vwap5"] else "→"
        
        # ✅ True reversal: VWAP still < open, PA still < VWAP, VWAP declining
        if vwap10 < open_p and pa_below >= 3 and vwap_trend == "↓":
            pa10 = last_5[-1].get("last_price", 0) or last_5[-1].get("open", 0) or 0
            confirmed.append({
                "symbol": sym,
                "open_price": open_p,
                "s1_vwap": s1["vwap5"],
                "s2_vwap": round(vwap10, 2),
                "s2_pa": pa10,
                "vwap_trend": vwap_trend,
                "pa_below_vwap": pa_below,
                "confidence": "high" if pa_below >= 4 and vwap10 < s1["vwap5"] * 0.995 else "medium",
                "type": "true_reversal",
            })
    
    if not confirmed:
        print(f"[{ts()}] ❌ S2: 无真反转, 全部为震仓或假信号")
        return None
    
    # Pick strongest reversal: lowest PA relative to VWAP (deepest reversal)
    confirmed.sort(key=lambda x: (x["s2_pa"] - x["s2_vwap"]) / x["s2_vwap"])
    best = confirmed[0]
    
    print(f"[{ts()}] ✅ S2确认: {len(confirmed)}只真反转")
    print(f"  D2入场: {best['symbol']} PA={best['s2_pa']:.2f} VWAP={best['s2_vwap']:.2f} ({best['vwap_trend']})")
    
    return {
        "symbol": best["symbol"],
        "entry_price": best["s2_pa"],
        "entry_time": iso(),
        "reasoning": f"D2两段确认: VWAP{best['vwap_trend']} PA<VWAP{best['pa_below_vwap']}/5min 置信度{best['confidence']}",
        "s1_vwap": best["s1_vwap"],
        "s2_vwap": best["s2_vwap"],
        "confidence": best["confidence"],
        "candidates_flagged": sum(1 for a in s1_alerts.values() if a["flagged"]),
        "candidates_confirmed": len(confirmed),
    }


# ── WebSocket D2 Flow ──────────────────────────────────────────
async def run_d2_flow(symbols: list[str], pool_meta: dict[str, Any] | None = None):
    """Main D2 WebSocket flow: connect → S1 collect → S2 collect → decide"""
    api_key = load_key()
    uri = f"{WS_URI}?api_key={api_key}"
    
    stock_data: dict[str, list[dict]] = defaultdict(list)
    open_prices: dict[str, float] = {}
    
    # Wait for 09:30
    now = cst_now()
    target = now.replace(hour=9, minute=30, second=0, microsecond=0)
    if now < target:
        wait = (target - now).total_seconds()
        print(f"[{ts()}] ⏳ D2 等待 09:30 ... ({wait:.0f}s)")
        await asyncio.sleep(wait)
    
    print(f"[{ts()}] 🔌 D2 WS连接 {len(symbols)} 标的 ...")
    try:
        async with websockets.connect(uri, open_timeout=10, ping_timeout=15, proxy=None) as ws:
            sub = json.dumps({"op": "subscribe", "channel": "quotes", "symbols": symbols})
            await ws.send(sub)
            resp = await asyncio.wait_for(ws.recv(), timeout=10)
            parsed = json.loads(resp)
            if parsed.get("op") == "subscribed":
                print(f"[{ts()}] ✅ D2订阅 {parsed.get('total',0)} 标的")
            else:
                print(f"[{ts()}] ⚠ D2订阅异常: {parsed}", file=sys.stderr)
            
            # ── S1: Collect 09:30-09:35 ──
            print(f"[{ts()}] 📡 S1观测 (09:30→09:35) ...")
            s1_start = time.time()
            qcount = 0
            while time.time() - s1_start < S1_DURATION:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=2)
                    data = json.loads(msg)
                    if data.get("op") == "quotes" and "data" in data:
                        for item in data["data"]:
                            sym = item.get("symbol", "")
                            if sym in stock_data or sym in symbols:
                                stock_data[sym].append(item)
                                if sym not in open_prices:
                                    open_prices[sym] = item.get("open", 0) or item.get("last_price", 0) or 0
                                qcount += 1
                except asyncio.TimeoutError:
                    continue
            
            print(f"[{ts()}] S1完成: {qcount}条推送, {len(stock_data)}只有数据")
            s1_results = s1_analyze(dict(stock_data), open_prices)
            
            # ── Pre-alert: S1 summary for frontend ──
            flagged = [s for s, a in s1_results.items() if a.get("flagged")]
            if flagged:
                print(f"[{ts()}] 📢 预报名: {len(flagged)}只标的触发S1预警")
                for sym in flagged[:5]:
                    s1 = s1_results[sym]
                    print(f"       {sym}: VWAP{s1['vwap5']}<开盘{s1['open_price']} PA<VWAP{s1['pa_below_vwap_min']}/5min")
            else:
                print(f"[{ts()}] 📢 预报名: 无预警, 全场平稳")
            
            # ── S2: Collect 09:35-09:40 ──
            print(f"[{ts()}] 📡 S2观测 (09:35→09:40) ...")
            s2_start = time.time()
            s2_qcount = 0
            while time.time() - s2_start < S2_DURATION:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=2)
                    data = json.loads(msg)
                    if data.get("op") == "quotes" and "data" in data:
                        for item in data["data"]:
                            sym = item.get("symbol", "")
                            if sym in stock_data:
                                stock_data[sym].append(item)
                                s2_qcount += 1
                except asyncio.TimeoutError:
                    continue
            
            print(f"[{ts()}] S2完成: +{s2_qcount}条推送")
    
    except Exception as exc:
        print(f"[{ts()}] ❌ D2 WS异常: {exc}", file=sys.stderr)
    
    # ── S2 Decision ──
    decision = s2_decide(dict(stock_data), s1_results)
    
    # ── Save output ──
    pool_meta = pool_meta or {}
    output = {
        "meta": {"date": cst_now().strftime("%Y-%m-%d"), "generated_at": iso(),
                 "pool_size": len(symbols), "pool_source": pool_meta.get("strategy", "pool2_historical_then_pool1_market"),
                 "pool1_source": pool_meta.get("pool1_source"),
                 "pool_quality": pool_meta.get("quality", "unknown"),
                 "pool_degraded_reasons": pool_meta.get("degraded_reasons", []),
                 **load_acceptance_metadata(HANDOFF)},
        "s1": {"flagged": sum(1 for a in s1_results.values() if a.get("flagged")),
               "details": {s: {"vwap5": a["vwap5"], "flagged": a["flagged"]}
                          for s, a in s1_results.items() if a.get("flagged")}},
        "s2_decision": decision,
    }
    
    out_path = HANDOFF / "d2_decision.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)
    canonical_path = HANDOFF / "decision_2.json"
    with open(canonical_path, "w", encoding="utf-8") as f:
        json.dump({"meta": output["meta"], "decision": decision}, f, ensure_ascii=False, indent=2, default=str)
    
    if decision:
        print(f"\n{'='*55}")
        print(f"  🏁 D2: {decision['symbol']} @ {decision['entry_price']:.2f}")
        print(f"  置信度: {decision['confidence']} | 预警{decision['candidates_flagged']}只 → 确认{decision['candidates_confirmed']}只")
        print(f"{'='*55}")
    else:
        print(f"\n{'='*55}")
        print(f"  🏁 D2: 空仓 (无真反转信号)")
        print(f"{'='*55}")
    
    print(f"  📁 {out_path}")
    return decision


# ── Main ───────────────────────────────────────────────────────
async def main():
    print("=" * 55)
    print("  D2 Engine — 两段式反转确认")
    print(f"  {iso()}")
    print("=" * 55)
    
    pool_meta = build_d2_candidate_pool(trade_date=cst_now().strftime("%Y-%m-%d"))
    pool = pool_meta["symbols"]
    if not pool:
        print(f"[{ts()}] ❌ D2候选池为空, D2退出")
        return
    if pool_meta["quality"] == "degraded":
        print(f"[{ts()}] ⚠ D2候选池降级: {pool_meta['degraded_reasons']}")
    
    result = await run_d2_flow(pool, pool_meta=pool_meta)
    print(f"\n[{ts()}] D2 完成")
    return result


if __name__ == "__main__":
    asyncio.run(main())
