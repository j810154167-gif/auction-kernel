"""Unified data models for datakit."""

from dataclasses import dataclass, field
from datetime import datetime, time
from enum import Enum
from typing import Any, Iterator, Optional


@dataclass(frozen=True)
class RawRecord:
    """Adapter response preserved before normalization."""
    symbol: str
    source: str
    transport: str
    payload: Any
    ingest_ts: float
    source_timestamp: Optional[Any]
    network_latency_ms: Optional[float]
    raw_size_bytes: int


@dataclass(frozen=True)
class ProvenanceEntry:
    """One immutable step in a record's processing lineage."""
    step: str
    actor: str
    timestamp: float
    detail: str


class ConsumptionIntent(Enum):
    """Requested combination of data-channel views."""
    REALTIME_DECISION = "realtime-decision"
    BACKTEST = "backtest"
    AUDIT = "audit"
    FULL_TRACE = "full-trace"


@dataclass
class AnchorPoint:
    """A caller-defined time anchor."""
    label: str
    time: time
    tz: str


@dataclass
class FetchResult:
    """Normalized, raw, and provenance views of one fetch."""
    normalized: dict
    raw: dict = field(default_factory=dict)
    provenance: dict = field(default_factory=dict)

    def __iter__(self) -> Iterator:
        return iter(self.normalized)


@dataclass(frozen=True)
class Quote:
    """Real-time quote snapshot."""
    symbol: str
    name: str
    last_price: float
    open: float
    high: float
    low: float
    volume: int          # shares
    amount: float        # yuan
    prev_close: float
    change_pct: float
    timestamp_ms: int    # exchange/source timestamp (ms)
    source: str          # "tickflow" | "eastmoney"
    _ingest_ts: float    # local ingestion timestamp (time.time()) — for temporal safety audit
    _provenance: frozenset[ProvenanceEntry] = field(default_factory=frozenset)


@dataclass(frozen=True)
class Kline:
    """Daily K-line bar."""
    symbol: str
    date: str            # "2026-07-07"
    open: float
    high: float
    low: float
    close: float
    volume: int
    amount: float
    _ingest_ts: float    # local ingestion timestamp (time.time())
    _provenance: frozenset[ProvenanceEntry] = field(default_factory=frozenset)


@dataclass(frozen=True)
class BlockInfo:
    """Sector/theme block info."""
    code: str            # block code
    name: str            # block name
    category: str        # "industry" | "concept"
    change_pct: float
    members: tuple[str, ...] = field(default_factory=tuple)
    _provenance: frozenset[ProvenanceEntry] = field(default_factory=frozenset)


@dataclass
class HealthStatus:
    """Adapter health check result."""
    source: str
    reachable: bool
    latency_ms: int
    quota_remaining: Optional[int] = None  # None = no quota concept
    last_checked: datetime = field(default_factory=datetime.now)
    error: Optional[str] = None
