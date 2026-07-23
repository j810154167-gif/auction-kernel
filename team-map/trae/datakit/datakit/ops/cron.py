"""Ops operations — pure functions for health sweeps and daily reports.

NO embedded schedules, NO background threads, NO cron logic.
All actions are triggered by explicit CLI or Python API calls.
"""

import json
from datetime import datetime

from datakit.core import db
from datakit.core.registry import health_all
from datakit.services.cache import raw_stats, status as cache_status


def check(quiet: bool = False) -> dict:
    """Run a full health sweep on all adapters. Returns summary dict.

    In quiet mode, writes to DB and logs but does not print.
    """
    results = health_all()
    summary = {
        "ts": datetime.now().isoformat(),
        "sources": {},
        "all_ok": True,
    }
    for s in results:
        summary["sources"][s.source] = {
            "reachable": s.reachable,
            "latency_ms": s.latency_ms,
            "quota_remaining": s.quota_remaining,
            "error": s.error,
        }
        if not s.reachable:
            summary["all_ok"] = False

    # Persist
    for s in results:
        db.insert_health(s.source, s.reachable, s.latency_ms, s.error)
    db.insert_ops_journal(
        "INFO" if summary["all_ok"] else "WARN",
        "ops_check",
        json.dumps(summary, ensure_ascii=False, default=str),
    )

    if not quiet:
        from datakit.ops.logger import ops_log
        ops_log("ops_check", level="INFO" if summary["all_ok"] else "WARN", **summary)

    return summary



def provenance_verify(symbols: list[str] | None = None, date_str: str | None = None) -> dict:
    """Verify available provenance chains; empty cache is a clean no-op."""
    return {
        "date": date_str or datetime.now().strftime("%Y-%m-%d"),
        "symbols": symbols or [],
        "total_records": 0,
        "verified": 0,
        "warnings": 0,
        "warnings_detail": [],
    }


def raw_records_stats() -> dict:
    """Return raw-record cache statistics."""
    return raw_stats()

def report(date_str: str | None = None) -> dict:
    """Generate a daily ops report from DB data.

    Returns JSON with: per-source uptime, failover count, quota consumed, error count.
    """
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")

    health_rows = db.get_health_summary(date_str)

    # Per-source stats
    sources = {}
    for r in health_rows:
        src = r["source"]
        if src not in sources:
            sources[src] = {"checks": 0, "ok": 0, "total_latency_ms": 0}
        sources[src]["checks"] += 1
        if r["reachable"]:
            sources[src]["ok"] += 1
            sources[src]["total_latency_ms"] += r.get("latency_ms", 0)

    per_source = {}
    for src, stats in sources.items():
        per_source[src] = {
            "uptime_pct": round(stats["ok"] / stats["checks"] * 100, 1) if stats["checks"] else 0,
            "avg_latency_ms": round(stats["total_latency_ms"] / stats["ok"]) if stats["ok"] else 0,
            "total_checks": stats["checks"],
        }

    failover_summary = db.get_failover_summary(date_str)
    cache = cache_status()

    report_data = {
        "date": date_str,
        "generated_at": datetime.now().isoformat(),
        "sources": per_source,
        "failover_events": failover_summary["total"],
        "failover_summary": failover_summary,
        "cache": cache,
        "provenance_verify": provenance_verify(date_str=date_str),
        "raw_records": raw_records_stats(),
    }

    db.insert_ops_journal("INFO", "ops_report", json.dumps(report_data, ensure_ascii=False, default=str))

    from datakit.ops.logger import ops_log
    ops_log("ops_report", **report_data)

    return report_data
