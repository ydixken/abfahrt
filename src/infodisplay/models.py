"""Data models for BVG departure data."""

from __future__ import annotations

import html
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class Departure:
    line_name: str
    line_product: str
    direction: str
    when: str | None
    planned_when: str | None
    delay_seconds: int | None
    platform: str | None
    remarks: list[str]
    is_cancelled: bool

    @property
    def minutes_until(self) -> int | None:
        """Minutes until departure, based on `when` (real-time) timestamp."""
        ts = self.when or self.planned_when
        if ts is None:
            return None
        dt = datetime.fromisoformat(ts)
        delta = dt - datetime.now(timezone.utc)
        return max(0, int(delta.total_seconds() // 60))

    @property
    def delay_minutes(self) -> int:
        """Delay in minutes (0 if no delay info)."""
        if self.delay_seconds is None:
            return 0
        return self.delay_seconds // 60


def parse_departure(raw: dict) -> Departure:
    """Parse a raw BVG API departure dict into a Departure object."""
    line = raw.get("line", {})
    remarks_raw = raw.get("remarks", [])

    remarks: list[str] = []
    for r in remarks_raw:
        if r.get("code") == "FK":
            remarks.append("Fahrradmitnahme möglich")
        elif r.get("type") == "warning" and r.get("text"):
            remarks.append(html.unescape(r["text"]))

    line_name = line.get("name", "")
    line_product = line.get("product", "")
    # Prefix tram lines without "M" with "M" for consistency with MetroTram branding
    if line_product == "tram" and line_name and not line_name.startswith("M"):
        line_name = f"M{line_name}"
    # Prefix bus lines with "B" (skip night buses which already have "N")
    if line_product == "bus" and line_name and not line_name.startswith(("B", "N")):
        line_name = f"B{line_name}"

    return Departure(
        line_name=line_name,
        line_product=line_product,
        direction=raw.get("direction", "").replace("⟲", "").replace("⟳", "").strip(),
        when=raw.get("when"),
        planned_when=raw.get("plannedWhen"),
        delay_seconds=raw.get("delay"),
        platform=raw.get("platform"),
        remarks=remarks,
        is_cancelled=raw.get("cancelled", False),
    )


@dataclass
class StationContext:
    station_id: str
    station_name: str
    walking_minutes: int = 5
    lines: list[str] = field(default_factory=list)
    departures: list[Departure] = field(default_factory=list)
    last_fetch: float = 0.0

    def needs_refresh(self, interval_seconds: int) -> bool:
        """Check if departures need to be refreshed."""
        return time.time() - self.last_fetch >= interval_seconds
