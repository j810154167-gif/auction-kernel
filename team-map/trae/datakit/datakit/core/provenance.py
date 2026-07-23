"""Provenance chain construction utilities."""

import time
from typing import Callable

from datakit.core.types import ProvenanceEntry


class ProvenanceBuilder:
    """Collect timestamped processing steps within a fetch operation."""

    def __init__(
        self,
        clock: Callable[[], float] = time.time,
        actor: str = "datakit",
    ):
        self._clock = clock
        self.actor = actor
        self.entries: list[ProvenanceEntry] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def add(self, step: str, actor: str, detail: str = "") -> ProvenanceEntry:
        """Append a processing step to this chain."""
        entry = ProvenanceEntry(step, actor, self._clock(), detail)
        self.entries.append(entry)
        return entry

    def source_fetch(self, actor: str, detail: str = "") -> ProvenanceEntry:
        return self.add("source_fetch", actor, detail)

    def normalize(self, actor: str = "datakit.normalizer", detail: str = "") -> ProvenanceEntry:
        return self.add("normalize", actor, detail)

    def failover(self, actor: str = "datakit.router", detail: str = "") -> ProvenanceEntry:
        return self.add("failover", actor, detail)
