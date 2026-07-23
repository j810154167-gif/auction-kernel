## Scope Boundary

This task list is for the adjacent `datakit` data capability layer. It is included in the LingGuanOS workspace only as a downgraded upstream-data protocol reference and must not be treated as a LingGuanOS workflow-kernel implementation plan.

Do not modify LingGuanOS daily governance, node consensus cards, modular map contracts, AgentPacket/HumanCard contracts, or `datakit/config.yaml` while executing this change unless a separate explicit decision is made.

## 1. Data Model Extension (core/types.py)

- [x] 1.1 Add `RawRecord` frozen dataclass with fields: symbol, source, transport, payload, ingest_ts, source_timestamp, network_latency_ms, raw_size_bytes
- [x] 1.2 Add `ProvenanceEntry` frozen dataclass with fields: step, actor, timestamp, detail
- [x] 1.3 Add `ConsumptionIntent` enum: REALTIME_DECISION, BACKTEST, AUDIT, FULL_TRACE
- [x] 1.4 Add `AnchorPoint` dataclass with fields: label, time (datetime.time), tz (str)
- [x] 1.5 Add `FetchResult` dataclass wrapping normalized (dict), raw (dict), provenance (dict) — with `.normalized` as the default iteration target
- [x] 1.6 Add `_provenance: frozenset[ProvenanceEntry]` field to `Quote`, `Kline`, `BlockInfo` (default empty frozenset, backward compatible)

## 2. Core Modules

- [x] 2.1 Create `core/channel.py` — `ChannelManager` that constructs `RawRecord` from adapter responses and assembles `ProvenanceEntry` chain during normalize
- [x] 2.2 Create `core/provenance.py` — `ProvenanceBuilder` context manager: `with ProvenanceBuilder() as pb: ...` auto-stamps source_fetch / normalize / failover steps
- [x] 2.3 Create `core/calendar.py` — `AnchorCalendar` class: loads `config.yaml` anchors, `next_anchor()`, `validate_temporal(data_ts, anchor_label)`, `current_window()`
- [x] 2.4 Extend `core/engine.py` Router — add `intent` parameter to `quote()`, `klines()`, `blocks()`; implement routing matrix dispatching to channels per `ConsumptionIntent`
- [x] 2.5 Ensure `Router._route()` returns `FetchResult` instead of raw dict — all internal callers adapted

## 3. Adapter Updates

- [x] 3.1 Update `adapters/base.py` — `fetch_quotes()` / `fetch_klines()` / `fetch_blocks()` return type signature updated to return `(Normalized, RawRecord)` tuple per symbol
- [x] 3.2 Update `adapters/tickflow.py` — REST quotes: capture original JSON as `RawRecord(payload=...)` with `transport="rest"`; WS frames: capture each frame as `RawRecord` with `transport="websocket"`
- [x] 3.3 Update `adapters/eastmoney.py` — capture original HTTP response JSON as `RawRecord`; measure and record `network_latency_ms`
- [x] 3.4 Update `adapters/iwencai.py` — capture cached payload origin as `RawRecord(transport="cache")` or `RawRecord(transport="http")`; note source_timestamp if available

## 4. Cache Extension (services/cache.py)

- [x] 4.1 Add `cache/raw/` subdirectory support — `write_raw()` and `read_raw()` methods for RawRecord Parquet storage
- [x] 4.2 Ensure `_provenance` frozenset survives Parquet round-trip — serialize as JSON array column, deserialize back to `frozenset[ProvenanceEntry]`
- [x] 4.3 On cache read, auto-append `ProvenanceEntry(step="cache_hit", ...)` to the provenance chain
- [x] 4.4 Add raw cache TTL to `config.yaml` under `cache.ttl.raw_record` (default: 1d)
- [x] 4.5 Extend `cache status` CLI to report raw cache statistics alongside normalized cache

## 5. CLI Extension (cli/commands.py)

- [x] 5.1 Add `--intent` flag to `quote`, `kline`, `block` subcommands — maps string to `ConsumptionIntent`
- [x] 5.2 Add `--show-raw` flag to data commands — includes raw record in JSON output
- [x] 5.3 Add `--show-provenance` flag to data commands — includes provenance chain in JSON output
- [x] 5.4 Add `anchors list` subcommand — lists all anchors for a calendar with pass/fail status
- [x] 5.5 Add `anchors validate` subcommand — accepts `--timestamp` and `--calendar`, returns temporal safety verdict
- [x] 5.6 Ensure default behavior (no flags) produces v1-compatible JSON output (normalized only)

## 6. Ops Extension

- [x] 6.1 Add `ops provenance verify` command — checks provenance chain completeness for specified symbols/date
- [x] 6.2 Add `ops raw-records stats` command — reports raw cache size, file count, breakdown by source and date
- [x] 6.3 Extend failover event recording in `core/db.py` — add `provenance_gap` boolean column; determine gap by whether primary source data was fully lost
- [x] 6.4 Extend `ops report` JSON output — include provenance verify summary, raw records stats, and provenance_gap failover counts

## 7. Config Extension (config.yaml)

- [x] 7.1 Add `anchors` section with `trading_session` sub-config containing t, t+5min, t+10min, t+15min anchors
- [x] 7.2 Add `cache.ttl.raw_record: 1d` to cache section
- [x] 7.3 Add `channel` section: `default_intent: realtime-decision` and `raw_cache_enabled: false` (default)

## 8. Public API (__init__.py)

- [x] 8.1 Update `Datakit.quote(symbols, intent=None)` — accepts optional intent, returns `FetchResult`
- [x] 8.2 Update `Datakit.klines(symbols, days, intent=None)` — same pattern
- [x] 8.3 Add `Datakit.anchors(calendar_name)` — returns `AnchorCalendar` instance
- [x] 8.4 Ensure `from datakit import Datakit, ConsumptionIntent, FetchResult, RawRecord, ProvenanceEntry` all work

## 9. Verify

- [ ] 9.1 Run `python -m datakit ops check --json` — all 3 adapters still healthy, output unchanged
- [x] 9.2 Run `python -m datakit quote --symbols 000001 --json` — output is v1-compatible (normalized only)
- [x] 9.3 Run `python -m datakit quote --symbols 000001 --intent audit --json --show-raw` — output includes raw and provenance keys
- [x] 9.4 Run `python -m datakit anchors list --calendar trading_session --json` — 4 anchors listed with correct times
- [x] 9.5 Run `python -m datakit ops provenance verify --date today --json` — no errors for fresh data
- [x] 9.6 Run existing engine node import test: `python -c "from datakit import Datakit; dk = Datakit(); r = dk.quote(['000001']); print(r.normalized['000001'].last_price)"` — works without code change
- [x] 9.7 Rebuild CodeGraph in the datakit workspace after its versioning boundary is confirmed
- [ ] 9.8 Sync datakit workspace git: commit all changes with message "feat: three-channel protocol — RawRecord + Provenance + ConsumptionRouter + ForwardAnchorCalendar"
