# consumption-router

## ADDED Requirements

### Requirement: ConsumptionIntent enum defines data view modes

The system SHALL define a `ConsumptionIntent` enum with at least four values: `REALTIME_DECISION`, `BACKTEST`, `AUDIT`, and `FULL_TRACE`.

#### Scenario: Intent values as strings

- **WHEN** `ConsumptionIntent.REALTIME_DECISION.value` is accessed
- **THEN** it returns `"realtime-decision"` for CLI compatibility

#### Scenario: Intent from string

- **WHEN** `python -m datakit quote --symbols 000001 --intent audit --json` is executed
- **THEN** the CLI parser maps `"audit"` to `ConsumptionIntent.AUDIT`

### Requirement: Router dispatches to correct data channel per intent

The Router SHALL select which channels (Raw, Normalized, Provenance) to populate based on the declared `ConsumptionIntent`.

#### Scenario: Realtime decision intent returns Normalized + Provenance

- **WHEN** `Datakit().quote("000001", intent=ConsumptionIntent.REALTIME_DECISION)` is called
- **THEN** `FetchResult.normalized` is populated (all quotes)
- **AND** `FetchResult.provenance` is populated (all provenance chains)
- **AND** `FetchResult.raw` is empty (excluded for latency)

#### Scenario: Full trace intent returns Raw + Provenance

- **WHEN** `Datakit().quote("000001", intent=ConsumptionIntent.FULL_TRACE)` is called
- **THEN** `FetchResult.raw` is populated (raw adapter responses)
- **AND** `FetchResult.provenance` is populated (full chains)
- **AND** `FetchResult.normalized` is populated (all three channels available)

#### Scenario: Backtest intent returns Normalized only

- **WHEN** `Datakit().klines(["000001"], intent=ConsumptionIntent.BACKTEST)` is called
- **THEN** `FetchResult.normalized` is populated
- **AND** `FetchResult.raw` is empty (not needed for backtest)
- **AND** `FetchResult.provenance` is empty (not needed for backtest)
- **AND** the response may use cached data even if cache is stale

#### Scenario: Audit intent returns Raw + Provenance

- **WHEN** `Datakit().quote("000001", intent=ConsumptionIntent.AUDIT)` is called
- **THEN** `FetchResult.raw` is populated with full adapter response
- **AND** `FetchResult.provenance` is populated
- **AND** cache is bypassed entirely (audit requires fresh data)

### Requirement: CLI supports --intent flag on all data commands

All data-fetching CLI commands SHALL accept a `--intent` flag that maps to `ConsumptionIntent`.

#### Scenario: Quote with full-trace intent

- **WHEN** `python -m datakit quote --symbols 000001 --intent full-trace --json` is executed
- **THEN** the JSON output includes `normalized`, `raw`, and `provenance` top-level keys

#### Scenario: Default intent is realtime-decision

- **WHEN** `python -m datakit quote --symbols 000001 --json` is executed without `--intent`
- **THEN** the system uses `ConsumptionIntent.REALTIME_DECISION` as default
- **AND** output is v1-compatible (normalized only)

### Requirement: Backward compatibility with v1 API

The existing `Datakit().quote()` and `Datakit().klines()` signatures without `intent` or `raw` parameters SHALL continue to work identically.

#### Scenario: v1 call unchanged

- **WHEN** existing engine code calls `dk.quote(["000001"])` (no intent parameter)
- **THEN** the return value is a `FetchResult`
- **AND** `result.normalized` contains the same data structure as v1's direct `{symbol: Quote}` return
- **AND** no code change is required in existing consumers

### Requirement: Router validates intent against supported channel operations

The Router SHALL validate that the selected adapter supports the required channels for the given intent, and fall back gracefully if not.

#### Scenario: Intent requires WS raw but adapter is REST-only

- **WHEN** `Datakit().quote("000001", intent=ConsumptionIntent.FULL_TRACE)` is called
- **AND** the active adapter is Eastmoney (REST only, no WS raw frame data)
- **THEN** `FetchResult.raw` is populated with the REST response (best available)
- **AND** `_provenance` includes a warning entry: `detail="raw: rest-only adapter, no WS raw frame available"`
