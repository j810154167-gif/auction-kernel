"""Adapter abstract base class."""

from abc import ABC, abstractmethod
from datakit.core.types import BlockInfo, HealthStatus, Kline, Quote, RawRecord


class BaseAdapter(ABC):
    """Every data source adapter must implement this interface.

    Subclasses set class-level attributes:
        name: str
        display_name: str
        requires_auth: bool
        supports_ws: bool
    """

    name: str
    display_name: str
    requires_auth: bool = False
    supports_ws: bool = False

    # Key injection metadata — shown to LLM/Agent on discovery
    key_env_vars: list[str] = []       # e.g. ["TICKFLOW_API_KEY"]
    key_injection_hint: str = ""       # e.g. "export TICKFLOW_API_KEY=tk_xxx"

    # ── Data interfaces (required) ──

    @abstractmethod
    async def fetch_quotes(self, symbols: list[str]) -> tuple[dict[str, Quote], dict[str, RawRecord]]:
        """Batch fetch real-time quotes. Returns ({symbol: Quote}, {symbol: RawRecord})."""
        ...

    @abstractmethod
    async def fetch_klines(self, symbols: list[str], days: int = 2) -> tuple[dict[str, list[Kline]], dict[str, RawRecord]]:
        """Batch fetch daily K-lines. Returns ({symbol: [Kline, ...]}, {symbol: RawRecord})."""
        ...

    @abstractmethod
    async def fetch_blocks(self, category: str = "industry") -> tuple[list[BlockInfo], dict[str, RawRecord]]:
        """Fetch block/sector list with member symbols and raw records."""
        ...

    # ── Ops interfaces (required) ──

    @abstractmethod
    async def health_check(self) -> HealthStatus:
        """Probe the source: minimal request, measure latency and reachability."""
        ...

    @abstractmethod
    async def quota_status(self) -> dict:
        """Return quota info: {remaining, total, reset_time, ...}."""
        ...

    # ── Optional interfaces ──

    async def connect_ws(self, symbols: list[str], callback) -> None:
        """Establish WebSocket connection (only for WS-capable sources)."""
        raise NotImplementedError(f"{self.name} does not support WebSocket")
