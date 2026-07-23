"""
筹码供需分析 — Order Book Supply-Demand

买卖盘挂单分布检测 (WS-dependent).
计算买盘集中度、卖盘集中度、供需比率。
识别供给端压单和自成交对倒。

WS不可用时: 所有标的标记 orderbook: "unknown" (不静默跳过)
"""


def apply_orderbook(candidates: list[dict], depth_data: dict | None = None) -> list[dict]:
    """
    筹码供需分析。
    
    Args:
        candidates: 候选标的列表
        depth_data: WS挂单簿数据 {symbol: {bids: [[price,vol],...], asks: [[price,vol],...]}}
                   None when WS unavailable
    
    When WS unavailable: marks all orderbook: "unknown" with degradation notice.
    """
    if not candidates:
        return candidates

    # Task 6.6: WS unavailable → degradation
    if depth_data is None:
        print(f"  [orderbook] ⚠️ WS不可用 → 全部标记 orderbook: unknown (筹码供需层不可用)")
        for c in candidates:
            c['marks']['orderbook'] = "unknown"
        return candidates

    supply_pressure_count = 0
    single_cp_count = 0
    balanced_count = 0

    for c in candidates:
        sym = c['symbol']
        depth = depth_data.get(sym, {})

        bids = depth.get('bids', [])  # [[price, volume], ...]
        asks = depth.get('asks', [])  # [[price, volume], ...]

        if not bids or not asks:
            c['marks']['orderbook'] = "unknown"
            continue

        # Task 6.2: buy concentration (top 3 bid levels / total bids)
        total_bids = sum(vol for _, vol in bids)
        top3_bids = sum(vol for _, vol in sorted(bids, key=lambda x: x[0], reverse=True)[:3])

        # Task 6.3: sell concentration (top 3 ask levels / total asks)
        total_asks = sum(vol for _, vol in asks)
        top3_asks = sum(vol for _, vol in sorted(asks, key=lambda x: x[0])[:3])

        buy_conc = top3_bids / max(total_bids, 1)
        sell_conc = top3_asks / max(total_asks, 1)

        # Task 6.4: supply-demand ratio (total bids / total asks)
        sd_ratio = total_bids / max(total_asks, 1)

        # Task 6.5: classification per spec
        if sd_ratio < 0.3:
            c['marks']['orderbook'] = "supply_pressure"
            c['marks']['orderbook_detail'] = f"供需比{sd_ratio:.2f}(卖超{1/sd_ratio:.1f}倍)"
            supply_pressure_count += 1
        elif buy_conc > 0.8 and sell_conc > 0.8:
            c['marks']['orderbook'] = "single_counterparty"
            c['marks']['orderbook_detail'] = f"买集{buy_conc:.0%}+卖集{sell_conc:.0%}(疑对倒)"
            single_cp_count += 1
        else:
            c['marks']['orderbook'] = "balanced"
            c['marks']['orderbook_detail'] = f"供需比{sd_ratio:.2f}"
            balanced_count += 1

    print(f"  [orderbook] 检测: balanced={balanced_count} supply_pressure={supply_pressure_count} single_counterparty={single_cp_count}")
    return candidates
