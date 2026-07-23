"""SQLite connection manager with auto-migration.

Manages datakit.db with tables:
  - health_log: per-source health check history
  - quota_ledger: per-source per-endpoint API call counts
  - failover_events: automatic failover records
  - ops_journal: operational event summary
"""

import sqlite3
import os
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock


_DB_PATH: Path | None = None
_RETENTION_DAYS = 30
_lock = Lock()


def init(db_path: str | Path | None = None) -> None:
    """Initialise the database. Called once on startup."""
    global _DB_PATH
    if db_path is None:
        db_path = Path(__file__).resolve().parent.parent / "datakit.db"
    _DB_PATH = Path(db_path)
    _migrate()


def _migrate() -> None:
    """Create tables if they don't exist."""
    assert _DB_PATH is not None
    with _lock:
        conn = sqlite3.connect(str(_DB_PATH))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(_SCHEMA)
        columns = {row[1] for row in conn.execute("PRAGMA table_info(failover_events)").fetchall()}
        if "provenance_gap" not in columns:
            conn.execute("ALTER TABLE failover_events ADD COLUMN provenance_gap INTEGER NOT NULL DEFAULT 0")
        conn.commit()
        conn.close()


def _get_conn() -> sqlite3.Connection:
    assert _DB_PATH is not None
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def insert_health(source: str, reachable: bool, latency_ms: int, error: str | None = None) -> None:
    """Record a health check result."""
    conn = _get_conn()
    conn.execute(
        "INSERT INTO health_log (ts, source, reachable, latency_ms, error) VALUES (?, ?, ?, ?, ?)",
        (datetime.now().isoformat(), source, int(reachable), latency_ms, error),
    )
    conn.commit()
    conn.close()


def insert_failover(
    from_source: str,
    to_source: str,
    reason: str,
    symbols: str = "",
    provenance_gap: bool = False,
) -> None:
    """Record a failover event."""
    conn = _get_conn()
    conn.execute(
        "INSERT INTO failover_events (ts, from_source, to_source, reason, affected_symbols, provenance_gap) VALUES (?, ?, ?, ?, ?, ?)",
        (datetime.now().isoformat(), from_source, to_source, reason, symbols, int(provenance_gap)),
    )
    conn.commit()
    conn.close()


def upsert_quota(source: str, endpoint: str, calls: int = 1, remaining: int | None = None) -> None:
    """Increment call count for (date, source, endpoint). Optionally update remaining."""
    date = datetime.now().strftime("%Y-%m-%d")
    conn = _get_conn()
    existing = conn.execute(
        "SELECT calls, remaining FROM quota_ledger WHERE date=? AND source=? AND endpoint=?",
        (date, source, endpoint),
    ).fetchone()
    if existing:
        new_calls = existing["calls"] + calls
        new_remaining = remaining if remaining is not None else existing["remaining"]
        conn.execute(
            "UPDATE quota_ledger SET calls=?, remaining=? WHERE date=? AND source=? AND endpoint=?",
            (new_calls, new_remaining, date, source, endpoint),
        )
    else:
        new_calls = calls
        new_remaining = remaining
        conn.execute(
            "INSERT INTO quota_ledger (date, source, endpoint, calls, remaining) VALUES (?, ?, ?, ?, ?)",
            (date, source, endpoint, new_calls, new_remaining),
        )
    conn.commit()
    conn.close()


def get_quota_remaining(source: str) -> int | None:
    """Get remaining quota for a source (minimum across all endpoints)."""
    date = datetime.now().strftime("%Y-%m-%d")
    conn = _get_conn()
    rows = conn.execute(
        "SELECT remaining FROM quota_ledger WHERE date=? AND source=? AND remaining IS NOT NULL",
        (date, source),
    ).fetchall()
    conn.close()
    if not rows:
        return None
    vals = [r["remaining"] for r in rows if r["remaining"] is not None]
    return min(vals) if vals else None


def is_quota_exhausted(source: str) -> bool:
    """Check if any endpoint for this source has 0 remaining."""
    remaining = get_quota_remaining(source)
    return remaining is not None and remaining <= 0


def insert_ops_journal(level: str, event: str, detail: str = "") -> None:
    """Record an operational event summary."""
    conn = _get_conn()
    conn.execute(
        "INSERT INTO ops_journal (ts, level, event, detail) VALUES (?, ?, ?, ?)",
        (datetime.now().isoformat(), level, event, detail),
    )
    conn.commit()
    conn.close()


def get_health_summary(date: str | None = None) -> list[dict]:
    """Get health check summary for a date."""
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    conn = _get_conn()
    rows = conn.execute(
        "SELECT source, reachable, latency_ms, error, ts FROM health_log WHERE date(ts)=? ORDER BY ts DESC",
        (date,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_failover_count(date: str | None = None) -> int:
    """Count failover events for a date."""
    return get_failover_summary(date)["total"]


def get_failover_summary(date: str | None = None) -> dict:
    """Summarize failover events and provenance gaps for a date."""
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    conn = _get_conn()
    row = conn.execute(
        "SELECT COUNT(*) as total, SUM(provenance_gap) as provenance_gap_count FROM failover_events WHERE date(ts)=?",
        (date,),
    ).fetchone()
    conn.close()
    return {
        "total": row["total"] if row else 0,
        "provenance_gap_count": int(row["provenance_gap_count"] or 0) if row else 0,
    }


def prune_old_records() -> int:
    """Delete records older than RETENTION_DAYS. Returns number of deleted rows."""
    cutoff = (datetime.now() - timedelta(days=_RETENTION_DAYS)).isoformat()
    total = 0
    conn = _get_conn()
    for table in ("health_log", "ops_journal", "failover_events"):
        cur = conn.execute(f"DELETE FROM {table} WHERE ts < ?", (cutoff,))
        total += cur.rowcount
    conn.commit()
    conn.close()
    return total


_SCHEMA = """
CREATE TABLE IF NOT EXISTS health_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    source TEXT NOT NULL,
    reachable INTEGER NOT NULL,
    latency_ms INTEGER NOT NULL,
    error TEXT
);
CREATE INDEX IF NOT EXISTS idx_health_ts ON health_log(ts);
CREATE INDEX IF NOT EXISTS idx_health_source ON health_log(source);

CREATE TABLE IF NOT EXISTS quota_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    source TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    calls INTEGER NOT NULL DEFAULT 0,
    remaining INTEGER,
    UNIQUE(date, source, endpoint)
);
CREATE INDEX IF NOT EXISTS idx_quota_lookup ON quota_ledger(date, source);

CREATE TABLE IF NOT EXISTS failover_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    from_source TEXT NOT NULL,
    to_source TEXT NOT NULL,
    reason TEXT NOT NULL,
    affected_symbols TEXT DEFAULT '',
    provenance_gap INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_failover_ts ON failover_events(ts);

CREATE TABLE IF NOT EXISTS ops_journal (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    level TEXT NOT NULL,
    event TEXT NOT NULL,
    detail TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_journal_ts ON ops_journal(ts);
"""
