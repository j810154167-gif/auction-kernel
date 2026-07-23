# raw-record-channel

## ADDED Requirements

### Requirement: Adapter returns raw record alongside normalized data

Each adapter's `fetch_*()` method SHALL return a `RawRecord` for every symbol in the batch, preserving the adapter's original response before any normalization step.

#### Scenario: TickFlow REST quote with raw record

- **WHEN** `adapter.fetch_quotes(["000001"])` is called against TickFlow
- **THEN** the return value includes `raw["000001"]` as a `RawRecord` containing the original JSON payload from `GET /v1/quotes`
- **AND** `raw["000001"].ingest_ts` records the local ingestion timestamp with microsecond precision
- **AND** `raw["000001"].source` is `"tickflow"`
- **AND** `raw["000001"].source_timestamp` preserves the exchange timestamp from the API response if present, or `None` if absent

#### Scenario: Eastmoney HTTP with raw record

- **WHEN** `adapter.fetch_quotes(["000001"])` is called against Eastmoney
- **THEN** `raw["000001"].payload` contains the original JSON response from Eastmoney's push2 API
- **AND** `raw["000001"].network_latency_ms` records the round-trip time of the HTTP request

#### Scenario: WebSocket frame captured as raw record

- **WHEN** TickFlow WebSocket pushes a quote frame for symbol "000001"
- **THEN** a `RawRecord` is created with `source="tickflow"`, `transport="websocket"`
- **AND** `raw["000001"].payload` contains the raw WS message (JSON string)
- **AND** `raw["000001"].ingest_ts` records the local timestamp when the frame was received

### Requirement: RawRecord data model

The system SHALL define a `RawRecord` dataclass with the following fields: `symbol`, `source`, `transport` (http/websocket), `payload` (original response), `ingest_ts` (local time.time()), `source_timestamp` (optional exchange timestamp), `network_latency_ms` (optional), and `raw_size_bytes`.

#### Scenario: RawRecord immutability

- **WHEN** a `RawRecord` is created from adapter output
- **THEN** the instance is frozen and cannot be modified after creation

### Requirement: Raw records are transmitted only when requested

Raw records SHALL NOT be serialized or transmitted unless the caller explicitly requests them via intent or flag.

#### Scenario: Default behavior excludes raw

- **WHEN** `Datakit().quote("000001")` is called without `raw=True` or intent that requires raw
- **THEN** the `FetchResult.raw` dict is empty
- **AND** no raw record is serialized in CLI JSON output

#### Scenario: Audit intent includes raw

- **WHEN** `Datakit().quote("000001", intent=ConsumptionIntent.AUDIT)` is called
- **THEN** `FetchResult.raw["000001"]` is populated with the `RawRecord`

### Requirement: Raw records can be cached in Parquet

The system SHALL support storing raw records in `datakit/cache/raw/` as timestamped Parquet files.

#### Scenario: Raw cache write on audit intent

- **WHEN** an API call with `intent=AUDIT` fetches data
- **AND** raw cache is enabled in config
- **THEN** system writes `cache/raw/{source}_{date}_{symbols_hash}.parquet`
- **AND** the file TTL is 1 day (default)

#### Scenario: Raw cache is not written by default

- **WHEN** an API call with default intent fetches data
- **THEN** no raw record is written to cache
