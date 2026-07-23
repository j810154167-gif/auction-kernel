"""
风险赔率计算 — Risk Odds

上行空间(天花板距离) vs 下行空间(VWAP底距离) 的不对称赔率标记。
数据源: 前日K线 + 竞价价 (REST可用, 非WS依赖)
"""


def apply_risk_odds(candidates: list[dict]) -> list[dict]:
    """
    风险赔率计算。
    
    Task 7.1: Compute upside (distance to daily limit ceiling)
    and downside (distance to VWAP floor).
    Task 7.2: Mark asymmetric when upside / max(downside, 0.01) < 0.3
    Task 7.3: Attach marks.risk_odds with detail.
    """
    if not candidates:
        return candidates

    asymmetric_count = 0
    balanced_count = 0

    for c in candidates:
        auction_price = c.get('auction_price', 0)
        vwap_ceiling = c.get('vwap_ceiling', 0)
        vwap_floor = c.get('vwap_floor', 0)

        if auction_price <= 0:
            c['marks']['risk_odds'] = "unknown"
            c['marks']['risk_odds_detail'] = "无竞价价"
            continue

        # Task 7.1: upside = distance from auction price to ceiling
        upside_pct = 0
        if vwap_ceiling > auction_price:
            upside_pct = (vwap_ceiling - auction_price) / auction_price * 100
        elif vwap_ceiling > 0:
            upside_pct = 0  # already at or above ceiling

        # Task 7.1: downside = distance from auction price to VWAP floor
        downside_pct = 0
        if auction_price > vwap_floor and vwap_floor > 0:
            downside_pct = (auction_price - vwap_floor) / auction_price * 100
        elif vwap_floor > 0:
            downside_pct = 0  # at or below floor

        # Task 7.2: asymmetric check
        upside_ratio = upside_pct / max(downside_pct, 0.01)

        if upside_ratio < 0.3:
            c['marks']['risk_odds'] = "asymmetric"
            c['marks']['risk_odds_detail'] = f"上行{upside_pct:+.1f}% 下行{downside_pct:+.1f}% (赔率不对等)"
            asymmetric_count += 1
        elif upside_pct > 3.0 and downside_pct < 5.0:
            c['marks']['risk_odds'] = "balanced"
            c['marks']['risk_odds_detail'] = f"上行{upside_pct:+.1f}% 下行{downside_pct:+.1f}%"
            balanced_count += 1
        else:
            c['marks']['risk_odds'] = "neutral"
            c['marks']['risk_odds_detail'] = f"上行{upside_pct:+.1f}% 下行{downside_pct:+.1f}%"

    print(f"  [risk_odds] 赔率: balanced={balanced_count} asymmetric={asymmetric_count} neutral={len(candidates)-asymmetric_count-balanced_count}")
    return candidates
