"""
题材前置筛选 — Sector-first Filter

活跃板块 Top3 → 只在板块内选候选标的。
无题材支撑的涨停不进监控池。
数据源: Eastmoney (via datakit)
"""

import asyncio

EASTMONEY_BASE = "https://push2delay.eastmoney.com"


async def _fetch_active_sectors_async(min_turnover_ratio: float = 2.0) -> list[dict]:
    """Pull industry blocks from Eastmoney, return top 3 by momentum."""
    from datakit.adapters.eastmoney import EastmoneyAdapter

    adapter = EastmoneyAdapter()
    try:
        blocks = await adapter.fetch_blocks(category="industry")
    except Exception:
        blocks = []
    try:
        concept_blocks = await adapter.fetch_blocks(category="concept")
        blocks.extend(concept_blocks)
    except Exception:
        pass

    if not blocks:
        return []

    blocks.sort(key=lambda b: b.change_pct, reverse=True)

    active = []
    for b in blocks[:10]:
        active.append({
            "name": b.name,
            "category": b.category,
            "change_pct": round(b.change_pct, 2),
            "members": list(b.members) if b.members else [],
        })
        if len(active) >= 3:
            break

    return active


async def _get_sector_stocks_async(block_name: str) -> list[str]:
    """Get stock symbols belonging to a sector block."""
    import urllib.parse
    from datakit.adapters.eastmoney import EastmoneyAdapter
    adapter = EastmoneyAdapter()

    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1", "pz": "500",
        "po": "0", "np": "1",
        "fltt": "2", "invt": "2",
        "fid": "f3",
        "fs": "b:" + block_name,
        "fields": "f12,f14",
    }
    full_url = url + "?" + urllib.parse.urlencode(params)
    try:
        data = adapter._get_json(full_url)
        items = data.get("data", {}).get("diff", [])
        symbols = []
        for item in items:
            em_code = item.get("f12", "")
            sym = adapter._em_to_tf_symbol(em_code)
            symbols.append(sym)
        return symbols
    except Exception:
        return []


def apply_sector_filter(candidates: list[dict]) -> list[dict]:
    """
    题材前置筛选。
    
    Pull Top 3 active sectors, attach marks.sector to each candidate
    that belongs to an active sector. Others get sector: "unknown".
    """
    try:
        active_sectors = asyncio.run(_fetch_active_sectors_async())
    except Exception as e:
        print("  [sector_filter] Eastmoney不可用:", e)
        active_sectors = []

    if not active_sectors:
        for c in candidates:
            c["marks"]["sector"] = "unknown"
        print("  [sector_filter] 无活跃板块 → 全量标记 sector: unknown (降级)")
        return candidates

    # Build sector→stocks mapping
    sector_stocks = {}
    for sector in active_sectors:
        sector_name = sector["name"]
        stocks = asyncio.run(_get_sector_stocks_async(sector_name))
        if stocks:
            sector_stocks[sector_name] = set(stocks)

    # Tag each candidate
    names = [s["name"] for s in active_sectors]
    changes = [s["change_pct"] for s in active_sectors]
    sector_desc = ", ".join(f"{n}({c:+.2f}%)" for n, c in zip(names, changes))
    print(f"  [sector_filter] 活跃板块Top3: {sector_desc}")

    tagged_count = 0
    for c in candidates:
        sym = c["symbol"]
        found = False
        for sector_name, stocks in sector_stocks.items():
            if sym in stocks:
                c["marks"]["sector"] = sector_name
                found = True
                tagged_count += 1
                break
        if not found:
            c["marks"]["sector"] = "unknown"

    print(f"  [sector_filter] {tagged_count}/{len(candidates)} 归入活跃板块, {len(candidates)-tagged_count} 标记unknown")
    return candidates
