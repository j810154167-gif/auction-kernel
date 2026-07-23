"""Router — unified data access with fallback chain.

Loads fallback chains from config.yaml, tries adapters in order,
logs failover events, and returns results.
"""

import asyncio
import sys
from pathlib import Path
from typing import Any

import yaml

from datakit.core.registry import get, list_all
from datakit.core.types import (
    BlockInfo,
    ConsumptionIntent,
    FetchResult,
    HealthStatus,
    Kline,
    ProvenanceEntry,
    Quote,
)
from datakit.core import db
from datakit.core.channel import ChannelManager


class SourceUnavailable(Exception):
    """Raised when a specific source is unreachable."""


class AllSourcesFailed(Exception):
    """Raised when all sources in the fallback chain fail."""
    def __init__(self, chain: str, targets: Any):
        self.chain = chain
        self.targets = targets
        super().__init__(f"All sources failed for '{chain}': {targets}")


class Router:
    """Unified data access router with automatic failover."""

    def __init__(self, config_path: str | Path | None = None):
        if config_path is None:
            config_path = Path(__file__).resolve().parent.parent / "config.yaml"
        self.config_path = Path(config_path)
        self._config = self._load_config()
        self._fallback = self._config.get("fallback", {})

    def _load_config(self) -> dict:
        if not self.config_path.exists():
            return {}
        with open(self.config_path) as f:
            return yaml.safe_load(f) or {}

    def _source_config(self, name: str) -> dict:
        return self._config.get("sources", {}).get(name, {})

    async def quote(
        self,
        symbols: list[str],
        mode: str = "auto",
        intent: ConsumptionIntent | str | None = None,
    ) -> FetchResult:
        """Fetch real-time quotes with automatic failover."""
        return await self._route("quote", symbols, mode, intent=intent)

    async def klines(
        self,
        symbols: list[str],
        days: int = 2,
        mode: str = "auto",
        intent: ConsumptionIntent | str | None = None,
    ) -> FetchResult:
        """Fetch daily K-lines with automatic failover."""
        return await self._route("kline", symbols, mode, intent=intent, days=days)

    async def blocks(
        self,
        category: str = "industry",
        mode: str = "auto",
        intent: ConsumptionIntent | str | None = None,
    ) -> FetchResult:
        """Fetch block/theme data. mode: realtime | cache-ok | auto."""
        return await self._route("block", category, mode, intent=intent)

    async def health_check(self) -> list[HealthStatus]:
        """Run health check on all registered adapters."""
        from datakit.core.registry import discover
        discover()
        results = []
        for name in list_all():
            try:
                adapter = get(name["name"])
                status = await adapter.health_check()
                db.insert_health(status.source, status.reachable, status.latency_ms, status.error)
                results.append(status)
            except Exception as e:
                results.append(HealthStatus(
                    source=name["name"],
                    reachable=False,
                    latency_ms=0,
                    error=str(e),
                ))
        return results

    async def _route(
        self,
        chain_key: str,
        target: Any,
        mode: str,
        intent: ConsumptionIntent | str | None = None,
        **kwargs,
    ) -> FetchResult:
        """Core routing logic: try each adapter in the fallback chain."""
        chain = self._fallback.get(chain_key, [])
        if not chain:
            raise AllSourcesFailed(chain_key, target)

        resolved_intent = self._resolve_intent(intent)
        errors = []
        failover_entries: list[ProvenanceEntry] = []
        channel = ChannelManager()
        for idx, source_name in enumerate(chain):
            # Check quota exhaustion
            if db.is_quota_exhausted(source_name):
                errors.append(f"{source_name}: quota exhausted")
                continue

            try:
                adapter = get(source_name)
                if chain_key == "quote":
                    result = await adapter.fetch_quotes(target)
                elif chain_key == "kline":
                    result = await adapter.fetch_klines(target, days=kwargs.get("days", 2))
                elif chain_key == "block":
                    result = await adapter.fetch_blocks(target)
                elif chain_key == "reason":
                    result = await adapter.fetch_block_reason(target)
                else:
                    raise ValueError(f"Unknown chain: {chain_key}")

                normalized_preview, _raw_preview = self._split_adapter_result(result)
                if (isinstance(normalized_preview, dict) or isinstance(normalized_preview, list)) and not normalized_preview:
                    raise SourceUnavailable(f"{source_name} returned no {chain_key} data")

                # Track quota
                db.upsert_quota(source_name, chain_key, calls=1)
                return self._to_fetch_result(result, source_name, resolved_intent, failover_entries, channel)

            except SourceUnavailable as e:
                reason = str(e)
                errors.append(f"{source_name}: {reason}")
                failover_entries.append(channel.provenance_entry("source_error", source_name, reason))
                # Log failover if there's a next source
                if idx + 1 < len(chain):
                    next_source = chain[idx + 1]
                    db.insert_failover(source_name, next_source, reason, str(target), provenance_gap=False)
                    failover_entries.append(
                        channel.provenance_entry("failover", "datakit.router", f"{source_name} → {next_source}")
                    )
                    print(f"[datakit] failover {source_name} → {next_source} ({reason})", file=sys.stderr)
                continue

            except Exception as e:
                errors.append(f"{source_name}: {e}")
                failover_entries.append(channel.provenance_entry("source_error", source_name, str(e)))
                if idx + 1 < len(chain):
                    db.insert_failover(source_name, chain[idx + 1], str(e), str(target), provenance_gap=False)
                    failover_entries.append(
                        channel.provenance_entry("failover", "datakit.router", f"{source_name} → {chain[idx + 1]}")
                    )
                continue

        raise AllSourcesFailed(chain_key, f"{target} — errors: {'; '.join(errors)}")

    def _resolve_intent(self, intent: ConsumptionIntent | str | None) -> ConsumptionIntent:
        if intent is None:
            value = self._config.get("channel", {}).get("default_intent", ConsumptionIntent.REALTIME_DECISION.value)
            return ConsumptionIntent(value)
        if isinstance(intent, ConsumptionIntent):
            return intent
        aliases = {"realtime": "realtime-decision", "audit": "audit", "backtest": "backtest", "full-trace": "full-trace"}
        return ConsumptionIntent(aliases.get(intent, intent))

    def _to_fetch_result(
        self,
        result: Any,
        source_name: str,
        intent: ConsumptionIntent,
        prefix_entries: list[ProvenanceEntry],
        channel: ChannelManager,
    ) -> FetchResult:
        normalized, raw = self._split_adapter_result(result)
        provenance: dict[str, list[ProvenanceEntry]] = {}
        normalized_with_provenance = self._attach_result_provenance(normalized, raw, source_name, prefix_entries, channel, provenance)

        include_raw = intent in (ConsumptionIntent.AUDIT, ConsumptionIntent.FULL_TRACE)
        include_provenance = intent in (
            ConsumptionIntent.REALTIME_DECISION,
            ConsumptionIntent.AUDIT,
            ConsumptionIntent.FULL_TRACE,
        )
        return FetchResult(
            normalized=normalized_with_provenance,
            raw=raw if include_raw else {},
            provenance=provenance if include_provenance else {},
        )

    @staticmethod
    def _split_adapter_result(result: Any) -> tuple[Any, dict]:
        if isinstance(result, FetchResult):
            return result.normalized, result.raw
        if isinstance(result, tuple) and len(result) == 2:
            return result
        return result, {}

    def _attach_result_provenance(
        self,
        normalized: Any,
        raw: dict,
        source_name: str,
        prefix_entries: list[ProvenanceEntry],
        channel: ChannelManager,
        provenance: dict[str, list[ProvenanceEntry]],
    ) -> Any:
        if isinstance(normalized, dict):
            updated = {}
            for symbol, value in normalized.items():
                entries = self._entries_for_symbol(symbol, value, raw, source_name, prefix_entries, channel)
                updated[symbol] = self._attach_value(value, entries, channel)
                provenance[symbol] = entries
            return updated
        if isinstance(normalized, list):
            updated_list = []
            for index, value in enumerate(normalized):
                symbol = getattr(value, "code", str(index))
                entries = self._entries_for_symbol(symbol, value, raw, source_name, prefix_entries, channel)
                updated_list.append(self._attach_value(value, entries, channel))
                provenance[symbol] = entries
            return updated_list
        return normalized

    def _entries_for_symbol(
        self,
        symbol: str,
        value: Any,
        raw: dict,
        source_name: str,
        prefix_entries: list[ProvenanceEntry],
        channel: ChannelManager,
    ) -> list[ProvenanceEntry]:
        existing = list(getattr(value, "_provenance", frozenset()))
        has_source = any(entry.step == "source_fetch" for entry in existing)
        has_normalize = any(entry.step == "normalize" for entry in existing)
        has_router = any(entry.step == "router_select" for entry in existing)
        entries = list(prefix_entries) + existing
        if not has_source:
            detail = "adapter returned normalized data"
            if symbol in raw:
                detail = f"raw_size_bytes={raw[symbol].raw_size_bytes}"
            entries.append(channel.provenance_entry("source_fetch", source_name, detail))
        if not has_normalize:
            entries.append(channel.provenance_entry("normalize", "datakit.normalizer", f"{type(value).__name__}"))
        if not has_router:
            entries.append(channel.provenance_entry("router_select", "datakit.router", source_name))
        return entries

    @staticmethod
    def _attach_value(value: Any, entries: list[ProvenanceEntry], channel: ChannelManager) -> Any:
        if isinstance(value, list):
            return [channel.attach_provenance(item, entries)[0] for item in value]
        if hasattr(value, "_provenance"):
            return channel.attach_provenance(value, entries)[0]
        return value
