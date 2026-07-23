#!/usr/bin/env python3
"""Data-source governance for morning-auction runtime.

This module is intentionally offline-first: it records source selection,
collision metrics, and loop acceptance state without scraping vendor web UI.
Live smoke tests can feed real payloads into these pure functions.
"""
from __future__ import annotations

import json
import os
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Mapping

SELECTED_IWENCAI_SKILLS = [
    "涨停板战士",
    "行业轮动研究员",
    "行情监控er",
    "舆情监控达人",
    "游资追踪手",
    "北向资金观察/追踪者",
]

MAPPING_CONSISTENCY_THRESHOLD = 0.70
LIMIT_UP_REASON_COVERAGE_PURCHASE_THRESHOLD = 0.80


def _env(env: Mapping[str, str] | None = None) -> Mapping[str, str]:
    return os.environ if env is None else env


def _has_tickflow_key(env: Mapping[str, str]) -> bool:
    if env.get("TICKFLOW_API_KEY", "").strip():
        return True
    key_file = env.get("TICKFLOW_API_KEY_FILE", "").strip()
    if not key_file:
        return False
    try:
        return bool(Path(key_file).expanduser().read_text(encoding="utf-8").splitlines()[0].strip())
    except (OSError, IndexError):
        return False


def _previous_trading_day(trade_date: str) -> str:
    current = date.fromisoformat(trade_date)
    current -= timedelta(days=1)
    while current.weekday() >= 5:
        current -= timedelta(days=1)
    return current.isoformat()


