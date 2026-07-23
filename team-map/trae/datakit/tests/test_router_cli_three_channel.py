import asyncio
from dataclasses import replace

from datakit.core.engine import Router
from datakit.core.types import ConsumptionIntent, FetchResult, Quote, RawRecord, ProvenanceEntry


class FakeAdapter:
    name = "fake"

    async def fetch_quotes(self, symbols):
        raw = {}
        normalized = {}
        for symbol in symbols:
            raw[symbol] = RawRecord(symbol, "fake", "rest", {"symbol": symbol}, 1.0, None, 2.0, 18)
            normalized[symbol] = Quote(symbol, "n", 1, 1, 1, 1, 1, 1, 1, 0, 123, "fake", 1.0)
        return normalized, raw


def test_router_returns_fetch_result_with_intent_channels(monkeypatch, tmp_path):
    config = tmp_path / "config.yaml"
    config.write_text("fallback:\n  quote: [fake]\n", encoding="utf-8")

    monkeypatch.setattr("datakit.core.engine.get", lambda name: FakeAdapter())
    monkeypatch.setattr("datakit.core.engine.db.is_quota_exhausted", lambda source: False)
    monkeypatch.setattr("datakit.core.engine.db.upsert_quota", lambda *args, **kwargs: None)

    router = Router(config)
    result = asyncio.run(router.quote(["000001"], intent=ConsumptionIntent.AUDIT))

    assert isinstance(result, FetchResult)
    assert result.normalized["000001"].last_price == 1
    assert result.raw["000001"].payload == {"symbol": "000001"}
    assert result.provenance["000001"]
    assert {entry.step for entry in result.provenance["000001"]} >= {"source_fetch", "normalize", "router_select"}


def test_router_backtest_omits_raw_and_provenance(monkeypatch, tmp_path):
    config = tmp_path / "config.yaml"
    config.write_text("fallback:\n  quote: [fake]\n", encoding="utf-8")

    monkeypatch.setattr("datakit.core.engine.get", lambda name: FakeAdapter())
    monkeypatch.setattr("datakit.core.engine.db.is_quota_exhausted", lambda source: False)
    monkeypatch.setattr("datakit.core.engine.db.upsert_quota", lambda *args, **kwargs: None)

    result = asyncio.run(Router(config).quote(["000001"], intent="backtest"))

    assert result.normalized["000001"].symbol == "000001"
    assert result.raw == {}
    assert result.provenance == {}
