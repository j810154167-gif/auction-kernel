"""Adapter auto-discovery.

Scans the adapters/ directory for modules, loads them by name attribute,
and exposes list_all() and get(name).
"""

from importlib import import_module
from pathlib import Path
from datakit.core.types import HealthStatus


_registry: dict[str, object] = {}


def discover() -> dict[str, object]:
    """Auto-discover all adapter modules in adapters/ and load them."""
    global _registry
    if _registry:
        return _registry

    adapters_dir = Path(__file__).resolve().parent.parent / "adapters"
    if not adapters_dir.is_dir():
        return {}

    for f in sorted(adapters_dir.glob("*.py")):
        if f.name.startswith("_") or f.name == "base.py":
            continue
        module_name = f"datakit.adapters.{f.stem}"
        try:
            mod = import_module(module_name)
            if hasattr(mod, "ADAPTER"):
                adapter = mod.ADAPTER
                _registry[adapter.name] = adapter
        except Exception as e:
            # Log but continue — a broken adapter shouldn't block the rest
            import sys
            print(f"[datakit] WARN: failed to load adapter {module_name}: {e}", file=sys.stderr)

    return _registry


def list_all() -> list[dict]:
    """Return metadata for all registered adapters."""
    discover()
    result = []
    for name, adp in _registry.items():
        result.append({
            "name": name,
            "display_name": adp.display_name,
            "supports_ws": adp.supports_ws,
            "requires_auth": adp.requires_auth,
        })
    return result


def get(name: str):
    """Get a single adapter by name. Raises KeyError if not found."""
    discover()
    if name not in _registry:
        raise KeyError(f"adapter '{name}' not found. Available: {list(_registry.keys())}")
    return _registry[name]


def health_all() -> list[HealthStatus]:
    """Synchronous health sweep across all adapters. Each runs in its own asyncio.run()."""
    import asyncio
    discover()
    results = []
    for name, adp in _registry.items():
        try:
            status = asyncio.run(adp.health_check())
            results.append(status)
        except Exception as e:
            results.append(HealthStatus(
                source=name,
                reachable=False,
                latency_ms=0,
                error=str(e),
            ))
    return results
