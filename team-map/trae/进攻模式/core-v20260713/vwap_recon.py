"""
VWAP多日重建 — 5-Day VWAP Reconstruction

每只候选拉5日K线，计算VWAP位置标记。
数据源: TickFlow klines REST API
"""

import asyncio
import json
import os
import ssl
import urllib.request
from datetime import datetime, timezone, timedelta


async def _fetch_klines_async(symbols: list[str], days: int = 5) -> dict[str, list[dict]]:
    """Fetch klines via TickFlow REST API directly (column-oriented format)."""
    api_key = os.environ.get("TICKFLOW_API_KEY", "")
    if not api_key:
        key_file = os.environ.get("TICKFLOW_API_KEY_FILE", "")
        if key_file:
            with open(os.path.expanduser(key_file)) as f:
                api_key = f.read().strip()
    if not api_key:
        raise RuntimeError("TickFlow API key missing")

    CST = timezone(timedelta(hours=8))
    yesterday = (datetime.now(CST) - timedelta(days=1)).strftime("%Y-%m-%d")
    base_url = os.environ.get("TICKFLOW_BASE_URL", "https://api.tickflow.org")

    out = {}
    batch_size = 100
    for i in range(0, len(symbols), batch_size):
        batch = symbols[i:i + batch_size]
        url = f"{base_url}/v1/klines/batch?symbols={','.join(batch)}&period=1d&count={days}&end_date={yesterday}&adjust=none"
        req = urllib.request.Request(url, headers={
            "x-api-key": api_key,
            "accept": "application/json",
            "user-agent": "datakit/1.0",
        })
        try:
            with urllib.request.urlopen(req, timeout=20, context=ssl.create_default_context()) as resp:
                data = json.loads(resp.read())
        except Exception as e:
            print(f"  [_fetch_klines] HTTP failed: {e}")
            continue

        items = data.get("data", {})
        if isinstance(items, dict):
            for sym, bars in items.items():
                if isinstance(bars, dict) and any(isinstance(v, list) for v in bars.values()):
                    lists = bars
                    if lists:
                        keys = list(lists.keys())
                        n = len(lists[keys[0]])
                        rows = []
                        for idx in range(n):
                            ts = lists.get('timestamp', [0]*n)[idx] if 'timestamp' in lists else 0
                            date_str = datetime.fromtimestamp(ts/1000, tz=CST).strftime('%Y-%m-%d') if ts else ''
                            rows.append({
                                "date": date_str,
                                "open": float(lists.get('open', [0]*n)[idx]),
                                "high": float(lists.get('high', [0]*n)[idx]),
                                "low": float(lists.get('low', [0]*n)[idx]),
                                "close": float(lists.get('close', [0]*n)[idx]),
                                "volume": int(float(lists.get('volume', [0]*n)[idx])),
                            })
                        out[sym] = rows
    return out


def _classify_vwap_position(auction_price: float, vwaps: list[float]) -> tuple[str, str]:
    """
    Classify current price position relative to 5-day VWAP channel.
    Returns (position, detail).

    position values:
      - "gap": today's auction price > 15% from 5-day VWAP mean
      - "above": price > VWAP for 3+ consecutive days
      - "below": price < VWAP for 3+ consecutive days
      - "oscillating": crossing VWAP
      - "unknown": insufficient data
    """
    if not vwaps:
        return "unknown", "无K线数据"

    vwap_mean = sum(vwaps) / len(vwaps)
    if vwap_mean <= 0:
        return "unknown", "VWAP均值=0"

    # Gap detection: auction price > 15% from 5-day VWAP mean
    deviation_pct = abs(auction_price - vwap_mean) / vwap_mean * 100
    if deviation_pct > 15:
        direction = "之上" if auction_price > vwap_mean else "之下"
        return "gap", f"竞价价偏离VWAP均值{deviation_pct:.1f}%(5日均={vwap_mean:.2f})"

    # Count consecutive days above/below
    above_count = 0
    below_count = 0
    for v in vwaps:
        if auction_price > v:
            above_count += 1
            below_count = 0
        elif auction_price < v:
            below_count += 1
            above_count = 0
        else:
            above_count = below_count = 0

    if above_count >= 3:
        return "above", f"持续高于VWAP{above_count}日(5日均={vwap_mean:.2f})"
    elif below_count >= 3:
        return "below", f"持续低于VWAP{below_count}日(5日均={vwap_mean:.2f})"

    vwap_min = min(vwaps)
    vwap_max = max(vwaps)
    return "oscillating", f"VWAP区间[{vwap_min:.2f}-{vwap_max:.2f}](5日均={vwap_mean:.2f})"


def apply_vwap_reconstruction(candidates: list[dict]) -> list[dict]:
    """
    VWAP多日重建。
    
    Pull 5-day klines, compute (H+L+C)/3 VWAP approximation,
    classify position for each candidate.
    """
    if not candidates:
        return candidates

    symbols = [c['symbol'] for c in candidates]

    try:
        klines_map = asyncio.run(_fetch_klines_async(symbols, days=5))
    except Exception as e:
        print(f"  [vwap_recon] ⚠️ K线获取失败: {e}")
        for c in candidates:
            c['marks']['vwap_position'] = "unknown"
            c['marks']['vwap_position_detail'] = str(e)[:100]
        return candidates

    classified = {"gap": 0, "above": 0, "below": 0, "oscillating": 0, "unknown": 0}

    for c in candidates:
        sym = c['symbol']
        klines = klines_map.get(sym, [])

        if not klines:
            c['marks']['vwap_position'] = "unknown"
            c['marks']['vwap_position_detail'] = "无K线数据"
            classified["unknown"] += 1
            continue

        # (H+L+C)/3 VWAP approximation for each day
        vwaps = []
        for k in klines:
            vwap_proxy = (k['high'] + k['low'] + k['close']) / 3
            vwaps.append(vwap_proxy)

        auction_price = c.get('auction_price', 0)
        position, detail = _classify_vwap_position(auction_price, vwaps)

        c['marks']['vwap_position'] = position
        c['marks']['vwap_position_detail'] = detail
        classified[position] = classified.get(position, 0) + 1

    print(f"  [vwap_recon] VWAP定位: gap={classified['gap']} above={classified['above']} below={classified['below']} oscillating={classified['oscillating']}")
    return candidates
