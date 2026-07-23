from datakit.core.types import ProvenanceEntry, RawRecord
from datakit.services import cache


def test_provenance_serializes_and_appends_cache_hit(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    if not cache.HAS_PYARROW:
        return

    original = ProvenanceEntry("source_fetch", "test", 1.0, "ok")
    cache.write_parquet("quote_snapshot", "sample", [{"symbol": "000001", "_provenance": frozenset([original])}])

    data, fresh = cache.read_parquet("quote_snapshot", "sample")

    assert fresh is False  # quote_snapshot has 0s TTL by design
    steps = {entry.step for entry in data["_provenance"][0]}
    assert {"source_fetch", "cache_hit"} <= steps


def test_raw_record_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    if not cache.HAS_PYARROW:
        return

    record = RawRecord("000001", "test", "rest", {"x": 1}, 1.0, None, 2.0, 8)
    cache.write_raw("sample", [record])

    data, fresh = cache.read_raw("sample")

    assert fresh is True
    assert data["000001"].payload == {"x": 1}
    assert data["000001"].network_latency_ms == 2.0
