"""Health checker — probe all adapters and persist results."""

import asyncio
from datetime import datetime

from datakit.core.registry import list_all, get
from datakit.core.types import HealthStatus
from datakit.core import db


class HealthChecker:
    """Run health checks across all registered adapters."""

    async def check_all(self) -> list[HealthStatus]:
        """Full health sweep across all adapters."""
        adapters = list_all()
        results: list[HealthStatus] = []
        for item in adapters:
            name = item["name"]
            try:
                adapter = get(name)
                status = await adapter.health_check()
                results.append(status)
            except Exception as e:
                status = HealthStatus(
                    source=name,
                    reachable=False,
                    latency_ms=0,
                    error=str(e),
                )
                results.append(status)
            # Persist each result
            db.insert_health(status.source, status.reachable, status.latency_ms, status.error)
        return results

    async def check_one(self, source: str) -> HealthStatus:
        """Probe a single adapter."""
        adapter = get(source)
        status = await adapter.health_check()
        db.insert_health(status.source, status.reachable, status.latency_ms, status.error)
        return status

    def check_all_sync(self) -> list[HealthStatus]:
        """Synchronous wrapper for check_all."""
        return asyncio.run(self.check_all())
