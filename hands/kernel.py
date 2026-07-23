#!/usr/bin/env python3
"""归零重构：T-1 review → T日竞价 → D1证据连接。"""
import argparse
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

CST = timezone(timedelta(hours=8))
ROOT = Path(__file__).resolve().parent


def load(path: Path):
    return json.loads(path.read_text())


def dump(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    tmp.replace(path)


def dense_zone(prices, volumes, coverage=0.60):
    pairs = [(round(float(p), 2), float(v)) for p, v in zip(prices, volumes) if float(p) > 0 and float(v) > 0]
    if not pairs:
        return None
    by_price = {}
    for price, volume in pairs:
        by_price[price] = by_price.get(price, 0.0) + volume
    levels = sorted(by_price)
    target = sum(by_price.values()) * coverage
    best = None
    for left in range(len(levels)):
        total = 0.0
        for right in range(left, len(levels)):
            total += by_price[levels[right]]
            if total >= target:
                candidate = (levels[right] - levels[left], levels[left], levels[right], total)
                if best is None or candidate < best:
                    best = candidate
                break
    if best is None:
        return None
    return {"low": best[1], "high": best[2], "covered_volume": round(best[3]), "coverage": coverage}


def build_review(date, pool_path, minute_dir, out_path):
    pool = load(Path(pool_path))
    rows = {}
    errors = []
    for stock in pool.get("limit_up_stocks", []):
        symbol = stock["symbol"]
        minute_path = Path(minute_dir) / f"{symbol}.json"
        if not minute_path.exists():
            errors.append({"symbol": symbol, "reason": "minute_missing"})
            continue
        minute = load(minute_path)
        if minute.get("target_date") != date:
            errors.append({"symbol": symbol, "reason": "minute_date_mismatch", "actual": minute.get("target_date")})
            continue
        data = minute.get("data", {})
        timestamps = data.get("timestamp", [])
        closes = data.get("close", [])
        lows = data.get("low", [])
        highs = data.get("high", [])
        volumes = data.get("volume", [])
        amounts = data.get("amount", [])
        n = min(map(len, [timestamps, closes, lows, highs, volumes, amounts])) if timestamps else 0
        if n == 0:
            errors.append({"symbol": symbol, "reason": "minute_empty"})
            continue
        raw_volume = sum(float(x) for x in volumes[:n])
        total_amount = sum(float(x) for x in amounts[:n])
        close_reference = float(stock.get("close_t1") or closes[n - 1] or 0)
        raw_vwap = total_amount / raw_volume if raw_volume else 0
        # TickFlow分钟K volume在当前历史产物中以“手”计，amount以“元”计；
        # 用价格量纲识别后统一成“股”，使其可与T日竞价volume直接对照。
        volume_multiplier = 100 if close_reference and raw_vwap / close_reference > 20 else 1
        total_volume = raw_volume * volume_multiplier
        vwap = total_amount / total_volume if total_volume else 0
        iw = stock.get("sources", {}).get("iwencai", {})
        em = stock.get("sources", {}).get("eastmoney", {})
        rows[symbol] = {
            "identity": {"symbol": symbol, "name": stock.get("name", "")},
            "price_space": {
                "close": stock.get("close_t1"),
                "previous_close": stock.get("prev_close"),
                "low": round(min(float(x) for x in lows[:n]), 2),
                "high": round(max(float(x) for x in highs[:n]), 2),
                "vwap": round(vwap, 4),
                "dense_zone": dense_zone(closes[:n], volumes[:n]),
            },
            "participation": {
                "day_volume": round(total_volume),
                "day_amount": round(total_amount, 2),
                "minute_observations": n,
                "source_volume_unit": "手" if volume_multiplier == 100 else "股",
                "normalized_volume_unit": "股",
                "volume_multiplier": volume_multiplier,
            },
            "time_path": {
                "first_bar": datetime.fromtimestamp(timestamps[0] / 1000, CST).isoformat(),
                "last_bar": datetime.fromtimestamp(timestamps[n-1] / 1000, CST).isoformat(),
                "first_limit_time": iw.get("first_limit_time") or em.get("first_limit_time"),
                "final_limit_time": iw.get("final_limit_time") or em.get("final_limit_time"),
                "limit_open_count": iw.get("limit_open_count") if iw.get("limit_open_count") is not None else em.get("open_count"),
            },
            "theme_facts": {
                "reason": iw.get("reason"),
                "industry": em.get("industry"),
                "board_days": iw.get("board_days"),
                "sealed_fund": em.get("sealed_fund"),
            },
            "provenance": {
                "pool_date": pool.get("meta", {}).get("date"),
                "pool_source": pool.get("meta", {}).get("source_mode"),
                "minute_file": str(minute_path),
                "minute_source": minute.get("source"),
            },
        }
    result = {
        "meta": {"kind": "t_minus_1_review", "date": date, "input": len(pool.get("limit_up_stocks", [])), "reviewed": len(rows), "errors": len(errors), "ready": not errors and bool(rows)},
        "symbols": rows,
        "errors": errors,
    }
    dump(Path(out_path), result)
    return result


def snapshot_to_trajectory(date, snapshot_path, out_path):
    snapshot = load(Path(snapshot_path))
    observed = f"{date}T{snapshot.get('meta', {}).get('time', '09:25:00')}+08:00"
    rows = []
    for symbol, q in snapshot.get("quotes", {}).items():
        price = float(q.get("open") or 0)
        raw_volume = float(q.get("volume") or 0)
        amount = float(q.get("amount") or 0)
        implied_multiplier = amount / (price * raw_volume) if price and raw_volume else 1
        # 当前历史产物：WS volume以“手”计，iWencai volume以“股”计。
        # 以量价额关系统一成“股”，不依赖来源名称硬编码。
        volume_multiplier = 100 if 80 <= implied_multiplier <= 120 else 1
        rows.append({
            "symbol": symbol,
            "observed_at": observed,
            "source": snapshot.get("meta", {}).get("mode"),
            "price": price,
            "volume": raw_volume * volume_multiplier,
            "amount": amount,
            "previous_close": q.get("prev_close"),
            "source_volume": raw_volume,
            "source_volume_unit": "手" if volume_multiplier == 100 else "股",
            "normalized_volume_unit": "股",
            "volume_multiplier": volume_multiplier,
        })
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))
    return {"date": date, "observations": len(rows), "warning": "历史输入只有09:25快照；可验证连接，不能证明时间维度"}


