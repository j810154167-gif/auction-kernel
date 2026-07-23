# data-cache (delta)

## ADDED Requirements

### Requirement: Raw records are cachable in Parquet format

The system SHALL support storing raw adapter response records as Parquet files under `datakit/cache/raw/`.

#### Scenario: Raw record cache write

- **WHEN** an API call with intent that includes raw data (AUDIT or FULL_TRACE) fetches data
- **THEN** system writes `cache/raw/{source}_{date}_{hash}.parquet` with columns: `symbol, source, transport, ingest_ts, source_timestamp, network_latency_ms, raw_size_bytes, payload`

#### Scenario: Raw record cache TTL

- **WHEN** a raw record cache file is older than the configured TTL (default 1 day)
- **THEN** the cache entry is treated as stale and not returned on cache read
- **AND** stale entries are purged by the cache purge command

#### Scenario: Raw cache status report

- **WHEN** `python -m datakit cache status --json` is executed
- **THEN** the output includes `raw_cache` statistics: `{"file_count": N, "total_size_bytes": M, "oldest_entry": ..., "newest_entry": ...}`

### Requirement: Provenance metadata survives cache round-trip

When Normalized data is read from Parquet cache, the provenance chain SHALL be preserved and augmented with a cache_hit entry rather than lost.

#### Scenario: Cache write preserves provenance

- **WHEN** a `Quote` with `_provenance = [source_fetch, normalize, router_select]` is written to Parquet cache
- **THEN** the `_provenance` field is serialized as a JSON array in the Parquet column

#### Scenario: Cache read augments provenance

- **WHEN** a cached `Quote` is read from Parquet
- **THEN** a `ProvenanceEntry(step="cache_hit", actor="datakit.cache", ...)` is appended to `_provenance`
- **AND** the original source_fetch and normalize entries are preserved

## MODIFIED Requirements

### Requirement: Cache status is queryable

The system SHALL provide cache statistics via CLI, including separate breakdowns for normalized and raw caches.

#### Scenario: Cache status

- **WHEN** Agent runs `python -m datakit cache status --json`
- **THEN** system reports `{"normalized_cache": {"total_size_bytes": ..., "file_count": ..., "hit_rate_pct": ...}, "raw_cache": {"total_size_bytes": ..., "file_count": ..., "oldest_entry": ..., "newest_entry": ...}}`
