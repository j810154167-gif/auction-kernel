"""Eastmoney adapter — HTTP for quotes, K-lines, and sector data.

Reuses existing patterns from data_preloader.py.
"""

import json
import time
import urllib.error
import urllib.parse
import urllib.request
import ssl

from datakit.adapters.base import BaseAdapter
from datakit.core.types import BlockInfo, HealthStatus, Kline, Quote, RawRecord
from datakit.core.engine import SourceUnavailable
from datakit.core.channel import ChannelManager


class EastmoneyAdapter(BaseAdapter):
    name = "eastmoney"
    display_name = "东方财富"
    requires_auth = False
    supports_ws = False
    key_env_vars = []
    key_injection_hint = "No API key required — public free source."

    def __init__(self):
        self.base_url = "https://push2delay.eastmoney.com"
        self.timeout = 15
        self.ua = "datakit/1.0"

    def _get_json(self, url: str, timeout: int | None = None) -> dict:
        """Sync HTTP GET returning parsed JSON."""
        data, _elapsed = self._get_json_with_latency(url, timeout=timeout)
        return data

    def _get_json_with_latency(self, url: str, timeout: int | None = None) -> tuple[dict, int]:
        """Sync HTTP GET returning parsed JSON and elapsed milliseconds."""
        if timeout is None:
            timeout = self.timeout
        req = urllib.request.Request(url, headers={
            "accept": "application/json",
            "user-agent": self.ua,
            "Referer": "https://data.eastmoney.com/",
        })
        started = time.time()
        try:
            with urllib.request.urlopen(req, timeout=timeout,
                                         context=ssl.create_default_context()) as resp:
                body = resp.read()
                elapsed = round((time.time() - started) * 1000)
                return json.loads(body), elapsed
        except Exception as e:
            raise SourceUnavailable(f"Eastmoney request failed: {e}")

    # ── Helpers ──

    def _em_to_tf_symbol(self, em_code: str) -> str:
        """Convert Eastmoney code (e.g. 1.000001) to TickFlow-style (000001.SZ)."""
        parts = em_code.split(".")
        if len(parts) == 2:
            market, code = parts
            if market == "1":  # SH
                return f"{code}.SH"
            elif market == "0":  # SZ
                return f"{code}.SZ"
        return em_code

    # ── Data interfaces ──

    async def fetch_quotes(self, symbols: list[str]) -> tuple[dict[str, Quote], dict[str, RawRecord]]:
        """Fetch quotes from Eastmoney push2 API."""
        # Convert TickFlow-style symbols to Eastmoney format
        em_codes = []
        for s in symbols:
            if s.endswith(".SH"):
                em_codes.append(f"1.{s[:-3]}")
            elif s.endswith(".SZ"):
                em_codes.append(f"0.{s[:-3]}")
            else:
                em_codes.append(s)

        url = f"{self.base_url}/api/qt/clist/get"
        params = {
            "pn": "1", "pz": str(len(em_codes)),
            "po": "0", "np": "1",
            "fltt": "2", "invt": "2",
            "fid": "f3",
            "fs": f"m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23",
            "fields": "f2,f3,f4,f5,f6,f12,f14,f15,f16,f17,f18",
        }
        url += "?" + urllib.parse.urlencode(params)
        data, elapsed = self._get_json_with_latency(url)
        items = data.get("data", {}).get("diff", [])
        results: dict[str, Quote] = {}
        raw: dict[str, RawRecord] = {}
        channel = ChannelManager()
        ts_ms = int(time.time() * 1000)
        for item in items:
            em_code = item.get("f12", "")
            sym = self._em_to_tf_symbol(em_code)
            raw[sym] = channel.raw_record(
                symbol=sym,
                source="eastmoney",
                transport="rest",
                payload=item,
                network_latency_ms=elapsed,
            )
            results[sym] = Quote(
                symbol=sym,
                name=item.get("f14", ""),
                last_price=float(item.get("f2", 0) or 0),
                open=float(item.get("f17", 0) or 0),
                high=float(item.get("f15", 0) or 0),
                low=float(item.get("f16", 0) or 0),
                volume=int(item.get("f5", 0) or 0),
                amount=float(item.get("f6", 0) or 0),
                prev_close=float(item.get("f18", 0) or 0),
                change_pct=float(item.get("f3", 0) or 0),
                timestamp_ms=ts_ms,
                source="eastmoney",
                _ingest_ts=time.time(),
            )
        return results, raw

    async def fetch_klines(self, symbols: list[str], days: int = 2) -> tuple[dict[str, list[Kline]], dict[str, RawRecord]]:
        """Fetch K-line from Eastmoney (daily)."""
        # Eastmoney K-line endpoint per symbol
        results: dict[str, list[Kline]] = {}
        raw: dict[str, RawRecord] = {}
        channel = ChannelManager()
        secid_map = {}
        for sym in symbols:
            if sym.endswith(".SH"):
                secid_map[sym] = f"1.{sym[:-3]}"
            elif sym.endswith(".SZ"):
                secid_map[sym] = f"0.{sym[:-3]}"
            else:
                secid_map[sym] = sym

        for sym, secid in secid_map.items():
            try:
                url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
                params = {
                    "secid": secid,
                    "fields1": "f1,f2,f3,f4,f5,f6",
                    "fields2": "f51,f52,f53,f54,f55,f56,f57",
                    "klt": "101",  # daily
                    "fqt": "1",    # 前复权
                    "end": "20500101",
                    "lmt": str(days + 1),
                }
                full_url = url + "?" + urllib.parse.urlencode(params)
                data, elapsed = self._get_json_with_latency(full_url)
                klines_data = data.get("data", {}).get("klines", [])
                raw[sym] = channel.raw_record(symbol=sym, source="eastmoney", transport="rest", payload=klines_data, network_latency_ms=elapsed)
                results[sym] = []
                for line in klines_data[-days:]:
                    parts = line.split(",")
                    if len(parts) >= 7:
                        results[sym].append(Kline(
                            symbol=sym,
                            date=parts[0],
                            open=float(parts[1]),
                            close=float(parts[2]),
                            high=float(parts[3]),
                            low=float(parts[4]),
                            volume=int(float(parts[5])),
                            amount=float(parts[6]),
                            _ingest_ts=time.time(),
                        ))
            except SourceUnavailable:
                # Skip failed symbols, let caller handle missing data
                pass
        return results, raw

    async def fetch_blocks(self, category: str = "industry") -> tuple[list[BlockInfo], dict[str, RawRecord]]:
        """Fetch sector/block data from Eastmoney."""
        fs_map = {
            "industry": "m:90+t:2",
            "concept": "m:90+t:3",
        }
        fs = fs_map.get(category, "m:90+t:2")
        url = f"{self.base_url}/api/qt/clist/get"
        params = {
            "pn": "1", "pz": "50",
            "po": "1", "np": "1",
            "fltt": "2", "invt": "2",
            "fid": "f3",
            "fs": fs,
            "fields": "f2,f3,f4,f12,f14",
        }
        full_url = url + "?" + urllib.parse.urlencode(params)
        data, elapsed = self._get_json_with_latency(full_url)
        items = data.get("data", {}).get("diff", [])
        results = []
        raw = {}
        channel = ChannelManager()
        for item in items:
            code = item.get("f12", "")
            raw[code] = channel.raw_record(symbol=code, source="eastmoney", transport="rest", payload=item, network_latency_ms=elapsed)
            results.append(BlockInfo(
                code=code,
                name=item.get("f14", ""),
                category=category,
                change_pct=float(item.get("f3", 0) or 0),
            ))
        return results, raw

    # ── Ops interfaces ──

    async def health_check(self) -> HealthStatus:
        """Probe Eastmoney with a minimal request."""
        started = time.time()
        try:
            url = f"{self.base_url}/api/qt/clist/get?pn=1&pz=1&po=0&np=1&fltt=2&invt=2&fid=f3&fs=m:0+t:6&fields=f2,f12"
            self._get_json(url)
            elapsed = round((time.time() - started) * 1000)
            return HealthStatus(
                source=self.name,
                reachable=True,
                latency_ms=elapsed,
                quota_remaining=None,
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
        """Eastmoney is free, no quota tracking."""
        return {"source": self.name, "remaining": None, "note": "free source, no quota"}


ADAPTER = EastmoneyAdapter()
