"""Quota ledger — track API call counts and detect exhaustion."""

from datakit.core import db


class QuotaLedger:
    """Track API calls per (date, source, endpoint)."""

    @staticmethod
    def record_call(source: str, endpoint: str, calls: int = 1) -> None:
        """Increment call count for a source+endpoint."""
        db.upsert_quota(source, endpoint, calls=calls)

    @staticmethod
    def record_remaining(source: str, endpoint: str, remaining: int) -> None:
        """Update remaining quota from API response headers."""
        db.upsert_quota(source, endpoint, calls=0, remaining=remaining)

    @staticmethod
    def get_remaining(source: str) -> int | None:
        """Get minimum remaining quota across all endpoints for a source."""
        return db.get_quota_remaining(source)

    @staticmethod
    def is_exhausted(source: str) -> bool:
        """Check if any endpoint has 0 remaining quota."""
        return db.is_quota_exhausted(source)

    @staticmethod
    def summary() -> dict:
        """Get quota summary for today."""
        from datetime import datetime
        date = datetime.now().strftime("%Y-%m-%d")
        conn = db._get_conn()
        rows = conn.execute(
            "SELECT source, endpoint, calls, remaining FROM quota_ledger WHERE date=?",
            (date,),
        ).fetchall()
        conn.close()
        result = {}
        for r in rows:
            src = r["source"]
            if src not in result:
                result[src] = {"endpoints": {}, "total_calls": 0}
            result[src]["endpoints"][r["endpoint"]] = {
                "calls": r["calls"],
                "remaining": r["remaining"],
            }
            result[src]["total_calls"] += r["calls"]
        return result
