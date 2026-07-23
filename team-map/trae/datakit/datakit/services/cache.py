"""Parquet cache for K-line and block index data.

Provides read/write with TTL, warm(), purge(), and status().
"""

import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from datakit.core.types import ProvenanceEntry, RawRecord

try:
    import pyarrow as pa
    import pyarrow.parquet as pq
    HAS_PYARROW = True
except ImportError:
    HAS_PYARROW = False


CACHE_DIR = Path(__file__).resolve().parent.parent / "cache"

# Default TTLs
DEFAULT_TTL = {
    "kline_daily": timedelta(days=1),
    "block_index": timedelta(hours=1),
    "raw_record": timedelta(days=1),
}

_hits = 0
_misses = 0


def _parse_ttl(ttl_str: str) -> timedelta:
    """Parse TTL string like '1d', '12h', '30m', '0s'."""
    ttl_str = ttl_str.strip()
    if ttl_str.endswith("d"):
        return timedelta(days=int(ttl_str[:-1]))
    elif ttl_str.endswith("h"):
        return timedelta(hours=int(ttl_str[:-1]))
    elif ttl_str.endswith("m"):
        return timedelta(minutes=int(ttl_str[:-1]))
    return timedelta(seconds=0)


def _load_config_ttls() -> dict[str, timedelta]:
    """Load TTL config from datakit/config.yaml if available."""
    ttls = dict(DEFAULT_TTL)
    try:
        import yaml
        config_path = Path(__file__).resolve().parent.parent / "config.yaml"
        if config_path.exists():
            with open(config_path) as f:
                config = yaml.safe_load(f) or {}
            for key, val in config.get("cache", {}).get("ttl", {}).items():
                ttls[key] = _parse_ttl(str(val))
    except Exception:
        pass
    return ttls


def _cache_path(data_type: str, key: str) -> Path:
    """Get cache file path for a data type and key."""
    return CACHE_DIR / data_type / f"{key}.parquet"



def _raw_record_to_dict(record: RawRecord) -> dict:
    return {
        "symbol": record.symbol,
        "source": record.source,
        "transport": record.transport,
        "payload": json.dumps(record.payload, ensure_ascii=False, default=str),
        "ingest_ts": record.ingest_ts,
        "source_timestamp": json.dumps(record.source_timestamp, ensure_ascii=False, default=str),
        "network_latency_ms": record.network_latency_ms,
        "raw_size_bytes": record.raw_size_bytes,
    }


def _dict_to_raw_record(row: dict) -> RawRecord:
    payload = row.get("payload")
    source_timestamp = row.get("source_timestamp")
    try:
        payload = json.loads(payload) if isinstance(payload, str) else payload
    except Exception:
        pass
    try:
        source_timestamp = json.loads(source_timestamp) if isinstance(source_timestamp, str) else source_timestamp
    except Exception:
        pass
    return RawRecord(
        symbol=str(row.get("symbol", "")),
        source=str(row.get("source", "")),
        transport=str(row.get("transport", "")),
        payload=payload,
        ingest_ts=float(row.get("ingest_ts", 0) or 0),
        source_timestamp=source_timestamp,
        network_latency_ms=row.get("network_latency_ms"),
        raw_size_bytes=int(row.get("raw_size_bytes", 0) or 0),
    )


def _provenance_to_json(entries) -> str:
    return json.dumps([entry.__dict__ for entry in entries], ensure_ascii=False, default=str)


def _provenance_from_json(value) -> frozenset[ProvenanceEntry]:
    if not value:
        return frozenset()
    if isinstance(value, list):
        items = value
    else:
        items = json.loads(value)
    return frozenset(ProvenanceEntry(**item) for item in items)

def read_parquet(data_type: str, key: str) -> tuple[Any | None, bool]:
    """Read from Parquet cache. Returns (data, is_fresh).
    If not fresh, returns (data, False) — caller decides what to do.
    """
    global _misses, _hits
    if not HAS_PYARROW:
        _misses += 1
        return None, False

    path = _cache_path(data_type, key)
    if not path.exists():
        _misses += 1
        return None, False

    ttls = _load_config_ttls()
    ttl = ttls.get(data_type, timedelta(hours=1))
    mtime = datetime.fromtimestamp(path.stat().st_mtime)
    is_fresh = (datetime.now() - mtime) < ttl

    try:
        table = pq.read_table(str(path))
        data = table.to_pydict()
        if "_provenance" in data:
            cache_entry = ProvenanceEntry(
                step="cache_hit",
                actor="datakit.cache",
                timestamp=time.time(),
                detail=str(path),
            )
            data["_provenance"] = [
                _provenance_from_json(value) | frozenset([cache_entry])
                for value in data["_provenance"]
            ]
        if is_fresh:
            _hits += 1
        else:
            _misses += 1
        return data, is_fresh
    except Exception:
        _misses += 1
        return None, False


def write_parquet(data_type: str, key: str, records: list[dict]) -> None:
    """Write records to Parquet cache."""
    if not HAS_PYARROW:
        return
    if not records:
        return
    path = _cache_path(data_type, key)
    path.parent.mkdir(parents=True, exist_ok=True)
    prepared = []
    for record in records:
        item = dict(record)
        if "_provenance" in item and not isinstance(item["_provenance"], str):
            item["_provenance"] = _provenance_to_json(item["_provenance"])
        prepared.append(item)
    table = pa.Table.from_pylist(prepared)
    pq.write_table(table, str(path))


