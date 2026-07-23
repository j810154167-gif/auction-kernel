from dataclasses import FrozenInstanceError

import pytest

from datakit.core.channel import ChannelManager
from datakit.core.provenance import ProvenanceBuilder
from datakit.core.types import Quote, RawRecord


def _quote():
    return Quote(
        symbol="000001",
        name="Ping An",
        last_price=12.3,
        open=12.0,
        high=12.5,
        low=11.9,
        volume=100,
        amount=1230.0,
        prev_close=12.1,
        change_pct=1.65,
        timestamp_ms=123000,
        source="tickflow",
        _ingest_ts=123.456,
    )


def test_channel_manager_constructs_raw_record_with_encoded_payload_size():
    manager = ChannelManager(clock=lambda: 123.456)

    record = manager.raw_record(
        symbol="000001",
        source="tickflow",
        transport="rest",
        payload={"price": "平安"},
        source_timestamp=123000,
        network_latency_ms=8.5,
    )

    assert isinstance(record, RawRecord)
    assert record.ingest_ts == 123.456
    assert record.raw_size_bytes == len('{"price":"平安"}'.encode("utf-8"))


def test_channel_manager_attaches_provenance_without_mutating_frozen_record():
    manager = ChannelManager()
    quote = _quote()
    entry = manager.provenance_entry("normalize", "datakit.normalizer", "quote")

    normalized, chain = manager.attach_provenance(quote, [entry])

    assert normalized is not quote
    assert normalized._provenance == frozenset((entry,))
    assert chain == [entry]
    assert quote._provenance == frozenset()


def test_provenance_builder_stamps_named_processing_steps():
    with ProvenanceBuilder(clock=lambda: 123.456) as builder:
        builder.source_fetch("tickflow", "REST response")
        builder.normalize("datakit.normalizer", "Quote")
        builder.failover("datakit.router", "tickflow → eastmoney")

    assert [entry.step for entry in builder.entries] == [
        "source_fetch",
        "normalize",
        "failover",
    ]
    assert all(entry.timestamp == 123.456 for entry in builder.entries)
    with pytest.raises(FrozenInstanceError):
        builder.entries[0].detail = "changed"