def read_trajectory(path):
    grouped = {}
    for line in Path(path).read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        grouped.setdefault(row["symbol"], []).append(row)
    for rows in grouped.values():
        rows.sort(key=lambda x: x["observed_at"])
    return grouped


def pct(a, b):
    return round((a / b - 1) * 100, 2) if a and b else None


def build_d1(run_date, review_path, trajectory_path, out_path):
    review = load(Path(review_path))
    trajectory = read_trajectory(trajectory_path)
    records = []
    missing_review = []
    for symbol, observations in trajectory.items():
        base = review.get("symbols", {}).get(symbol)
        if base is None:
            missing_review.append(symbol)
            continue
        first, last = observations[0], observations[-1]
        price = float(last.get("price") or 0)
        volume = float(last.get("volume") or 0)
        amount = float(last.get("amount") or 0)
        ps = base["price_space"]
        participation = base["participation"]
        theme = base["theme_facts"]
        records.append({
            "identity": base["identity"],
            "price_result": {
                "auction_price": price,
                "vs_t1_close_pct": pct(price, ps.get("close")),
                "vs_t1_vwap_pct": pct(price, ps.get("vwap")),
                "t1_dense_zone": ps.get("dense_zone"),
            },
            "volume_commitment": {
                "auction_volume": volume,
                "auction_amount": amount,
                "vs_t1_day_volume_pct": round(volume / participation["day_volume"] * 100, 2) if participation.get("day_volume") else None,
                "vs_t1_day_amount_pct": round(amount / participation["day_amount"] * 100, 2) if participation.get("day_amount") else None,
            },
            "time_evidence": {
                "observations": len(observations),
                "first": first["observed_at"],
                "last": last["observed_at"],
                "price_change": round(price - float(first.get("price") or 0), 4),
                "volume_change": round(volume - float(first.get("volume") or 0), 2),
                "has_process_evidence": len(observations) > 1,
            },
            "space": {
                "self": {"t1_low": ps.get("low"), "t1_high": ps.get("high"), "t1_vwap": ps.get("vwap")},
                "market": {"theme_peer_position": None, "status": "需要同题材T日观测后计算"},
            },
            "theme_facts": theme,
            "consumption": {
                "review_date": review.get("meta", {}).get("date"),
                "review_fields": ["price_space", "participation", "time_path", "theme_facts"],
                "auction_observations": len(observations),
                "trajectory_file": str(Path(trajectory_path)),
            },
        })
    result = {
        "meta": {
            "kind": "d1_evidence",
            "run_date": run_date,
            "review_date": review.get("meta", {}).get("date"),
            "trajectory_symbols": len(trajectory),
            "joined": len(records),
            "missing_review": len(missing_review),
            "time_dimension_ready": bool(records) and all(x["time_evidence"]["has_process_evidence"] for x in records),
            "ranking": "not_defined",
        },
        "records": records,
        "missing_review_symbols": missing_review,
    }
    dump(Path(out_path), result)
    return result


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("review")
    r.add_argument("date"); r.add_argument("--pool", required=True); r.add_argument("--minute-dir", required=True); r.add_argument("--out", required=True)
    a = sub.add_parser("snapshot-trajectory")
    a.add_argument("date"); a.add_argument("--snapshot", required=True); a.add_argument("--out", required=True)
    d = sub.add_parser("d1")
    d.add_argument("date"); d.add_argument("--review", required=True); d.add_argument("--trajectory", required=True); d.add_argument("--out", required=True)
    x = p.parse_args()
    if x.cmd == "review": result = build_review(x.date, x.pool, x.minute_dir, x.out)
    elif x.cmd == "snapshot-trajectory": result = snapshot_to_trajectory(x.date, x.snapshot, x.out)
    else: result = build_d1(x.date, x.review, x.trajectory, x.out)
    print(json.dumps(result.get("meta", result), ensure_ascii=False))


if __name__ == "__main__":
    main()
