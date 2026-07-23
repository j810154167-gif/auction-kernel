#!/usr/bin/env python3
"""
20260618 早盘数据预加载脚本
- 扫描全部主板标的 2日K线 → 识别昨日涨停
- 计算 VWAP 锚点（底价/7%天花板）
- 爬取东方财富成交前十行业板块
输出: handoff/data_preload.json
"""
import csv, json, os, re, ssl, sys, time
import urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone, timedelta
TODAY = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")
YESTERDAY = (datetime.now(timezone(timedelta(hours=8))) - timedelta(days=1)).strftime("%Y-%m-%d")
from pathlib import Path
from typing import Any

# ── Paths ──────────────────────────────────────────────────────
SCRIPT_DIR  = Path(__file__).resolve().parent
from core.v20260713.paths import HANDOFF as OUT_DIR, load_api_key
from core.v20260713.paths import today_str  # unused, kept for compatibility
ROOT = OUT_DIR.parent.parent  # workspace root
DEFAULT_STOCK_CSV = ROOT / "data" / "static" / "all_stocks_20260306.csv"
BATCH_SIZE  = 100
MAX_RETRIES = 2
UA          = "TickFlowExpertGovernance/1.0"
BASE        = "https://api.tickflow.org"

OUT_DIR.mkdir(parents=True, exist_ok=True)


# ── API key loader ────────────────────────────────────────────
# Delegates to paths.load_api_key()


# ── TickFlow HTTP ──────────────────────────────────────────────
def tf_get(path: str, params: dict | None = None, timeout: int = 20) -> dict:
    api_key = load_api_key()
    url = f"{BASE}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params, doseq=False)
    req = urllib.request.Request(url, headers={
        "x-api-key": api_key,
        "accept": "application/json",
        "user-agent": UA,
    })
    started = time.time()
    last_err = ""
    for attempt in range(MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout,
                                         context=ssl.create_default_context()) as resp:
                elapsed = round((time.time() - started) * 1000)
                return {"ok": True, "status": resp.status,
                        "elapsed_ms": elapsed,
                        "data": json.loads(resp.read())}
        except urllib.error.HTTPError as exc:
            last_err = f"HTTP {exc.code}: {exc.read().decode(errors='replace')[:150]}"
            if exc.code == 429 and attempt < MAX_RETRIES:
                time.sleep(1.5 * (attempt + 1))
                continue
            break
        except Exception as exc:
            last_err = f"{type(exc).__name__}: {exc}"
            if attempt < MAX_RETRIES:
                time.sleep(1)
                continue
            break
    elapsed = round((time.time() - started) * 1000)
    return {"ok": False, "elapsed_ms": elapsed, "error": last_err}


# ── Stock list ─────────────────────────────────────────────────
def stock_csv_path() -> Path:
    configured = os.environ.get("HERMES_STOCK_CSV", "").strip()
    return Path(configured).expanduser() if configured else DEFAULT_STOCK_CSV


def load_mainboard_symbols() -> list[str]:
    syms: list[str] = []
    with open(stock_csv_path(), encoding="utf-8") as f:
        for row in csv.DictReader(f):
            code = row.get("code", "").strip()
            name = row.get("code_name", "").strip()
            if any(kw in name for kw in ("指数", "B股", "基金", "债券")):
                continue
            if code.startswith("sh.60"):
                syms.append(f"{code[3:]}.SH")
            elif code.startswith("sz.00"):
                syms.append(f"{code[3:]}.SZ")
    return syms


