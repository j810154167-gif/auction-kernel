"""TickFlow adapter — REST + WebSocket.

Reuses existing endpoint patterns from data_preloader.py.
"""

import asyncio
import json
import os
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta

from datakit.adapters.base import BaseAdapter
from datakit.core.types import BlockInfo, HealthStatus, Kline, Quote, RawRecord
from datakit.core.engine import SourceUnavailable
from datakit.core.channel import ChannelManager


def _get_api_key() -> str:
    key = os.environ.get("TICKFLOW_API_KEY", "").strip()
    if key:
        return key
    key_file = os.environ.get("TICKFLOW_API_KEY_FILE", "").strip()
    if key_file:
        with open(os.path.expanduser(key_file)) as f:
            return f.read().strip()
    raise RuntimeError("TickFlow API key missing: set TICKFLOW_API_KEY or TICKFLOW_API_KEY_FILE")


class TickFlowAdapter(BaseAdapter):
    name = "tickflow"
    display_name = "TickFlow API"
    requires_auth = True
    supports_ws = True
    key_env_vars = ["TICKFLOW_API_KEY", "TICKFLOW_API_KEY_FILE"]
    key_injection_hint = (
        "Set TICKFLOW_API_KEY env var with your API key (e.g. tk_b3...),\n"
        "or set TICKFLOW_API_KEY_FILE pointing to a file containing the key.\n"
        "Best practice: store in ~/.openclaw/keys.env and source it before running."
    )

    def __init__(self):
        self.api_key = _get_api_key()
        self.base_url = os.environ.get("TICKFLOW_BASE_URL", "https://api.tickflow.org")
        self.ws_url = os.environ.get("TICKFLOW_WS_URL", "wss://api.tickflow.org/v1/ws/stream")
        self.timeout = int(os.environ.get("TICKFLOW_TIMEOUT", "20"))
        self.max_retries = 2
        self.ua = "datakit/1.0"

    # ── HTTP helpers ──

    def _get(self, path: str, params: dict | None = None, timeout: int | None = None) -> dict:
        """Sync HTTP GET with retry. Returns {ok, status, elapsed_ms, data|error}."""
        if timeout is None:
            timeout = self.timeout
        url = f"{self.base_url}{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params, doseq=False)
        req = urllib.request.Request(url, headers={
            "x-api-key": self.api_key,
            "accept": "application/json",
            "user-agent": self.ua,
        })
        started = time.time()
        last_err = ""
        for attempt in range(self.max_retries + 1):
            try:
                with urllib.request.urlopen(req, timeout=timeout,
                                             context=ssl.create_default_context()) as resp:
                    elapsed = round((time.time() - started) * 1000)
                    return {"ok": True, "status": resp.status,
                            "elapsed_ms": elapsed,
                            "data": json.loads(resp.read())}
            except urllib.error.HTTPError as exc:
                last_err = f"HTTP {exc.code}: {exc.read().decode(errors='replace')[:150]}"
                if exc.code == 429 and attempt < self.max_retries:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                break
            except Exception as exc:
                last_err = f"{type(exc).__name__}: {exc}"
                if attempt < self.max_retries:
                    time.sleep(1)
                    continue
                break
        elapsed = round((time.time() - started) * 1000)
        return {"ok": False, "elapsed_ms": elapsed, "error": last_err}

    # ── Data interfaces ──

    async def fetch_quotes(self, symbols: list[str]) -> tuple[dict[str, Quote], dict[str, RawRecord]]:
        """Fetch real-time quotes via REST."""
        batch_size = 50
        results: dict[str, Quote] = {}
        raw: dict[str, RawRecord] = {}
        channel = ChannelManager()
        for i in range(0, len(symbols), batch_size):
            batch = symbols[i:i + batch_size]
            r = self._get("/v1/quotes", {"symbols": ",".join(batch)})
            if not r["ok"]:
                raise SourceUnavailable(f"TickFlow quotes failed: {r.get('error')}")
            data = r["data"]
            ts_ms = int(time.time() * 1000)
            items = data.get("data", data) if isinstance(data, dict) else data
            if isinstance(items, list):
                for item in items:
                    sym = item.get("symbol", "")
                    raw[sym] = channel.raw_record(symbol=sym, source="tickflow", transport="rest", payload=item, network_latency_ms=r.get("elapsed_ms"))
                    results[sym] = Quote(
                        symbol=sym,
                        name=item.get("name", ""),
                        last_price=float(item.get("last_price", 0)),
                        open=float(item.get("open", 0)),
                        high=float(item.get("high", 0)),
                        low=float(item.get("low", 0)),
                        volume=int(item.get("volume", 0)),
                        amount=float(item.get("amount", 0)),
                        prev_close=float(item.get("prev_close", 0)),
                        change_pct=float(item.get("change_pct", 0)),
                        timestamp_ms=ts_ms,
                        source="tickflow",
                        _ingest_ts=time.time(),
                    )
            elif isinstance(items, dict):
                for sym, item in items.items():
                    raw[sym] = channel.raw_record(symbol=sym, source="tickflow", transport="rest", payload=item, network_latency_ms=r.get("elapsed_ms"))
                    results[sym] = Quote(
                        symbol=sym,
                        name=item.get("name", ""),
                        last_price=float(item.get("last_price", 0)),
                        open=float(item.get("open", 0)),
                        high=float(item.get("high", 0)),
                        low=float(item.get("low", 0)),
                        volume=int(item.get("volume", 0)),
                        amount=float(item.get("amount", 0)),
                        prev_close=float(item.get("prev_close", 0)),
                        change_pct=float(item.get("change_pct", 0)),
                        timestamp_ms=ts_ms,
                        source="tickflow",
                        _ingest_ts=time.time(),
                    )
        return results, raw

    async def fetch_klines(self, symbols: list[str], days: int = 2) -> tuple[dict[str, list[Kline]], dict[str, RawRecord]]:
        """Fetch daily K-lines."""
        yesterday = (datetime.now(timezone(timedelta(hours=8))) - timedelta(days=1)).strftime("%Y-%m-%d")
        batch_size = 100
        results: dict[str, list[Kline]] = {}
        raw: dict[str, RawRecord] = {}
        channel = ChannelManager()
        for i in range(0, len(symbols), batch_size):
            batch = symbols[i:i + batch_size]
            r = self._get("/v1/klines/batch", {
                "symbols": ",".join(batch),
                "period": "1d",
                "count": str(days),
                "end_date": yesterday,
                "adjust": "none",
            })
            if not r["ok"]:
                raise SourceUnavailable(f"TickFlow klines failed: {r.get('error')}")
            data = r["data"]
            items = data.get("data", data) if isinstance(data, dict) else data
            if isinstance(items, dict):
                for sym, bars in items.items():
                    raw[sym] = channel.raw_record(symbol=sym, source="tickflow", transport="rest", payload=bars, network_latency_ms=r.get("elapsed_ms"))
                    results[sym] = [
                        Kline(
                            symbol=sym,
                            date=b.get("date", ""),
                            open=float(b.get("open", 0)),
                            high=float(b.get("high", 0)),
                            low=float(b.get("low", 0)),
                            close=float(b.get("close", 0)),
                            volume=int(b.get("volume", 0)),
                            amount=float(b.get("amount", 0)),
                            _ingest_ts=time.time(),
                        )
                        for b in (bars if isinstance(bars, list) else [bars])
                    ]
            elif isinstance(items, list):
                sym_map: dict[str, list] = {}
                for b in items:
                    s = b.get("symbol", "")
                    sym_map.setdefault(s, []).append(b)
                for sym, bars in sym_map.items():
                    raw[sym] = channel.raw_record(symbol=sym, source="tickflow", transport="rest", payload=bars, network_latency_ms=r.get("elapsed_ms"))
                    results[sym] = [
                        Kline(
                            symbol=sym,
                            date=b.get("date", ""),
                            open=float(b.get("open", 0)),
                            high=float(b.get("high", 0)),
                            low=float(b.get("low", 0)),
                            close=float(b.get("close", 0)),
                            volume=int(b.get("volume", 0)),
                            amount=float(b.get("amount", 0)),
                            _ingest_ts=time.time(),
                        )
                        for b in bars
                    ]
        return results, raw

    async def fetch_blocks(self, category: str = "industry") -> list[BlockInfo]:
        """TickFlow does not provide block data — raise SourceUnavailable to trigger failover."""
        raise SourceUnavailable("TickFlow does not support block/sector data")

    # ── Ops interfaces ──

    async def health_check(self) -> HealthStatus:
        """Probe by requesting a single quote."""
        started = time.time()
        try:
            r = self._get("/v1/quotes", {"symbols": "000001.SZ"}, timeout=5)
            elapsed = round((time.time() - started) * 1000)
            if r["ok"]:
                return HealthStatus(
                    source=self.name,
                    reachable=True,
                    latency_ms=elapsed,
                    quota_remaining=None,
                )
            return HealthStatus(
                source=self.name,
                reachable=False,
                latency_ms=elapsed,
                error=r.get("error", "unknown"),
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
        """TickFlow does not expose quota info in API responses."""
        return {"source": self.name, "remaining": None, "note": "quota not exposed by TickFlow API"}

    # ── WebSocket ──

    async def connect_ws(self, symbols: list[str], callback) -> None:
        """Connect to TickFlow WebSocket stream and invoke callback on each message."""
        import websockets
        channel = ChannelManager()
        uri = f"{self.ws_url}?api_key={self.api_key}"
        try:
            async with websockets.connect(uri, open_timeout=10, ping_timeout=15, proxy=None) as ws:
                sub = json.dumps({"op": "subscribe", "channel": "quotes", "symbols": symbols})
                await ws.send(sub)
                resp = await asyncio.wait_for(ws.recv(), timeout=10)
                parsed = json.loads(resp)
                if parsed.get("op") != "subscribed":
                    raise SourceUnavailable(f"TickFlow WS subscription failed: {resp[:200]}")
                while True:
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=3)
                        frame = json.loads(msg)
                        symbol = frame.get("symbol", "") if isinstance(frame, dict) else ""
                        if symbol:
                            frame["_raw_record"] = channel.raw_record(symbol=symbol, source="tickflow", transport="websocket", payload=frame).__dict__
                        await callback(frame)
                    except asyncio.TimeoutError:
                        continue
        except Exception as e:
            raise SourceUnavailable(f"TickFlow WS failed: {e}")


ADAPTER = TickFlowAdapter()
