"""
反量化博弈识别 — Anti-HFT Detection

竞价最后1分钟轨迹分析 (WS-dependent).
检测: 价位跳升>2%, 成交量集中>60%, 开盘首笔量<竞价累积量30%

WS不可用时: 所有标的标记 anti_hft: "unknown" (不静默跳过)
"""

# WS availability flag — can be set externally to indicate WS state
_ws_available = False


def set_ws_available(available: bool):
    """Set the global WS availability flag."""
    global _ws_available
    _ws_available = available


def is_ws_available() -> bool:
    """Check if WS is currently available."""
    return _ws_available


def apply_anti_hft(candidates: list[dict], ws_data: dict | None = None) -> list[dict]:
    """
    反量化博弈检测。
    
    Args:
        candidates: 候选标的列表
        ws_data: WS竞价轨迹数据 (None when WS unavailable)
    
    When WS unavailable: marks all anti_hft: "unknown" with degradation notice.
    """
    if not candidates:
        return candidates

    # Task 5.6: WS unavailable → degradation
    if not _ws_available and ws_data is None:
        print(f"  [anti_hft] ⚠️ WS不可用 → 全部标记 anti_hft: unknown (反量化防御层不可用)")
        for c in candidates:
            c['marks']['anti_hft'] = "unknown"
        return candidates

    if ws_data is None:
        print(f"  [anti_hft] ⚠️ WS数据为空 → 全部标记 anti_hft: unknown")
        for c in candidates:
            c['marks']['anti_hft'] = "unknown"
        return candidates

    suspicious_count = 0
    confirmed_count = 0

    for c in candidates:
        sym = c['symbol']
        tick_data = ws_data.get(sym, {})

        if not tick_data:
            c['marks']['anti_hft'] = "unknown"
            continue

        # Task 5.2: price jump > 2% in last 60s
        price_jump = tick_data.get('last_60s_price_jump_pct', 0)

        # Task 5.3: volume concentration > 60% in last 60s
        vol_conc = tick_data.get('last_60s_volume_ratio', 0)

        # Task 5.4: opening first-trade volume < 30% of auction accumulated
        opening_vol_ratio = tick_data.get('opening_vol_ratio', 1.0)

        # Task 5.5: classification
        if price_jump > 2.0 and vol_conc > 0.6:
            if opening_vol_ratio < 0.3:
                c['marks']['anti_hft'] = "confirmed"
                c['marks']['anti_hft_detail'] = f"价跳{price_jump:.1f}%+量集{vol_conc:.0%}+首笔{opening_vol_ratio:.0%}"
                confirmed_count += 1
            else:
                c['marks']['anti_hft'] = "suspicious"
                c['marks']['anti_hft_detail'] = f"价跳{price_jump:.1f}%+量集{vol_conc:.0%}"
                suspicious_count += 1
        elif price_jump > 2.0:
            c['marks']['anti_hft'] = "suspicious"
            c['marks']['anti_hft_detail'] = f"价跳{price_jump:.1f}%"
            suspicious_count += 1
        elif vol_conc > 0.6:
            c['marks']['anti_hft'] = "suspicious"
            c['marks']['anti_hft_detail'] = f"量集{vol_conc:.0%}"
            suspicious_count += 1
        else:
            c['marks']['anti_hft'] = "clean"
            c['marks']['anti_hft_detail'] = "未检测到异常"

    print(f"  [anti_hft] 检测: clean={len(candidates)-suspicious_count-confirmed_count} suspicious={suspicious_count} confirmed={confirmed_count}")
    return candidates