# ── K-line batch (2-day) ───────────────────────────────────────
def batch_klines_2day(symbols: list[str]) -> dict[str, Any]:
    """Returns {symbol: {prev_close, close, volume, amount, vwap, change_pct, high, low}}"""
    results: dict[str, Any] = {}
    total = len(symbols)
    for i in range(0, total, BATCH_SIZE):
        batch = symbols[i:i + BATCH_SIZE]
        r = tf_get("/v1/klines/batch", {
            "symbols": ",".join(batch),
            "period": "1d", "count": "2", "end_date": YESTERDAY, "adjust": "none",
        })
        if not r["ok"]:
            print(f"  ⚠ batch {i//BATCH_SIZE+1}: {r['error'][:100]}", file=sys.stderr)
            time.sleep(0.5)
            continue

        data = r["data"].get("data", {}) if isinstance(r["data"], dict) else {}
        for sym, k in data.items():
            if not isinstance(k, dict):
                continue
            closes  = k.get("close", [])
            volumes = k.get("volume", [])
            amounts = k.get("amount", [])
            highs   = k.get("high", [])
            lows    = k.get("low", [])
            if not isinstance(closes, list) or len(closes) < 2:
                continue
            prev_c = closes[0]
            close  = closes[1]
            vol    = volumes[1] if len(volumes) >= 2 else 0
            amt    = amounts[1] if len(amounts) >= 2 else 0
            high   = highs[1]   if len(highs) >= 2   else close
            low_p  = lows[1]    if len(lows) >= 2    else close
            if prev_c <= 0:
                continue
            pct  = (close - prev_c) / prev_c
            # Volume is in 手 (lots of 100 shares), amount is in 元
            vwap = amt / (vol * 100) if vol > 0 else close
            results[sym] = {
                "prev_close": prev_c, "close": close,
                "high": high, "low": low_p,
                "volume_lots": vol, "amount": amt,
                "vwap": round(vwap, 4),
                "change_pct": round(pct, 6),
            }

        if (i // BATCH_SIZE) % 10 == 9:
            print(f"  ... {min(i+BATCH_SIZE, total)}/{total} | {len(results)} with data")

        time.sleep(0.10)
    return results


# ── Limit-up filter ────────────────────────────────────────────
def detect_limit_ups(klines: dict) -> list[dict]:
    lu: list[dict] = []
    for sym, k in klines.items():
        if k["change_pct"] < 0.098:
            continue
        lu.append({
            "symbol": sym,
            "yesterday_close": k["close"],
            "prev_close": k["prev_close"],
            "change_pct": k["change_pct"],
            "volume_lots": k["volume_lots"],
            "amount": k["amount"],
            "vwap": k["vwap"],
            "vwap_floor": round(k["vwap"], 4),
            "vwap_ceiling": round(k["vwap"] * 1.07, 4),
            "vwap_ceiling_pct": 7.0,
            "high": k["high"],
            "low": k["low"],
        })
    return sorted(lu, key=lambda x: x["change_pct"], reverse=True)


# ── Eastmoney top-10 sectors (via push2delay) ──────────────────
def fetch_sectors() -> list[dict]:
    params = {
        "pn": "1", "pz": "10", "po": "1", "np": "1",
        "fltt": "2", "invt": "2",
        "fid": "f62",
        "fs": "m:90+t:2",
        "fields": "f2,f3,f12,f14,f20,f62,f104,f105,f128,f136,f140",
    }
    url = f"https://push2delay.eastmoney.com/api/qt/clist/get?{urllib.parse.urlencode(params)}"
    try:
        req = urllib.request.Request(url, headers={
            "Referer": "https://data.eastmoney.com/",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            if data.get("rc") != 0:
                return []
            items = data.get("data", {}).get("diff", [])
            return [{
                "code": it.get("f12", ""),  # e.g. BK0470
                "name": it.get("f14", ""),
                "change_pct": it.get("f3", None),
                "turnover_amount": it.get("f62", None),
                "up_count": it.get("f104", None),
                "down_count": it.get("f105", None),
                "leading_stock_code": it.get("f140", ""),
                "leading_stock_name": it.get("f128", ""),
                "leading_change": it.get("f136", None),
            } for it in items]
    except Exception as exc:
        print(f"  ⚠ Sector fetch failed: {exc}", file=sys.stderr)
        return []


# ── Main ───────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print(f"  {TODAY} 早盘数据预加载")
    print(f"  {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)
    t0 = time.time()

    # 1
    syms = load_mainboard_symbols()
    print(f"\n[1/4] 主板标的: {len(syms)} 只")

    # 2
    print(f"\n[2/4] 批量查询 2日K线 (batch={BATCH_SIZE}) ...")
    kldata = batch_klines_2day(syms)
    print(f"  → {len(kldata)} 个标的有数据")

    # 3
    lus = detect_limit_ups(kldata)
    print(f"\n[3/4] 涨停检测: {len(lus)} 只")

    # 4
    sectors = fetch_sectors()
    print(f"\n[4/4] 成交前十板块: {len(sectors)} 个")

    # Output
    elapsed = round(time.time() - t0, 1)
    out = {
        "meta": {
            "date": TODAY,
            "data_date": YESTERDAY,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "elapsed_seconds": elapsed,
            "total_scanned": len(syms),
        },
        "limit_up_stocks": lus,
        "top_sectors": sectors,
    }
    opath = OUT_DIR / "data_preload.json"
    with open(opath, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=str)

    print(f"\n{'=' * 60}")
    print(f"  ✅ 完成 ({elapsed}s) → {opath}")
    print(f"  涨停: {len(lus)} | 板块: {len(sectors)}")
    print(f"{'=' * 60}")

    if sectors:
        print("\n── 成交前十板块 ──")
        for i, s in enumerate(sectors, 1):
            print(f"  {i:2}. {s['name']:8s}  "
                  f"成交:{s.get('turnover_amount','?')}  "
                  f"涨跌:{s.get('change_pct','?')}  "
                  f"领涨:{s.get('leading_stock_name','?')}")

    if lus:
        print(f"\n── 涨停前10 ──")
        for i, s in enumerate(lus[:10], 1):
            print(f"  {i:2}. {s['symbol']:12s}  "
                  f"+{s['change_pct']*100:5.2f}%  "
                  f"VWAP:{s['vwap']:8.2f}  "
                  f"量:{s['volume_lots']}手")

    return out


if __name__ == "__main__":
    main()