def write_raw(key: str, records: list[RawRecord]) -> None:
    """Write RawRecord entries under cache/raw."""
    write_parquet("raw", key, [_raw_record_to_dict(record) for record in records])


def read_raw(key: str) -> tuple[dict[str, RawRecord] | None, bool]:
    """Read RawRecord entries from cache/raw."""
    data, fresh = read_parquet("raw", key)
    if not data:
        return None, fresh
    rows = []
    keys = list(data)
    count = len(data[keys[0]]) if keys else 0
    for index in range(count):
        rows.append({key: data[key][index] for key in keys})
    return {row["symbol"]: _dict_to_raw_record(row) for row in rows}, fresh


async def warm(symbols: list[str] | None = None) -> dict:
    """Pre-fetch and cache K-lines for tracked symbols.

    If symbols is None or 'all', loads from the project's stock CSV.
    """
    if not HAS_PYARROW:
        return {"warmed": 0, "errors": 0, "duration_ms": 0, "note": "pyarrow not installed"}

    import asyncio
    from datakit.core.registry import get

    if symbols is None or symbols == ["all"]:
        # Load from project stock CSV
        try:
            import csv
            csv_path = Path(__file__).resolve().parent.parent.parent / "data" / "static" / "all_stocks_20260306.csv"
            if csv_path.exists():
                symbols = []
                with open(csv_path, encoding="utf-8") as f:
                    for row in csv.DictReader(f):
                        code = row.get("code", "").strip()
                        name = row.get("code_name", "").strip()
                        if any(kw in name for kw in ("指数", "B股", "基金", "债券")):
                            continue
                        if code.startswith("sh.60"):
                            symbols.append(f"{code[3:]}.SH")
                        elif code.startswith("sz.00"):
                            symbols.append(f"{code[3:]}.SZ")
        except Exception:
            symbols = []

    if not symbols:
        return {"warmed": 0, "errors": 0, "duration_ms": 0, "note": "no symbols found"}

    started = time.time()
    warmed = 0
    errors = 0

    try:
        adapter = get("tickflow")
        # Fetch in batches
        batch_size = 100
        for i in range(0, len(symbols), batch_size):
            batch = symbols[i:i + batch_size]
            try:
                result = await adapter.fetch_klines(batch, days=2)
                normalized, _raw = result if isinstance(result, tuple) else (result, {})
                for _sym, bars in normalized.items():
                    records = [{
                        "symbol": b.symbol,
                        "date": b.date,
                        "open": b.open,
                        "high": b.high,
                        "low": b.low,
                        "close": b.close,
                        "volume": b.volume,
                        "amount": b.amount,
                    } for b in bars]
                    if records:
                        # Cache by date
                        date = records[0]["date"]
                        write_parquet("kline_daily", date, records)
                        warmed += 1
            except Exception:
                errors += 1
    except Exception:
        pass

    elapsed = round((time.time() - started) * 1000)
    return {"warmed": warmed, "errors": errors, "duration_ms": elapsed}


def purge(older_than_days: int = 7) -> dict:
    """Delete cache entries older than N days."""
    cutoff = time.time() - (older_than_days * 86400)
    deleted = 0
    freed = 0
    for root, _dirs, files in os.walk(CACHE_DIR):
        for f in files:
            fpath = Path(root) / f
            if fpath.stat().st_mtime < cutoff:
                size = fpath.stat().st_size
                fpath.unlink()
                deleted += 1
                freed += size
    return {"deleted_files": deleted, "freed_bytes": freed}


def _dir_stats(path: Path) -> dict:
    total_size = 0
    file_count = 0
    oldest = None
    newest = None
    for root, _dirs, files in os.walk(path):
        for f in files:
            fpath = Path(root) / f
            st = fpath.stat()
            total_size += st.st_size
            file_count += 1
            mtime = datetime.fromtimestamp(st.st_mtime)
            if oldest is None or mtime < oldest:
                oldest = mtime
            if newest is None or mtime > newest:
                newest = mtime
    return {
        "total_size_bytes": total_size,
        "file_count": file_count,
        "oldest_entry": oldest.isoformat() if oldest else None,
        "newest_entry": newest.isoformat() if newest else None,
    }


def raw_stats() -> dict:
    """Return raw cache file statistics."""
    raw_dir = CACHE_DIR / "raw"
    stats = _dir_stats(raw_dir)
    by_source = {}
    by_date = {}
    for path in raw_dir.glob("*.parquet") if raw_dir.exists() else []:
        parts = path.stem.split("_")
        source = parts[0] if parts else "unknown"
        date = parts[1] if len(parts) > 1 else datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d")
        by_source.setdefault(source, {"files": 0, "size_bytes": 0})
        by_source[source]["files"] += 1
        by_source[source]["size_bytes"] += path.stat().st_size
        by_date.setdefault(date, {"files": 0, "size_bytes": 0})
        by_date[date]["files"] += 1
        by_date[date]["size_bytes"] += path.stat().st_size
    stats.update({"total_files": stats["file_count"], "by_source": by_source, "by_date": by_date})
    return stats


def status() -> dict:
    """Get cache statistics."""
    total_requests = _hits + _misses
    hit_rate = (_hits / total_requests * 100) if total_requests > 0 else 0.0
    normalized = _dir_stats(CACHE_DIR)
    raw = raw_stats()
    normalized["hit_rate_pct"] = round(hit_rate, 1)
    normalized["hits"] = _hits
    normalized["misses"] = _misses
    return {
        **normalized,
        "normalized_cache": normalized,
        "raw_cache": raw,
    }
