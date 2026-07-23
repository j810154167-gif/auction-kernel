"""iwencai adapter — offline-first: blocks from cached data, health gate probe.

iwencai SkillHub provides industry/concept block data through its OpenAPI.
The adapter caches results and only probes the HTTP gate for health checks.
"""

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import ssl

from datakit.adapters.base import BaseAdapter
from datakit.core.types import BlockInfo, HealthStatus, Kline, Quote, RawRecord
from datakit.core.engine import SourceUnavailable
from datakit.core.channel import ChannelManager


def _get_api_key() -> str:
    key = os.environ.get("IWENCAI_API_KEY", "").strip()
    if key:
        return key
    key_file = os.environ.get("IWENCAI_API_KEY_FILE", "").strip()
    if key_file:
        with open(os.path.expanduser(key_file)) as f:
            return f.read().strip()
    raise RuntimeError("i问财 API key missing: set IWENCAI_API_KEY or IWENCAI_API_KEY_FILE")


class IwencaiAdapter(BaseAdapter):
    name = "iwencai"
    display_name = "i问财 SkillHub"
    requires_auth = True
    supports_ws = False
    key_env_vars = ["IWENCAI_API_KEY", "IWENCAI_API_KEY_FILE"]
    key_injection_hint = (
        "Set IWENCAI_API_KEY env var with your OpenAPI key (e.g. sk-proj-...),\n"
        "or set IWENCAI_API_KEY_FILE pointing to a file containing the key.\n"
        "Best practice: store in ~/.openclaw/keys.env and source it before running."
    )

    def __init__(self):
        self.api_key = _get_api_key()
        self.base_url = os.environ.get("IWENCAI_BASE_URL", "https://openapi.iwencai.com")
        self.timeout = 15
        self.ua = "datakit/1.0"

    def _get_json(self, path: str, timeout: int | None = None) -> dict:
        """Sync HTTP GET returning parsed JSON."""
        if timeout is None:
            timeout = self.timeout
        url = f"{self.base_url}{path}"
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {self.api_key}",
            "accept": "application/json",
            "user-agent": self.ua,
        })
        try:
            with urllib.request.urlopen(req, timeout=timeout,
                                         context=ssl.create_default_context()) as resp:
                return json.loads(resp.read())
        except Exception as e:
            raise SourceUnavailable(f"iwencai request failed: {e}")

    # ── Data interfaces ──

    async def fetch_quotes(self, symbols: list[str]) -> tuple[dict[str, Quote], dict[str, RawRecord]]:
        """iwencai does not provide real-time quotes."""
        raise SourceUnavailable("iwencai does not support real-time quotes")

    async def fetch_klines(self, symbols: list[str], days: int = 2) -> tuple[dict[str, list[Kline]], dict[str, RawRecord]]:
        """iwencai does not provide K-line data."""
        raise SourceUnavailable("iwencai does not support K-line data")

    async def fetch_blocks(self, category: str = "industry") -> tuple[list[BlockInfo], dict[str, RawRecord]]:
        """Fetch block data from iwencai SkillHub."""
        # Try the skillhub endpoint for industry/concept data
        endpoint = "/api/skillhub/industry" if category == "industry" else "/api/skillhub/concept"
        try:
            data = self._get_json(endpoint)
            items = data.get("data", data) if isinstance(data, dict) else data
            if not isinstance(items, list):
                raise SourceUnavailable(f"iwencai blocks unexpected format: {type(items)}")
            results = []
            raw = {}
            channel = ChannelManager()
            for item in items:
                code = str(item.get("code", ""))
                raw[code] = channel.raw_record(symbol=code, source="iwencai", transport="http", payload=item)
                results.append(BlockInfo(
                    code=code,
                    name=str(item.get("name", "")),
                    category=category,
                    change_pct=float(item.get("change_pct", 0) or 0),
                    members=tuple(item.get("members", []) or []),
                ))
            return results, raw
        except SourceUnavailable:
            raise
        except Exception as e:
            raise SourceUnavailable(f"iwencai blocks failed: {e}")

    async def fetch_block_reason(self, symbol: str) -> dict:
        """Fetch limit-up reason for a symbol."""
        try:
            data = self._get_json(f"/api/skillhub/limit-reason?symbol={symbol}")
            return data.get("data", data) if isinstance(data, dict) else {}
        except Exception as e:
            raise SourceUnavailable(f"iwencai limit reason failed: {e}")

    # ── Ops interfaces ──

    async def health_check(self) -> HealthStatus:
        """Probe iwencai by querying block endpoint (lightweight)."""
        started = time.time()
        try:
            # Use blocks endpoint as health probe — minimal payload
            self._get_json("/api/skillhub/industry", timeout=5)
            elapsed = round((time.time() - started) * 1000)
            return HealthStatus(
                source=self.name,
                reachable=True,
                latency_ms=elapsed,
            )
        except SourceUnavailable as e:
            elapsed = round((time.time() - started) * 1000)
            err_msg = str(e)
            # 401/403 = server is reachable but auth issue
            if "401" in err_msg or "403" in err_msg:
                return HealthStatus(
                    source=self.name,
                    reachable=True,
                    latency_ms=elapsed,
                    error=f"auth: {err_msg}",
                )
            return HealthStatus(
                source=self.name,
                reachable=False,
                latency_ms=elapsed,
                error=err_msg,
            )
        except Exception as e:
            elapsed = round((time.time() - started) * 1000)
            return HealthStatus(
                source=self.name,
                reachable=False,
                latency_ms=elapsed,
                error=str(e),
            )

    async def quota_status(self) -> dict:
        """iwencai quota is not publicly exposed."""
        return {"source": self.name, "remaining": None, "note": "quota not exposed by iwencai API"}


ADAPTER = IwencaiAdapter()