def _tickflow_reference(
    env: Mapping[str, str],
    context: Mapping[str, Any] | None,
    tickflow_status: Mapping[str, Any] | None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    context = context or {}
    tickflow_status = tickflow_status or {}
    trade_date = context.get("trade_date") or env.get("HERMES_TRADE_DATE", "").strip()
    if not trade_date:
        return None, None

    local_previous = (
        str(context.get("local_previous_trading_day") or "").strip()
        or env.get("HERMES_LOCAL_PREVIOUS_TRADING_DAY", "").strip()
        or _previous_trading_day(str(trade_date))
    )
    latest = (
        str(tickflow_status.get("latest_completed_daily_bar_date") or "").strip()
        or str(tickflow_status.get("latest_completed_daily_bar") or "").strip()
        or env.get("TICKFLOW_LATEST_COMPLETED_DAILY_BAR_DATE", "").strip()
    )
    freshness = (
        str(tickflow_status.get("freshness") or "").strip()
        or str(tickflow_status.get("status") or "").strip()
        or env.get("TICKFLOW_FRESHNESS_STATUS", "").strip()
        or ("ok" if latest else "missing")
    )
    reference = {
        "status": "locked" if latest == local_previous and freshness == "ok" else "blocked",
        "trade_date": str(trade_date),
        "local_previous_trading_day": local_previous,
        "tickflow_latest_completed_daily_bar_date": latest or None,
        "tickflow_freshness": freshness,
        "session_boundary": "09:15",
    }
    if not latest:
        return reference, {
            "reason": "tickflow_latest_daily_bar_missing",
            "blocked_layer": "market_fact_layer",
            "hard_alert": True,
        }
    if freshness != "ok":
        return reference, {
            "reason": "tickflow_fact_layer_stale",
            "blocked_layer": "market_fact_layer",
            "tickflow_freshness": freshness,
            "hard_alert": True,
        }
    if latest != local_previous:
        return reference, {
            "reason": "tickflow_previous_day_reference_mismatch",
            "blocked_layer": "market_fact_layer",
            "local_previous_trading_day": local_previous,
            "tickflow_latest_completed_daily_bar_date": latest,
            "hard_alert": True,
        }
    return reference, None


def build_preflight(
    env: Mapping[str, str] | None = None,
    context: Mapping[str, Any] | None = None,
    tickflow_status: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    current_env = _env(env)
    tickflow_ok = _has_tickflow_key(current_env)
    previous_day_reference, tickflow_blocked = _tickflow_reference(current_env, context, tickflow_status)
    if tickflow_blocked:
        tickflow_ok = False
    iwencai_mode = current_env.get("IWENCAI_ACCESS_MODE", "").strip()
    ths_key_file = current_env.get("THS_API_KEY_FILE", "").strip()
    iwencai_base_url = current_env.get("IWENCAI_BASE_URL", "").strip()
    iwencai_api_key = current_env.get("IWENCAI_API_KEY", "").strip()
    iwencai_configured = bool(iwencai_mode or ths_key_file or (iwencai_base_url and iwencai_api_key))
    manual_probe = Path(__file__).resolve().parent / "rebuild_manifest" / "manual_files_688798_source_probe.json"

    report: dict[str, Any] = {
        "schema_version": 1,
        "status": "ok" if tickflow_ok else "blocked",
        "hard_alert": bool(tickflow_blocked),
        "sources": {
            "tickflow": {
                "role": "market_fact_layer",
                "status": "ok" if tickflow_ok else "blocked",
                "credential_policy": ["TICKFLOW_API_KEY", "TICKFLOW_API_KEY_FILE"],
                "provides": ["quotes", "daily_klines", "1m_klines", "websocket_quotes"],
                "freshness_policy": "latest_completed_daily_bar_must_equal_local_T_minus_1",
            },
            "eastmoney": {
                "role": "explanation_layer_candidate",
                "status": "configured",
                "access": "public_unofficial",
                "provides": ["sector_rank", "sector_change", "sector_members"],
                "failure_policy": "degraded_continue",
            },
            "iwencai": {
                "role": "explanation_layer_candidate",
                "status": "configured" if iwencai_configured else "trial_required",
                "access_mode": iwencai_mode or ("skillhub_api_key" if iwencai_base_url and iwencai_api_key else "trial_or_platform_skill_required"),
                "credential_policy": ["IWENCAI_ACCESS_MODE", "THS_API_KEY_FILE", "IWENCAI_BASE_URL", "IWENCAI_API_KEY", "platform_skillhub_or_mcp"],
                "production_cookie_allowed": False,
                "selected_skills": SELECTED_IWENCAI_SKILLS,
                "failure_policy": "degraded_continue",
            },
            "manual_files_688798": {
                "role": "manual_explanation_mapping_fallback",
                "status": "configured" if manual_probe.exists() else "missing",
                "access": "public_json",
                "provides": ["stock_to_concepts", "stock_to_industries"],
                "failure_policy": "degraded_continue",
            },
        },
        "procurement": {
            "decision": "trial_before_purchase",
            "purchase_request": False,
            "purchase_gate": {
                "mapping_consistency_min": MAPPING_CONSISTENCY_THRESHOLD,
                "limit_up_reason_coverage_min": LIMIT_UP_REASON_COVERAGE_PURCHASE_THRESHOLD,
                "sample_window": "3_trading_days_or_5_live_smokes",
            },
        },
    }
    if previous_day_reference:
        report["previous_day_reference"] = previous_day_reference
    if not tickflow_ok:
        report["blocked_state"] = tickflow_blocked or {
            "reason": "tickflow_credentials_missing",
            "blocked_layer": "market_fact_layer",
            "allowed_next_actions": ["offline_fixture_validation", "configure_tickflow_credentials"],
        }
        if tickflow_blocked:
            report["blocked_state"]["allowed_next_actions"] = ["refresh_tickflow_fact_layer", "offline_fixture_validation"]
    return report


def _sector_names(payload: Mapping[str, Any]) -> set[str]:
    return {str(item.get("name", "")).strip() for item in payload.get("sectors", []) if str(item.get("name", "")).strip()}


def _stock_sector_map(payload: Mapping[str, Any]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    raw = payload.get("stock_sector_map", {})
    if not isinstance(raw, Mapping):
        return result
    for code, sectors in raw.items():
        if isinstance(sectors, str):
            values = {sectors}
        else:
            values = {str(value).strip() for value in sectors or [] if str(value).strip()}
        result[str(code)] = values
    return result


def _mapping_consistency(left: Mapping[str, Any], right: Mapping[str, Any]) -> float:
    lmap = _stock_sector_map(left)
    rmap = _stock_sector_map(right)
    common = sorted(set(lmap) & set(rmap))
    if not common:
        return 0.0
    matched = sum(1 for code in common if lmap[code] & rmap[code])
    return round(matched / len(common), 4)


def _limit_up_reason_coverage(iwencai: Mapping[str, Any]) -> float:
    reasons = iwencai.get("limit_up_reasons", {})
    if not isinstance(reasons, Mapping) or not reasons:
        return 0.0
    covered = sum(1 for reason in reasons.values() if str(reason).strip())
    return round(covered / len(reasons), 4)


def compare_explanation_sources(
    eastmoney: Mapping[str, Any],
    iwencai: Mapping[str, Any],
    mapping_threshold: float = MAPPING_CONSISTENCY_THRESHOLD,
) -> dict[str, Any]:
    east_names = _sector_names(eastmoney)
    iwencai_names = _sector_names(iwencai)
    iwencai_available = bool(iwencai.get("available", True))
    degraded_reasons: list[str] = []

    if not iwencai_available:
        degraded_reasons.append("iwencai_unavailable")

    name_union = east_names | iwencai_names
    name_overlap = len(east_names & iwencai_names) / len(name_union) if name_union else 0.0
    mapping_consistency = _mapping_consistency(eastmoney, iwencai) if iwencai_available else 0.0
    reason_coverage = _limit_up_reason_coverage(iwencai) if iwencai_available else 0.0

    if iwencai_available and mapping_consistency < mapping_threshold:
        degraded_reasons.append("low_mapping_consistency")

    status = "ok" if not degraded_reasons else "degraded_continue"
    preferred = "dual_source_collision" if status == "ok" else "eastmoney"
    purchase_candidate = (
        status == "ok" and reason_coverage >= LIMIT_UP_REASON_COVERAGE_PURCHASE_THRESHOLD
    )

    return {
        "schema_version": 1,
        "status": status,
        "preferred_explanation_source": preferred,
        "degraded_reasons": degraded_reasons,
        "metrics": {
            "sector_name_overlap": round(name_overlap, 4),
            "mapping_consistency": mapping_consistency,
            "limit_up_reason_coverage": reason_coverage,
        },
        "procurement_signal": "purchase_evaluation_candidate" if purchase_candidate else "continue_trial",
    }


def build_acceptance(preflight: Mapping[str, Any], collision: Mapping[str, Any]) -> dict[str, Any]:
    tickflow_status = preflight.get("sources", {}).get("tickflow", {}).get("status")
    if tickflow_status != "ok":
        blocked = dict(preflight.get("blocked_state", {}))
        reason = blocked.get("reason", "tickflow_fact_layer_unavailable")
        return {
            "schema_version": 1,
            "status": "blocked",
            "data_source_quality": "blocked",
            "hard_alert": bool(preflight.get("hard_alert") or blocked.get("hard_alert")),
            "previous_day_reference": preflight.get("previous_day_reference"),
            "blocked_state": {
                "reason": reason,
                "blocked_layer": "market_fact_layer",
                "allowed_next_actions": ["configure_tickflow_credentials", "offline_fixture_validation"],
                **blocked,
            },
        }

    if collision.get("status") == "degraded_continue":
        return {
            "schema_version": 1,
            "status": "degraded_continue",
            "data_source_quality": "degraded",
            "preferred_explanation_source": collision.get("preferred_explanation_source", "eastmoney"),
            "degraded_reasons": collision.get("degraded_reasons", []),
            "metrics": collision.get("metrics", {}),
            "degraded_state": {
                "reason": "explanation_layer_degraded",
                "allowed_next_actions": ["run_D1_with_degraded_metadata", "run_D2_with_degraded_metadata", "review_data_sources"],
            },
        }

    return {
        "schema_version": 1,
        "status": "ok",
        "data_source_quality": "ok",
        "preferred_explanation_source": collision.get("preferred_explanation_source", "dual_source_collision"),
        "metrics": collision.get("metrics", {}),
    }


def write_reports(
    handoff_dir: Path,
    preflight: Mapping[str, Any],
    collision: Mapping[str, Any],
    acceptance: Mapping[str, Any],
) -> dict[str, str]:
    handoff_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "data_source_preflight": handoff_dir / "data_source_preflight.json",
        "data_source_collision": handoff_dir / "data_source_collision.json",
        "data_source_acceptance": handoff_dir / "data_source_acceptance.json",
    }
    payloads = {
        "data_source_preflight": preflight,
        "data_source_collision": collision,
        "data_source_acceptance": acceptance,
    }
    for name, path in outputs.items():
        path.write_text(json.dumps(payloads[name], ensure_ascii=False, indent=2), encoding="utf-8")
    return {name: str(path) for name, path in outputs.items()}


def load_acceptance_metadata(handoff_dir: Path) -> dict[str, Any]:
    path = handoff_dir / "data_source_acceptance.json"
    if not path.exists():
        path = handoff_dir / "nodes" / "data_source_acceptance.json"
    if not path.exists():
        return {
            "data_source_quality": "unknown",
            "data_source_acceptance_status": "missing",
            "preferred_explanation_source": "unknown",
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {
            "data_source_quality": "blocked",
            "data_source_acceptance_status": "invalid_json",
            "preferred_explanation_source": "unknown",
        }
    return {
        "data_source_quality": payload.get("data_source_quality", "unknown"),
        "data_source_acceptance_status": payload.get("status", "unknown"),
        "preferred_explanation_source": payload.get("preferred_explanation_source", "unknown"),
        "blocked_reason": payload.get("blocked_state", {}).get("reason"),
        "hard_alert": bool(payload.get("hard_alert") or payload.get("blocked_state", {}).get("hard_alert")),
    }
