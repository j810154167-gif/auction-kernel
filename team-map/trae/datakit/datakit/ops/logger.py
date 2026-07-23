"""Structured JSON logger — appends newline-delimited JSON to daily log files."""

import json
import os
from datetime import datetime
from pathlib import Path


LOG_DIR = Path(__file__).resolve().parent.parent / "logs"


def _log_path(date_str: str | None = None) -> Path:
    """Get the log file path for a given date."""
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
    return LOG_DIR / f"{date_str}.jsonl"


def ops_log(event: str, level: str = "INFO", **kwargs) -> None:
    """Write a structured JSON log line to today's log file.

    Args:
        event: Event name (e.g., "health_check", "failover", "cache_hit")
        level: Log level (INFO, WARN, ERROR)
        **kwargs: Event-specific fields
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": datetime.now().isoformat(),
        "level": level,
        "event": event,
        **kwargs,
    }
    with open(_log_path(), "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")


def ops_log_silent(event: str, **kwargs) -> None:
    """Write log without printing to stdout (for quiet mode)."""
    ops_log(event, **kwargs)


def tail(n: int = 20, date_str: str | None = None) -> list[dict]:
    """Return the last N lines of today's log."""
    path = _log_path(date_str)
    if not path.exists():
        return []
    with open(path) as f:
        lines = f.readlines()
    recent = lines[-n:]
    result = []
    for line in recent:
        try:
            result.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return result


def read_date(date_str: str) -> list[dict]:
    """Read all log lines for a specific date."""
    path = _log_path(date_str)
    if not path.exists():
        return []
    result = []
    with open(path) as f:
        for line in f:
            try:
                result.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return result
