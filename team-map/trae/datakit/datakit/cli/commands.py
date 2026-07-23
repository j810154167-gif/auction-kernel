"""CLI commands for datakit — full command tree.

All data commands output --json by default.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from datakit.core.registry import list_all, get, health_all
from datakit.core.engine import Router
from datakit.core.calendar import AnchorCalendar
from datakit.core.types import ConsumptionIntent
from datakit.core import db
from datakit.services.cache import status as cache_status, warm as cache_warm, purge as cache_purge
from datakit.ops.cron import check as ops_check, provenance_verify, raw_records_stats, report as ops_report
from datakit.ops.logger import tail as log_tail
from datakit.inject import key_status, key_injection_guide


def _json_out(obj) -> None:
    """Print JSON to stdout."""
    print(json.dumps(obj, ensure_ascii=False, indent=2, default=str))



def _intent(value: str | None):
    if not value:
        return None
    aliases = {"realtime": "realtime-decision", "realtime-decision": "realtime-decision", "backtest": "backtest", "audit": "audit", "full-trace": "full-trace"}
    return ConsumptionIntent(aliases.get(value, value))


def _symbols(value: str) -> list[str]:
    symbols = []
    for item in value.split(","):
        symbol = item.strip()
        if not symbol:
            continue
        if symbol.isdigit() and len(symbol) == 6:
            suffix = ".SH" if symbol.startswith("6") else ".SZ"
            symbol = f"{symbol}{suffix}"
        symbols.append(symbol)
    return symbols


def _provenance_json(entries) -> list[dict]:
    return [entry.__dict__ for entry in entries]


def _raw_json(record) -> dict:
    return {
        "symbol": record.symbol,
        "source": record.source,
        "transport": record.transport,
        "payload": record.payload,
        "ingest_ts": record.ingest_ts,
        "source_timestamp": record.source_timestamp,
        "network_latency_ms": record.network_latency_ms,
        "raw_size_bytes": record.raw_size_bytes,
    }


def _quote_json(q, show_provenance: bool = False) -> dict:
    item = {
        "symbol": q.symbol,
        "name": q.name,
        "last_price": q.last_price,
        "open": q.open,
        "high": q.high,
        "low": q.low,
        "volume": q.volume,
        "amount": q.amount,
        "prev_close": q.prev_close,
        "change_pct": q.change_pct,
        "timestamp_ms": q.timestamp_ms,
        "source": q.source,
    }
    if show_provenance:
        item["_provenance"] = _provenance_json(q._provenance)
    return item


def _kline_json(b, show_provenance: bool = False) -> dict:
    item = {
        "date": b.date,
        "open": b.open,
        "high": b.high,
        "low": b.low,
        "close": b.close,
        "volume": b.volume,
        "amount": b.amount,
    }
    if show_provenance:
        item["_provenance"] = _provenance_json(b._provenance)
    return item


def _fetch_output(result, normalized, args) -> dict:
    output = normalized
    intent = _intent(getattr(args, "intent", None))
    include_raw = getattr(args, "show_raw", False)
    include_provenance = getattr(args, "show_provenance", False) or (include_raw and intent in (ConsumptionIntent.AUDIT, ConsumptionIntent.FULL_TRACE))
    if include_raw or include_provenance:
        output = {"normalized": normalized}
        if include_raw:
            output["raw"] = {symbol: _raw_json(record) for symbol, record in result.raw.items()}
        if include_provenance:
            output["provenance"] = {symbol: _provenance_json(entries) for symbol, entries in result.provenance.items()}
    return output

def _init_db() -> None:
    """Ensure DB is initialised before any command that touches it."""
    db_dir = Path(__file__).resolve().parent.parent
    db.init(db_dir / "datakit.db")


def cmd_registry(args) -> int:
    """registry list | show <name>"""
    if args.action == "list":
        _json_out(list_all())
    elif args.action == "show":
        try:
            adapter = get(args.name)
            info = {
                "name": adapter.name,
                "display_name": adapter.display_name,
                "supports_ws": adapter.supports_ws,
                "requires_auth": adapter.requires_auth,
            }
            if adapter.requires_auth:
                info["key_env_vars"] = adapter.key_env_vars
                info["key_injection_hint"] = adapter.key_injection_hint
            _json_out(info)
        except KeyError as e:
            print(str(e), file=sys.stderr)
            return 1
    return 0


def cmd_health(args) -> int:
    """health --all | --source <name>"""
    _init_db()
    if args.all:
        results = health_all()
        output = []
        for s in results:
            output.append({
                "source": s.source,
                "reachable": s.reachable,
                "latency_ms": s.latency_ms,
                "quota_remaining": s.quota_remaining,
                "error": s.error,
            })
            db.insert_health(s.source, s.reachable, s.latency_ms, s.error)
        _json_out(output)
    elif args.source:
        adapter = get(args.source)
        status = asyncio.run(adapter.health_check())
        db.insert_health(status.source, status.reachable, status.latency_ms, status.error)
        _json_out({
            "source": status.source,
            "reachable": status.reachable,
            "latency_ms": status.latency_ms,
            "quota_remaining": status.quota_remaining,
            "error": status.error,
        })
    return 0


def cmd_quote(args) -> int:
    """quote --symbols A,B,C [--source auto]"""
    _init_db()
    router = Router()
    symbols = _symbols(args.symbols)
    if not symbols:
        print("error: no symbols provided", file=sys.stderr)
        return 1
    try:
        result = asyncio.run(router.quote(symbols, intent=_intent(getattr(args, "intent", None))))
        normalized = {sym: _quote_json(q, getattr(args, "show_provenance", False)) for sym, q in result.normalized.items()}
        _json_out(_fetch_output(result, normalized, args))
    except Exception as e:
        _json_out({"error": str(e)})
        return 1
    return 0


def cmd_kline(args) -> int:
    """kline --symbols A,B,C [--days 2]"""
    _init_db()
    router = Router()
    symbols = _symbols(args.symbols)
    if not symbols:
        print("error: no symbols provided", file=sys.stderr)
        return 1
    try:
        result = asyncio.run(router.klines(symbols, days=args.days, intent=_intent(getattr(args, "intent", None))))
        normalized = {sym: [_kline_json(b, getattr(args, "show_provenance", False)) for b in bars] for sym, bars in result.normalized.items()}
        _json_out(_fetch_output(result, normalized, args))
    except Exception as e:
        _json_out({"error": str(e)})
        return 1
    return 0


def cmd_block(args) -> int:
    """block --category industry|concept [--mode auto|realtime|cache-ok]"""
    _init_db()
    router = Router()
    mode = getattr(args, "mode", "auto") or "auto"
    if mode == "cache-ok":
        # Try cache first
        from datakit.services.cache import read_parquet
        data, fresh = read_parquet("block_index", args.category)
        if fresh and data:
            _json_out(data)
            return 0
        # Fall through to live fetch
    try:
        result = asyncio.run(router.blocks(category=args.category, mode=mode, intent=_intent(getattr(args, "intent", None))))
        normalized = [{
            "code": b.code,
            "name": b.name,
            "category": b.category,
            "change_pct": b.change_pct,
            "members": list(b.members),
            **({"_provenance": _provenance_json(b._provenance)} if getattr(args, "show_provenance", False) else {}),
        } for b in result.normalized]
        _json_out(_fetch_output(result, normalized, args))
    except Exception as e:
        _json_out({"error": str(e)})
        return 1
    return 0


def cmd_cache(args) -> int:
    """cache status | warm | purge"""
    _init_db()
    if args.action == "status":
        _json_out(cache_status())
    elif args.action == "warm":
        syms = args.symbols.split(",") if args.symbols else None
        result = asyncio.run(cache_warm(syms))
        _json_out(result)
    elif args.action == "purge":
        days = getattr(args, "older_than", "7d") or "7d"
        # Parse "7d" to int
        days_int = int(days.replace("d", "")) if days else 7
        result = cache_purge(older_than_days=days_int)
        _json_out(result)
    return 0


def cmd_ops(args) -> int:
    """ops check | report | log"""
    _init_db()
    if args.action == "check":
        quiet = getattr(args, "quiet", False)
        result = ops_check(quiet=quiet)
        if not quiet:
            _json_out(result)
    elif args.action == "report":
        date_str = getattr(args, "date", None)
        result = ops_report(date_str=date_str)
        _json_out(result)
    elif args.action == "provenance" and args.subaction == "verify":
        symbols = _symbols(args.symbols) if getattr(args, "symbols", None) else None
        _json_out(provenance_verify(symbols=symbols, date_str=getattr(args, "date", None)))
    elif args.action == "raw-records" and args.subaction == "stats":
        _json_out(raw_records_stats())
    elif args.action == "log":
        n = getattr(args, "tail", 20)
        lines = log_tail(n=n)
        for line in lines:
            print(json.dumps(line, ensure_ascii=False, default=str))
    return 0



def cmd_anchors(args) -> int:
    """anchors list | validate"""
    calendar = AnchorCalendar(args.calendar)
    if args.action == "list":
        now_window = calendar.current_window()
        next_anchor = calendar.next_anchor()
        output = []
        for anchor in calendar.anchors:
            output.append({
                "label": anchor.label,
                "time": anchor.time.strftime("%H:%M"),
                "tz": anchor.tz,
                "passed": next_anchor is None or anchor.time < next_anchor.time,
            })
        _json_out({"calendar": args.calendar, "anchors": output, "current_window": now_window})
    elif args.action == "validate":
        from datetime import datetime
        ts = datetime.fromisoformat(args.timestamp)
        label = args.anchor or (calendar.next_anchor().label if calendar.next_anchor() else "")
        valid, reason = calendar.validate_temporal(ts, label)
        _json_out({"valid": valid, "reason": reason, "position": calendar.current_window(), "next_anchor": label})
    return 0

def cmd_inject(args) -> int:
    """inject status | guide"""
    if args.action == "status":
        _json_out(key_status())
    elif args.action == "guide":
        print(key_injection_guide())
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the full CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="python -m datakit",
        description="datakit — unified data access toolkit",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # registry
    reg = sub.add_parser("registry", help="List/show registered adapters")
    reg_sub = reg.add_subparsers(dest="action", required=True)
    reg_list = reg_sub.add_parser("list", help="List all adapters")
    reg_list.add_argument("--json", action="store_true", default=True, help=argparse.SUPPRESS)
    reg_show = reg_sub.add_parser("show", help="Show adapter details")
    reg_show.add_argument("name", help="Adapter name")
    reg_show.add_argument("--json", action="store_true", default=True, help=argparse.SUPPRESS)

    # health
    h = sub.add_parser("health", help="Health check")
    h.add_argument("--all", action="store_true", help="Check all sources")
    h.add_argument("--source", help="Check single source")
    h.add_argument("--json", action="store_true", default=True, help=argparse.SUPPRESS)

    # quote
    q = sub.add_parser("quote", help="Fetch real-time quotes")
    q.add_argument("--symbols", required=True, help="Comma-separated symbols")
    q.add_argument("--source", default="auto", help="Source (auto|tickflow|eastmoney)")
    q.add_argument("--json", action="store_true", default=True, help=argparse.SUPPRESS)
    q.add_argument("--intent", choices=["realtime-decision", "realtime", "backtest", "audit", "full-trace"], help="Consumption intent")
    q.add_argument("--show-raw", action="store_true", help="Include raw channel")
    q.add_argument("--show-provenance", action="store_true", help="Include provenance channel")

    # kline
    kl = sub.add_parser("kline", help="Fetch daily K-lines")
    kl.add_argument("--symbols", required=True, help="Comma-separated symbols")
    kl.add_argument("--days", type=int, default=2, help="Number of days (default 2)")
    kl.add_argument("--source", default="auto", help="Source (auto|tickflow|eastmoney)")
    kl.add_argument("--json", action="store_true", default=True, help=argparse.SUPPRESS)
    kl.add_argument("--intent", choices=["realtime-decision", "realtime", "backtest", "audit", "full-trace"], help="Consumption intent")
    kl.add_argument("--show-raw", action="store_true", help="Include raw channel")
    kl.add_argument("--show-provenance", action="store_true", help="Include provenance channel")

    # block
    bl = sub.add_parser("block", help="Fetch block/theme data")
    bl.add_argument("--category", default="industry", choices=["industry", "concept"], help="Block category")
    bl.add_argument("--mode", default="auto", choices=["auto", "realtime", "cache-ok"], help="Cache mode")
    bl.add_argument("--source", default="auto", help="Source (auto|iwencai|eastmoney)")
    bl.add_argument("--json", action="store_true", default=True, help=argparse.SUPPRESS)
    bl.add_argument("--intent", choices=["realtime-decision", "realtime", "backtest", "audit", "full-trace"], help="Consumption intent")
    bl.add_argument("--show-raw", action="store_true", help="Include raw channel")
    bl.add_argument("--show-provenance", action="store_true", help="Include provenance channel")

    # cache
    ca = sub.add_parser("cache", help="Cache management")
    ca_sub = ca.add_subparsers(dest="action", required=True)
    ca_status = ca_sub.add_parser("status", help="Cache statistics")
    ca_status.add_argument("--json", action="store_true", default=True, help=argparse.SUPPRESS)
    ca_warm = ca_sub.add_parser("warm", help="Pre-warm cache")
    ca_warm.add_argument("--symbols", help="Comma-separated symbols or 'all'")
    ca_warm.add_argument("--json", action="store_true", default=True, help=argparse.SUPPRESS)
    ca_purge = ca_sub.add_parser("purge", help="Purge old cache entries")
    ca_purge.add_argument("--older-than", default="7d", help="Delete entries older than (e.g. 7d)")
    ca_purge.add_argument("--json", action="store_true", default=True, help=argparse.SUPPRESS)

    # ops
    op = sub.add_parser("ops", help="Operational commands")
    op_sub = op.add_subparsers(dest="action", required=True)
    op_check = op_sub.add_parser("check", help="Full health sweep")
    op_check.add_argument("--quiet", action="store_true", help="Silent mode (write to DB only)")
    op_check.add_argument("--json", action="store_true", default=True, help=argparse.SUPPRESS)
    op_report = op_sub.add_parser("report", help="Daily ops report")
    op_report.add_argument("--date", help="Date (YYYY-MM-DD), defaults to today")
    op_report.add_argument("--json", action="store_true", default=True, help=argparse.SUPPRESS)
    op_prov = op_sub.add_parser("provenance", help="Provenance operations")
    op_prov_sub = op_prov.add_subparsers(dest="subaction", required=True)
    op_prov_verify = op_prov_sub.add_parser("verify", help="Verify provenance chains")
    op_prov_verify.add_argument("--date", default="today", help="Date or today")
    op_prov_verify.add_argument("--symbols", help="Comma-separated symbols")
    op_prov_verify.add_argument("--json", action="store_true", default=True, help=argparse.SUPPRESS)
    op_raw = op_sub.add_parser("raw-records", help="Raw record operations")
    op_raw_sub = op_raw.add_subparsers(dest="subaction", required=True)
    op_raw_stats = op_raw_sub.add_parser("stats", help="Raw record cache stats")
    op_raw_stats.add_argument("--json", action="store_true", default=True, help=argparse.SUPPRESS)
    op_log = op_sub.add_parser("log", help="View recent logs")
    op_log.add_argument("--tail", type=int, default=20, help="Number of lines (default 20)")
    op_log.add_argument("--json", action="store_true", default=True, help=argparse.SUPPRESS)

    # anchors
    an = sub.add_parser("anchors", help="Anchor calendar operations")
    an_sub = an.add_subparsers(dest="action", required=True)
    an_list = an_sub.add_parser("list", help="List anchors")
    an_list.add_argument("--calendar", required=True, help="Calendar name")
    an_list.add_argument("--json", action="store_true", default=True, help=argparse.SUPPRESS)
    an_validate = an_sub.add_parser("validate", help="Validate timestamp")
    an_validate.add_argument("--timestamp", required=True, help="ISO timestamp")
    an_validate.add_argument("--calendar", required=True, help="Calendar name")
    an_validate.add_argument("--anchor", help="Anchor label; defaults to next anchor")
    an_validate.add_argument("--json", action="store_true", default=True, help=argparse.SUPPRESS)

    # inject
    inj = sub.add_parser("inject", help="API key injection — status and guide")
    inj_sub = inj.add_subparsers(dest="action", required=True)
    inj_status = inj_sub.add_parser("status", help="Show key configuration status")
    inj_status.add_argument("--json", action="store_true", default=True, help=argparse.SUPPRESS)
    inj_guide = inj_sub.add_parser("guide", help="Print key injection guide (markdown)")

    return parser


COMMAND_MAP = {
    "registry": cmd_registry,
    "health": cmd_health,
    "quote": cmd_quote,
    "kline": cmd_kline,
    "block": cmd_block,
    "cache": cmd_cache,
    "ops": cmd_ops,
    "anchors": cmd_anchors,
    "inject": cmd_inject,
}
