"""datakit — unified data access toolkit.

CLI + Python API for multi-source financial data with automatic failover.

Usage:
    # Python API
    from datakit import Datakit
    dk = Datakit()
    quotes = dk.quote(["000001.SZ", "000002.SZ"])
    klines = dk.klines(["000001.SZ"], days=2)
    blocks = dk.blocks("industry", mode="auto")
    health = dk.health_all()

    # CLI
    python -m datakit quote --symbols 000001.SZ --json
    python -m datakit ops check --json
"""

import asyncio
import sys
from pathlib import Path

from datakit.core.registry import list_all, get, health_all as _health_all
from datakit.core.engine import Router
from datakit.core.calendar import AnchorCalendar
from datakit.core.types import (
    AnchorPoint,
    BlockInfo,
    ConsumptionIntent,
    FetchResult,
    HealthStatus,
    Kline,
    ProvenanceEntry,
    Quote,
    RawRecord,
)
from datakit.core import db
from datakit.inject import key_status, key_injection_guide
from datakit.guard import check_consensus, print_warning


class Datakit:
    """Public API facade for datakit.

    Provides synchronous wrappers for all data operations.
    Internally uses asyncio with Router.
    """

    def __init__(self, config_path: str | Path | None = None):
        # ── 未来函数风险门控 ──
        if not check_consensus():
            print_warning(file=sys.stderr)

        if config_path is None:
            config_path = Path(__file__).resolve().parent / "config.yaml"
        self._router = Router(config_path)
        # Initialize DB
        db_dir = Path(__file__).resolve().parent
        db.init(db_dir / "datakit.db")

    def quote(self, symbols: list[str], intent: ConsumptionIntent | str | None = None) -> FetchResult:
        """Fetch real-time quotes with automatic failover."""
        requested = list(symbols)
        routed_symbols = [self._normalize_symbol(symbol) for symbol in requested]
        result = asyncio.run(self._router.quote(routed_symbols, intent=intent))
        self._add_requested_symbol_aliases(result, requested, routed_symbols)
        return result

    def klines(self, symbols: list[str], days: int = 2, intent: ConsumptionIntent | str | None = None) -> FetchResult:
        """Fetch daily K-lines with automatic failover."""
        return asyncio.run(self._router.klines(symbols, days=days, intent=intent))

    def blocks(
        self,
        category: str = "industry",
        mode: str = "auto",
        intent: ConsumptionIntent | str | None = None,
    ) -> FetchResult:
        """Fetch block/theme data. mode: realtime | cache-ok | auto."""
        return asyncio.run(self._router.blocks(category=category, mode=mode, intent=intent))

    def anchors(self, calendar_name: str) -> AnchorCalendar:
        """Return an anchor calendar by name."""
        return AnchorCalendar(calendar_name)

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        if symbol.isdigit() and len(symbol) == 6:
            suffix = ".SH" if symbol.startswith("6") else ".SZ"
            return f"{symbol}{suffix}"
        return symbol

    @staticmethod
    def _add_requested_symbol_aliases(result: FetchResult, requested: list[str], routed: list[str]) -> None:
        for original, normalized in zip(requested, routed):
            if original == normalized:
                continue
            if normalized in result.normalized:
                result.normalized.setdefault(original, result.normalized[normalized])
            if normalized in result.raw:
                result.raw.setdefault(original, result.raw[normalized])
            if normalized in result.provenance:
                result.provenance.setdefault(original, result.provenance[normalized])

    def health_all(self) -> list[HealthStatus]:
        """Run health check on all registered adapters (synchronous)."""
        return _health_all()

    def list_sources(self) -> list[dict]:
        """List all registered data sources."""
        return list_all()

    def get_source(self, name: str):
        """Get a specific adapter by name."""
        return get(name)

__all__ = ["Datakit", "Quote", "Kline", "BlockInfo", "HealthStatus", "ConsumptionIntent", "FetchResult", "RawRecord", "ProvenanceEntry", "AnchorPoint"]
