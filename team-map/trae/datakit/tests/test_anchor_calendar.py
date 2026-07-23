from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

import yaml

from datakit.core.calendar import AnchorCalendar


SHANGHAI = ZoneInfo("Asia/Shanghai")


def _write_config(tmp_path, anchors=None):
    config = {} if anchors is None else {"anchors": {"trading_session": anchors}}
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    return path


def _clock(hour, minute, second=0):
    instant = datetime(2026, 7, 10, hour, minute, second, tzinfo=SHANGHAI)
    return lambda tz: instant.astimezone(tz)


def _anchors():
    return [
        {"label": "T+0", "time": "09:15", "tz": "Asia/Shanghai"},
        {"label": "T+5min", "time": "09:20", "tz": "Asia/Shanghai"},
        {"label": "T+10min", "time": "09:25", "tz": "Asia/Shanghai"},
    ]


def test_calendar_loads_and_sorts_configured_timezone_aware_anchors(tmp_path):
    path = _write_config(tmp_path, list(reversed(_anchors())))

    calendar = AnchorCalendar("trading_session", config_path=path)

    assert [anchor.label for anchor in calendar.anchors] == ["T+0", "T+5min", "T+10min"]
    assert calendar.anchors[0].time == time(9, 15, tzinfo=SHANGHAI)


def test_missing_calendar_is_empty_and_applies_no_constraint(tmp_path):
    calendar = AnchorCalendar("trading_session", config_path=_write_config(tmp_path))

    assert calendar.anchors == []
    assert calendar.next_anchor() is None
    assert calendar.current_window() is None
    assert calendar.validate_temporal(datetime(2026, 7, 10, tzinfo=timezone.utc), "T+0") == (
        True,
        None,
    )


def test_next_anchor_uses_anchor_timezone(tmp_path):
    path = _write_config(tmp_path, _anchors())

    before = AnchorCalendar("trading_session", config_path=path, clock=_clock(9, 10))
    between = AnchorCalendar("trading_session", config_path=path, clock=_clock(9, 22))
    after = AnchorCalendar("trading_session", config_path=path, clock=_clock(9, 40))

    assert before.next_anchor().label == "T+0"
    assert between.next_anchor().label == "T+10min"
    assert after.next_anchor() is None


def test_validate_temporal_rejects_future_data_before_anchor(tmp_path):
    calendar = AnchorCalendar(
        "trading_session",
        config_path=_write_config(tmp_path, _anchors()),
        clock=_clock(9, 14, 58),
    )

    assert calendar.validate_temporal(
        datetime(2026, 7, 10, 9, 14, 50, tzinfo=SHANGHAI), "T+0"
    ) == (True, None)
    assert calendar.validate_temporal(
        datetime(2026, 7, 10, 9, 15, 2, tzinfo=SHANGHAI), "T+0"
    ) == (
        False,
        "data_timestamp 09:15:02 exceeds next anchor 09:15 at current time 09:14:58",
    )


def test_current_window_reports_generic_anchor_position(tmp_path):
    path = _write_config(tmp_path, _anchors())

    assert AnchorCalendar(
        "trading_session", config_path=path, clock=_clock(9, 8)
    ).current_window() == {
        "position": "before_first",
        "next_anchor": {"label": "T+0", "time": "09:15"},
    }
    assert AnchorCalendar(
        "trading_session", config_path=path, clock=_clock(9, 18)
    ).current_window() == {
        "position": "between",
        "prev_anchor": {"label": "T+0", "time": "09:15"},
        "next_anchor": {"label": "T+5min", "time": "09:20"},
    }
    assert AnchorCalendar(
        "trading_session", config_path=path, clock=_clock(9, 35)
    ).current_window() == {
        "position": "after_last",
        "prev_anchor": {"label": "T+10min", "time": "09:25"},
    }


def test_repository_config_defines_task_7_1_trading_session_anchors():
    calendar = AnchorCalendar("trading_session")

    assert [(anchor.label, anchor.time.strftime("%H:%M")) for anchor in calendar.anchors] == [
        ("T+0", "09:15"),
        ("T+5min", "09:20"),
        ("T+10min", "09:25"),
        ("T+15min", "09:30"),
    ]
