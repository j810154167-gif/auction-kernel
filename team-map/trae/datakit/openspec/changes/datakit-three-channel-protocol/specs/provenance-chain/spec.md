# provenance-chain

## ADDED Requirements

### Requirement: Every normalized record carries a provenance chain

Each `Quote`, `Kline`, and `BlockInfo` instance returned by datakit SHALL carry a `_provenance` field containing the complete processing lineage as a `frozenset[ProvenanceEntry]`.

#### Scenario: Provenance chain on fresh fetch

- **WHEN** `Datakit().quote("000001")` fetches data from TickFlow (no cache hit)
- **THEN** `result.normalized["000001"]._provenance` contains at least:
  - `ProvenanceEntry(step="source_fetch", actor="tickflow", ...)`
  - `ProvenanceEntry(step="normalize", actor="datakit.normalizer", ...)`
  - `ProvenanceEntry(step="router_select", actor="datakit.router", ...)`

#### Scenario: Provenance chain on cache hit

- **WHEN** `Datakit().klines(["000001"])` returns cached data from Parquet
- **THEN** `_provenance` includes `ProvenanceEntry(step="cache_hit", actor="datakit.cache", detail="cache/kline_daily/2026-07-07.parquet")`
- **AND** the original source fetch entry from when the cache was populated is preserved

#### Scenario: Provenance chain on failover

- **WHEN** TickFlow times out and Router fails over to Eastmoney
- **THEN** `_provenance` includes:
  - `ProvenanceEntry(step="source_error", actor="tickflow", detail="timeout 5000ms")`
  - `ProvenanceEntry(step="source_fetch", actor="eastmoney", ...)`
  - `ProvenanceEntry(step="failover", actor="datakit.router", detail="tickflow → eastmoney")`

### Requirement: ProvenanceEntry data model

The system SHALL define a `ProvenanceEntry` frozen dataclass with fields: `step` (enumeration of processing stages), `actor` (component name), `timestamp` (float, time.time()), and `detail` (human-readable string).

#### Scenario: ProvenanceEntry immutability

- **WHEN** a `ProvenanceEntry` is created
- **THEN** all fields are frozen and cannot be modified after creation

#### Scenario: ProvenanceEntry hashing

- **WHEN** two `ProvenanceEntry` instances with identical fields are compared
- **THEN** they are hash-equal and can coexist in a `frozenset`

### Requirement: Provenance chain survives serialization

The provenance chain SHALL be preserved when data is serialized to JSON (for Agent consumption) or written to Parquet cache.

#### Scenario: CLI JSON output includes provenance

- **WHEN** `python -m datakit quote --symbols 000001 --json --show-provenance` is executed
- **THEN** the JSON output includes a `_provenance` array under each symbol: `[{"step": ..., "actor": ..., "timestamp": ..., "detail": ...}]`

#### Scenario: Default CLI output excludes provenance

- **WHEN** `python -m datakit quote --symbols 000001 --json` is executed without `--show-provenance`
- **THEN** the JSON output does NOT include `_provenance` fields (v1 compatible)

### Requirement: Provenance verification via ops command

The system SHALL provide `ops provenance verify` to check the integrity of provenance chains across a dataset.

#### Scenario: Verify clean chain

- **WHEN** `python -m datakit ops provenance verify --symbols 000001 --json` is executed
- **THEN** system checks that every `_provenance` chain for the given symbols has no gaps, no duplicate steps, and all mandatory steps present
- **AND** reports `{"verified": 1, "warnings": 0}` for a clean chain

#### Scenario: Detect provenance gap

- **WHEN** a provenance chain is missing the `source_fetch` step (e.g., data was injected without adapter call)
- **THEN** verify reports `{"verified": 1, "warnings": 1, "warnings_detail": [{"symbol": "000001", "issue": "missing step: source_fetch"}]}`
