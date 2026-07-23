# ops-workflows (delta)

## ADDED Requirements

### Requirement: Provenance verification command

The system SHALL provide `ops provenance verify` to audit the integrity of provenance chains across stored data.

#### Scenario: Verify provenance of current day data

- **WHEN** `python -m datakit ops provenance verify --date today --json` is executed
- **THEN** system checks all cached data for today, verifies every record has a complete provenance chain
- **AND** reports `{"total_records": N, "verified": M, "warnings": W}` with per-symbol details for any gaps

#### Scenario: Verify provenance with specific symbols

- **WHEN** `python -m datakit ops provenance verify --symbols 000001,000002 --json` is executed
- **THEN** system checks provenance chains only for the specified symbols

### Requirement: Raw records statistics command

The system SHALL provide `ops raw-records stats` to report on accumulated raw data storage.

#### Scenario: Raw records stats

- **WHEN** `python -m datakit ops raw-records stats --json` is executed
- **THEN** output includes: `{"total_files": N, "total_size_bytes": M, "by_source": {"tickflow": {"files": 5, "size_bytes": ...}, "eastmoney": {...}}, "by_date": {"2026-07-10": {...}}}`

### Requirement: Failover events include provenance gap flag

Failover events recorded in `failover_events` SHALL include a `provenance_gap` boolean indicating whether the failover introduced a gap in the provenance chain (i.e., the primary source's data was lost entirely rather than just unavailable).

#### Scenario: Failover with provenance gap

- **WHEN** TickFlow WS disconnects mid-stream and Router fails over to Eastmoney REST
- **THEN** the failover event includes `provenance_gap: true`
- **AND** detail field notes "WS disconnect → REST fallback, raw frames from disconnected period unavailable"

#### Scenario: Failover without provenance gap

- **WHEN** TickFlow REST times out once and Router retries Eastmoney (both REST, same data structure)
- **THEN** the failover event includes `provenance_gap: false`
- **AND** detail field notes "REST timeout, full retry via Eastmoney, no data loss"

## MODIFIED Requirements

### Requirement: Daily ops report generation

The system SHALL provide `ops report` to generate a structured daily status summary that includes provenance and raw record metrics.

#### Scenario: Generate report

- **WHEN** `python -m datakit ops report --date 2026-07-10 --json` is executed
- **THEN** system outputs JSON containing: per-source uptime, total failover events (including provenance gap counts), quota consumed, cache hit rates (normalized + raw), provenance verify summary, and error count
