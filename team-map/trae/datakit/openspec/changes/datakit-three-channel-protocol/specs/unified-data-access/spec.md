# unified-data-access (delta)

## ADDED Requirements

### Requirement: Data fetch returns three-channel FetchResult

The `Datakit().quote()`, `Datakit().klines()`, and `Datakit().blocks()` methods SHALL return a `FetchResult` object containing `normalized`, `raw`, and `provenance` views, instead of directly returning `{symbol: Quote}`.

#### Scenario: FetchResult provides normalized access identical to v1

- **WHEN** engine code calls `result = dk.quote(["000001"])` and accesses `result.normalized`
- **THEN** `result.normalized` is a `dict[str, Quote]` with the same structure as v1's direct return value
- **AND** all existing engine node code that accesses `result.normalized["000001"].last_price` works without modification

#### Scenario: FetchResult provides raw access when requested

- **WHEN** `result = dk.quote(["000001"], intent=ConsumptionIntent.AUDIT)` is called
- **THEN** `result.raw["000001"]` is a `RawRecord` containing the adapter's original response

#### Scenario: FetchResult provides provenance access when requested

- **WHEN** `result = dk.quote(["000001"], intent=ConsumptionIntent.FULL_TRACE)` is called
- **THEN** `result.provenance["000001"]` is a `list[ProvenanceEntry]` with the full processing chain

### Requirement: CLI --show-raw and --show-provenance flags

Data-fetching CLI commands SHALL accept `--show-raw` and `--show-provenance` flags to include additional channels in JSON output.

#### Scenario: CLI with raw flag

- **WHEN** `python -m datakit quote --symbols 000001 --json --show-raw` is executed
- **THEN** the JSON output includes a top-level `raw` key with raw record data
- **AND** the `normalized` key is still present (v1 compatible structure)

#### Scenario: CLI with provenance flag

- **WHEN** `python -m datakit kline --symbols 000001 --days 2 --json --show-provenance` is executed
- **THEN** the JSON output includes `_provenance` arrays under each K-line entry

## MODIFIED Requirements

### Requirement: Unified quote interface with automatic failover

The system SHALL provide a single `quote(symbols, intent=ConsumptionIntent.REALTIME_DECISION)` entry point that routes to the best available source according to the configured fallback chain and declared consumption intent.

#### Scenario: Primary source healthy

- **WHEN** `Datakit().quote(["000001", "000002"])` is called and TickFlow is healthy
- **THEN** system fetches quotes from TickFlow and returns a `FetchResult` with `normalized` populated as `{symbol: Quote}` within 2 seconds

#### Scenario: Primary source fails, falls back

- **WHEN** TickFlow times out or returns error
- **THEN** system logs a failover event to `datakit.db` → `failover_events`
- **AND** system retries the same request via Eastmoney adapter
- **AND** returns the Eastmoney result as a `FetchResult` without error
- **AND** `result.provenance` includes the failover step

#### Scenario: All sources fail

- **WHEN** all sources in the fallback chain are unreachable
- **THEN** system raises `AllSourcesFailed("quote", symbols)` with details of each source's failure

### Requirement: Python API returns typed objects in FetchResult

The Python API SHALL return a `FetchResult` object whose `normalized` dict contains `Quote`, `Kline`, and `BlockInfo` dataclass instances (not raw dicts) for type safety. The `raw` dict contains `RawRecord` instances when populated.

#### Scenario: Type-safe quote access

- **WHEN** engine code calls `dk = Datakit(); result = dk.quote(["000001"])`
- **THEN** `result` is a `FetchResult` instance
- **AND** `result.normalized["000001"]` is a `Quote` instance with typed fields
- **AND** `result.raw` is empty by default (no performance penalty)
