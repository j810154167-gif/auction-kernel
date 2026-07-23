"""
多日池分类 — Multi-Day Pool Classification

呼吸板/连板/回调板/延续标的分类标记。
数据源: TickFlow klines (via datakit Parquet cache)
"""

import asyncio
import os
from pathlib import Path

# Limit-up threshold: change >= 9.5%
LIMIT_UP_THRESHOLD = 9.5


async def _fetch_klines_async(symbols: list[str], days: int = 5) -> dict[str, list[dict]]:
    """Fetch klines via TickFlow REST API directly (bypasses adapter for column-oriented format)."""
    import json, ssl, time, urllib.request
    from datetime import datetime, timezone, timedelta

    # Load API key
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

        # TickFlow returns column-oriented: {symbol: {timestamp: [...], open: [...], ...}}
        items = data.get("data", {})
        if isinstance(items, dict):
            for sym, bars in items.items():
                if isinstance(bars, dict) and any(isinstance(v, list) for v in bars.values()):
                    # Column-oriented format
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
                                "amount": float(lists.get('amount', [0]*n)[idx]) if lists.get('amount') else 0,
                            })
                        out[sym] = rows
    return out


def _is_limit_up(change_pct: float) -> bool:
    """Check if a daily change qualifies as limit-up."""
    return change_pct >= LIMIT_UP_THRESHOLD


def _classify_symbol(sym: str, klines: list[dict]) -> tuple[str, str]:
    """
    Classify a single stock based on its kline history.
    Returns (pool_type, anchor).
    
    pool_type values:
      - "continuous": 2+ consecutive limit-ups
      - "breathing": limit-up → pullback → limit-up
      - "pullback": limit-up → pullback → no limit-up
      - "continuation": limit-up → small gain next day
      - "active": 2+ limit-ups in 5 days (non-consecutive)
      - "single_day": single limit-up only
      - "unknown": insufficient data
    """
    if len(klines) < 2:
        return "unknown", "none"

    # Compute daily changes from klines (assume sorted by date ascending)
    changes = []
    for k in klines:
        if k['close'] > 0 and k['open'] > 0:
            prev_close = k['open']  # approximate: prev_close ≈ open for daily bars from TickFlow
            # Actually, use close vs prev_close approximation
            # For Eastmoney data, we don't have prev_close per bar, so use open as prev
            pass
    # Better approach: compare consecutive closes
    if len(klines) >= 2:
        prevs = []
        for i in range(1, len(klines)):
            prev = klines[i - 1]
            curr = klines[i]
            if prev['close'] > 0:
                chg = (curr['close'] - prev['close']) / prev['close'] * 100
                prevs.append({
                    "date": curr['date'],
                    "change_pct": round(chg, 2),
                    "volume": curr['volume'],
                    "close": curr['close'],
                })

        if not prevs:
            return "unknown", "none"

        # Count limit-ups
        limit_up_indices = [i for i, p in enumerate(prevs) if _is_limit_up(p['change_pct'])]

        if len(limit_up_indices) >= 2:
            # Check consecutiveness
            is_consecutive = all(
                limit_up_indices[i + 1] - limit_up_indices[i] == 1
                for i in range(len(limit_up_indices) - 1)
            )
            if is_consecutive and len(limit_up_indices) >= 2:
                # Task 3.3: continuous limit-up detection
                # Use last pullback day close as anchor if exists
                anchor = "none"
                if limit_up_indices[0] > 0:
                    anchor_day = prevs[limit_up_indices[0] - 1]
                    anchor = f"{anchor_day['date']}:{anchor_day['close']:.2f}"
                return "continuous", anchor

        if len(limit_up_indices) >= 2:
            # Task 3.4: 2+ limit-ups in 5 days but non-consecutive → "active"
            return "active", "none"

        if len(limit_up_indices) == 1:
            last_up = limit_up_indices[-1]
            # Is there a day after the limit-up?
            if last_up + 1 < len(prevs):
                next_day = prevs[last_up + 1]
                # Task 3.2: breathing board detection
                # T-2 limit-up, T-1 pullback with volume < T-2 volume, today-limit-up
                prev_day = prevs[last_up]
                if next_day['change_pct'] < 0 and next_day['volume'] < prev_day['volume']:
                    # This is a pullback. Check if the next (today) would be limit-up
                    # Today's status is determined by the caller (auction engine)
                    # So mark as "pullback" context; caller determines if breathing
                    anchor = f"{next_day['date']}:{next_day['close']:.2f}"
                    return "pending_breathing", anchor  # T-1 showed pullback

                # Task 3.4: continuation (limit-up → small gain)
                if 0 < next_day['change_pct'] < 5:
                    return "continuation", f"{next_day['date']}:{next_day['close']:.2f}"
                elif next_day['change_pct'] < 0:
                    return "pullback", f"{next_day['date']}:{next_day['close']:.2f}"

            return "single_day", "none"

    return "unknown", "none"


def apply_multi_day_pool(candidates: list[dict]) -> list[dict]:
    """
    多日池分类。
    
    Pull 5-day klines via datakit, classify each candidate,
    attach marks.pool_type and marks.anchor.
    Task 3.6: merge marks — most restrictive wins on duplicates.
    """
    if not candidates:
        return candidates

    symbols = [c['symbol'] for c in candidates]

    try:
        klines_map = asyncio.run(_fetch_klines_async(symbols, days=5))
    except Exception as e:
        print(f"  [multi_day] ⚠️ K线获取失败: {e}")
        for c in candidates:
            c['marks']['pool_type'] = "unknown"
            c['marks']['anchor'] = "none"
        return candidates

    classified = {"continuous": 0, "breathing": 0, "active": 0, "pullback": 0, "continuation": 0, "single_day": 0, "unknown": 0}

    for c in candidates:
        sym = c['symbol']
        klines = klines_map.get(sym, [])

        pool_type, anchor = _classify_symbol(sym, klines)

        # Task 3.6: merge — most restrictive wins
        existing = c['marks'].get('pool_type', '')
        priority = {"continuous": 6, "breathing": 5, "active": 4, "pullback": 3, "continuation": 2, "single_day": 1, "unknown": 0, "pending_breathing": 0}
        if priority.get(pool_type, 0) > priority.get(existing, 0):
            # If pending_breathing and today is limit-up → upgrade to "breathing"
            if pool_type == "pending_breathing" and abs(c.get('change_pct', 0)) >= LIMIT_UP_THRESHOLD:
                pool_type = "breathing"
        if priority.get(pool_type, 0) > priority.get(existing, 0):
            c['marks']['pool_type'] = pool_type
            c['marks']['anchor'] = anchor

        classified[pool_type] = classified.get(pool_type, 0) + 1

    print(f"  [multi_day] 分类: 连板{classified['continuous']} 呼吸{classified['breathing']} 回调{classified['pullback']} 延续{classified['continuation']} 活跃{classified['active']} 单日{classified['single_day']}")
    return candidates
