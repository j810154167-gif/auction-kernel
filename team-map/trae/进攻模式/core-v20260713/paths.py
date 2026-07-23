"""
Hermes workspace paths — self-contained, no OpenClaw dependencies.
All outputs go to /Users/fiona/.hermes/workspace/handoff/<date>/
"""
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))
HERMES_HOME = Path("/Users/fiona/.hermes")
WORKSPACE = Path("/Users/fiona/.hermes/workspace")
HANDOFF_ROOT = WORKSPACE / "handoff"

def today_str() -> str:
    return datetime.now(CST).strftime("%Y-%m-%d")

def resolve_handoff_dir() -> Path:
    """Resolve today's handoff directory under Hermes workspace."""
    env_dir = os.environ.get("HERMES_HANDOFF_DIR", "").strip()
    if env_dir:
        return Path(env_dir)
    run_dir = os.environ.get("HERMES_RUN_HANDOFF_DIR", "").strip()
    if run_dir:
        return Path(run_dir)
    return HANDOFF_ROOT / today_str()

HANDOFF = resolve_handoff_dir()
HANDOFF.mkdir(parents=True, exist_ok=True)

def load_api_key() -> str:
    """Load TickFlow API key from env or known file locations."""
    # Priority: env var > Hermes skills dir > default locations
    key = os.environ.get("TICKFLOW_API_KEY", "").strip()
    if key:
        return key
    
    key_file = os.environ.get("TICKFLOW_API_KEY_FILE", "").strip()
    candidates = []
    if key_file:
        candidates.append(Path(key_file))
    candidates.extend([
        Path("/Users/fiona/.hermes/skills/tickflow-expert-governance/tickflow expert api.txt"),
        Path("/Users/fiona/.openclaw/workspace/skills/tickflow-expert-governance/tickflow expert api.txt"),
    ])
    for p in candidates:
        if p.exists():
            return p.read_text().strip()
    
    raise RuntimeError("TickFlow API key missing: set TICKFLOW_API_KEY or TICKFLOW_API_KEY_FILE")

def get_data_dir() -> Path:
    """Get data directory for static files (stock CSV etc)."""
    env_csv = os.environ.get("HERMES_STOCK_CSV", "").strip()
    if env_csv:
        return Path(env_csv).parent
    # Fallback: use the CSV from the OpenClaw workspace if available
    csv_path = Path("/Users/fiona/.openclaw/workspace/runtime/20260618-morning-auction/data/static/all_stocks_20260306.csv")
    if csv_path.exists():
        return csv_path.parent
    return WORKSPACE / "data"

def get_stock_csv() -> Path:
    """Get the full stock list CSV path."""
    env_csv = os.environ.get("HERMES_STOCK_CSV", "").strip()
    if env_csv:
        return Path(env_csv)
    return Path("/Users/fiona/.openclaw/workspace/runtime/20260618-morning-auction/data/static/all_stocks_20260306.csv")
