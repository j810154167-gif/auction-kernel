"""API key injection — unified discovery and validation.

Provides key_status() for LLM/Agent to check what's configured, and
key_injection_guide() for a human-readable setup checklist.

All key reading uses os.environ only — no .env file is read directly.
The caller (human, cron, master_launcher) is responsible for loading
environment variables before importing datakit.
"""

import os
from datakit.core.registry import list_all


def key_status() -> list[dict]:
    """Return the current key status for all adapters that require auth.

    LLM/Agent use: python -m datakit inject status
    """
    results = []
    for item in list_all():
        if not item["requires_auth"]:
            continue
        from datakit.core.registry import get
        adapter = get(item["name"])
        found = {}
        missing = []
        for var in adapter.key_env_vars:
            val = os.environ.get(var, "").strip()
            if val:
                found[var] = f"{val[:8]}..." if len(val) > 12 else val[:4] + "***"
            else:
                missing.append(var)
        # configured = at least one key var is set (they are alternatives)
        configured = len(found) > 0
        results.append({
            "source": item["name"],
            "display_name": item["display_name"],
            "configured": configured,
            "found_vars": found,
            "missing_vars": missing,
        })
    return results


def key_injection_guide() -> str:
    """Return a markdown-formatted guide for all key-injectable adapters.

    LLM/Agent use: python -m datakit inject guide
    """
    lines = ["## API Key Injection Guide", ""]
    for item in list_all():
        if not item["requires_auth"]:
            lines.append(f"- **{item['display_name']}** ({item['name']}): no key needed")
            continue
        from datakit.core.registry import get
        adapter = get(item["name"])
        vars_str = ", ".join(f"`{v}`" for v in adapter.key_env_vars)
        lines.append(f"### {item['display_name']} ({item['name']})")
        lines.append(f"**Env vars**: {vars_str}")
        lines.append(f"```bash\n{adapter.key_injection_hint.strip()}\n```")
        lines.append("")
    lines.append("## Recommended Pattern")
    lines.append("")
    lines.append("Store all keys in `~/.openclaw/keys.env`:")
    lines.append("```bash")
    lines.append("# ~/.openclaw/keys.env — source before running datakit")
    lines.append("export TICKFLOW_API_KEY=tk_b35f...")
    lines.append("export IWENCAI_API_KEY=sk-proj-00-...")
    lines.append("```")
    lines.append("")
    lines.append("Then either:")
    lines.append("- `source ~/.openclaw/keys.env && python -m datakit ops check`")
    lines.append("- or add `source ~/.openclaw/keys.env` to your `master_launcher.py` preamble")
    return "\n".join(lines)


def check_all_keys() -> bool:
    """Return True if all auth-required adapters have their keys configured."""
    for status in key_status():
        if not status["configured"]:
            return False
    return True
