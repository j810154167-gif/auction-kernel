"""Configuration-backed generic time-anchor calendar."""

from datetime import datetime
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo

import yaml

from datakit.core.types import AnchorPoint


class AnchorCalendar:
    """Load and evaluate one caller-defined anchor sequence."""

    def __init__(
        self,
        name: str,
        config_path: str | Path | None = None,
        clock: Callable[[ZoneInfo], datetime] | None = None,
    ):
        if config_path is None:
            config_path = Path(__file__).resolve().parent.parent / "config.yaml"
        self.name = name
        self._clock = clock or (lambda tz: datetime.now(tz))
        self.anchors = self._load(Path(config_path))

    def _load(self, config_path: Path) -> list[AnchorPoint]:
        if not config_path.exists():
            return []
        with open(config_path, encoding="utf-8") as config_file:
            config = yaml.safe_load(config_file) or {}
        anchors = []
        for item in config.get("anchors", {}).get(self.name, []):
            timezone = ZoneInfo(item["tz"])
            parsed = datetime.strptime(item["time"], "%H:%M").time().replace(tzinfo=timezone)
            anchors.append(AnchorPoint(item["label"], parsed, item["tz"]))
        return sorted(anchors, key=lambda anchor: anchor.time)

    def _now(self, anchor: AnchorPoint) -> datetime:
        return self._clock(ZoneInfo(anchor.tz))

    def next_anchor(self) -> AnchorPoint | None:
        """Return the first anchor later than the current local time."""
        for anchor in self.anchors:
            if self._now(anchor).timetz() < anchor.time:
                return anchor
        return None

    def validate_temporal(self, data_timestamp: datetime, anchor_label: str):
        """Check that data available before an anchor is not timestamped after it."""
        if not self.anchors:
            return True, None
        anchor = next((item for item in self.anchors if item.label == anchor_label), None)
        if anchor is None:
            return True, None
        timezone = ZoneInfo(anchor.tz)
        now = self._clock(timezone)
        data_time = data_timestamp.astimezone(timezone)
        anchor_datetime = datetime.combine(now.date(), anchor.time)
        if now < anchor_datetime and data_time > anchor_datetime:
            reason = (
                f"data_timestamp {data_time.strftime('%H:%M:%S')} exceeds next anchor "
                f"{anchor.time.strftime('%H:%M')} at current time {now.strftime('%H:%M:%S')}"
            )
            return False, reason
        return True, None

    def current_window(self) -> dict | None:
        """Return the current generic position and neighboring anchor references."""
        if not self.anchors:
            return None
        first = self.anchors[0]
        now_time = self._now(first).timetz()
        references = [self._reference(anchor) for anchor in self.anchors]
        if now_time < first.time:
            return {"position": "before_first", "next_anchor": references[0]}
        for index, anchor in enumerate(self.anchors[1:], start=1):
            if now_time < anchor.time:
                return {
                    "position": "between",
                    "prev_anchor": references[index - 1],
                    "next_anchor": references[index],
                }
        return {"position": "after_last", "prev_anchor": references[-1]}

    @staticmethod
    def _reference(anchor: AnchorPoint) -> dict[str, str]:
        return {"label": anchor.label, "time": anchor.time.strftime("%H:%M")}
