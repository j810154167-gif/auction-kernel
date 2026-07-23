from dataclasses import FrozenInstanceError
from datetime import time

import pytest

from datakit.core.types import (
    AnchorPoint,
    BlockInfo,
    ConsumptionIntent,
    FetchResult,
    Kline,
    ProvenanceEntry,
    Quote,
    RawRecord,
)


def test_raw_record_is_frozen_and_preserves_adapter_payload():
    payload = {"price": 12.3}
    record = RawRecord(
        symbol="000001",
        source="tickflow",
        transport="rest",
        payload=payload,
        ingest_ts=123.456,
        source_timestamp=123000,
        network_latency_ms=8.5,
        raw_size_bytes=15,
    )

    assert record.payload is payload
    with pytest.raises(FrozenInstanceError):
        record.source = "eastmoney"


def test_provenance_entry_is_frozen_and_hashable():
    entry = ProvenanceEntry("source_fetch", "tickflow", 123.456, "REST response")

    assert frozenset((entry, entry)) == frozenset((entry,))
    with pytest.raises(FrozenInstanceError):
        entry.step = "normalize"


def test_consumption_intent_uses_cli_compatible_values():
    assert [intent.value for intent in ConsumptionIntent] == [
        "realtime-decision",
        "backtest",
        "audit",
        "full-trace",
    ]


def test_anchor_point_holds_parsed_time_contract():
    anchor = AnchorPoint("T+0", time(9, 15), "Asia/Shanghai")

    assert anchor.time == time(9, 15)


def test_fetch_result_iterates_normalized_by_default():
    result = FetchResult(
        normalized={"000001": "quote"},
        raw={"000001": "raw"},
        provenance={"000001": ["source_fetch"]},
    )

    assert list(result) == ["000001"]


def test_existing_data_models_default_to_empty_provenance():
    quote = Quote(
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
    kline = Kline("000001", "2026-07-10", 12.0, 12.5, 11.9, 12.3, 100, 1230.0, 123.456)
    block = BlockInfo("BK001", "Bank", "industry", 1.2)

    assert quote._provenance == frozenset()
    assert kline._provenance == frozenset()
    assert block._provenance == frozenset()
