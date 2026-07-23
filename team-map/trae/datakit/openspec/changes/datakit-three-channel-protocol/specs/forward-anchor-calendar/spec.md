# forward-anchor-calendar

## ADDED Requirements

### Requirement: Config-driven anchor calendar

The system SHALL read forward anchor definitions from `datakit/config.yaml` under an `anchors` section, with each anchor having a `label`, `time`, and `tz` field.

#### Scenario: Load trading session anchors

- **WHEN** `datakit/config.yaml` contains:
  ```yaml
  anchors:
    trading_session:
      - { label: "T+0",    time: "09:15", tz: "Asia/Shanghai" }
      - { label: "T+5min", time: "09:20", tz: "Asia/Shanghai" }
  ```
- **THEN** `AnchorCalendar("trading_session")` loads two anchor points
- **AND** each anchor's time is parsed as `datetime.time` in the specified timezone

#### Scenario: Missing anchors section

- **WHEN** `config.yaml` has no `anchors` section
- **THEN** `AnchorCalendar` returns an empty calendar
- **AND** all temporal validation methods return `None` (no constraint applied)

### Requirement: Next anchor query

The system SHALL provide `AnchorCalendar.next_anchor()` that returns the chronologically next, not-yet-passed anchor.

#### Scenario: Before first anchor

- **WHEN** current time is 09:10 Asia/Shanghai and the calendar has anchors at 09:15, 09:20, 09:25
- **THEN** `calendar.next_anchor()` returns the 09:15 anchor with `label="T+0"`

#### Scenario: Between anchors

- **WHEN** current time is 09:22 Asia/Shanghai
- **THEN** `calendar.next_anchor()` returns the 09:25 anchor (09:20 has already passed)

#### Scenario: After all anchors

- **WHEN** current time is 09:40 Asia/Shanghai
- **THEN** `calendar.next_anchor()` returns `None` (all anchors have passed)

### Requirement: Temporal validation against anchors

The system SHALL provide `AnchorCalendar.validate_temporal(data_timestamp, anchor_label)` that checks whether a data record's timestamp is consistent with the calendar — specifically, data SHALL NOT carry a timestamp from after any not-yet-reached anchor.

#### Scenario: Valid data before anchor

- **WHEN** a data record has `timestamp_ms = 09:14:50` and the next anchor is 09:15
- **THEN** `validate_temporal(09:14:50, "T+0")` returns `(True, None)` — data arrived before the anchor, legitimate

#### Scenario: Future data before anchor (look-ahead violation)

- **WHEN** a data record has `timestamp_ms = 09:15:02` and the current time is 09:14:58
- **THEN** `validate_temporal` returns `(False, "data_timestamp 09:15:02 exceeds next anchor 09:15 at current time 09:14:58")`
- **AND** the caller SHALL block consumption of this record

#### Scenario: No anchors configured

- **WHEN** `validate_temporal` is called on a calendar with no anchors
- **THEN** returns `(True, None)` — no constraint, pass-through

### Requirement: Current window query

The system SHALL provide `AnchorCalendar.current_window()` that returns the current position relative to defined anchors, without prescribing business-specific window names.

#### Scenario: Before first anchor

- **WHEN** current time is 09:08 Asia/Shanghai and the first anchor is 09:15
- **THEN** `calendar.current_window()` returns `{"position": "before_first", "next_anchor": {"label": "T+0", "time": "09:15"}}`

#### Scenario: Between anchors

- **WHEN** current time is 09:18 Asia/Shanghai
- **THEN** `calendar.current_window()` returns `{"position": "between", "prev_anchor": {"label": "T+0", "time": "09:15"}, "next_anchor": {"label": "T+5min", "time": "09:20"}}`

#### Scenario: After last anchor

- **WHEN** current time is 09:35 Asia/Shanghai
- **THEN** `calendar.current_window()` returns `{"position": "after_last", "prev_anchor": {"label": "T+15min", "time": "09:30"}}`

### Requirement: CLI exposes anchor calendar operations

The system SHALL provide CLI commands to query the anchor calendar state.

#### Scenario: CLI list anchors

- **WHEN** `python -m datakit anchors list --calendar trading_session --json` is executed
- **THEN** output is a JSON array of anchor objects: `[{"label": "T+0", "time": "09:15", "passed": true}, ...]`

#### Scenario: CLI check temporal safety

- **WHEN** `python -m datakit anchors validate --timestamp "2026-07-10T09:14:50+08:00" --calendar trading_session --json` is executed
- **THEN** output includes `{"valid": true, "position": "before_first", "next_anchor": "T+0"}`

### Requirement: Anchor calendar is timezone-aware

All anchor time comparisons SHALL use the timezone specified in the anchor definition (or system timezone if not specified).

#### Scenario: Cross-timezone check

- **WHEN** an anchor is defined with `tz: "Asia/Shanghai"` and the system clock is in UTC
- **THEN** the anchor time is compared against `datetime.now(ZoneInfo("Asia/Shanghai"))`
- **AND** DST transitions are handled correctly by the zoneinfo database
