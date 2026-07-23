"""Helpers for constructing raw and provenance channel records."""

from dataclasses import replace
import json
import time
from typing import Any, Callable, Iterable

from datakit.core.types import ProvenanceEntry, RawRecord


class ChannelManager:
    """Construct and attach three-channel records during normalization."""

    def __init__(self, clock: Callable[[], float] = time.time):
        self._clock = clock

    def raw_record(
        self,
        *,
        symbol: str,
        source: str,
        transport: str,
        payload: Any,
        source_timestamp: Any = None,
        network_latency_ms: float | None = None,
    ) -> RawRecord:
        """Preserve one adapter response before normalization."""
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        return RawRecord(
            symbol=symbol,
            source=source,
            transport=transport,
            payload=payload,
            ingest_ts=self._clock(),
            source_timestamp=source_timestamp,
            network_latency_ms=network_latency_ms,
            raw_size_bytes=len(encoded),
        )

    def provenance_entry(self, step: str, actor: str, detail: str = "") -> ProvenanceEntry:
        """Create one timestamped provenance entry."""
        return ProvenanceEntry(step, actor, self._clock(), detail)

    def attach_provenance(self, normalized: Any, entries: Iterable[ProvenanceEntry]):
        """Return a frozen normalized copy and its ordered provenance view."""
        chain = list(entries)
        return replace(normalized, _provenance=frozenset(chain)), chain
