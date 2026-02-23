"""Data models for BVG departure data."""

from __future__ import annotations

import html
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class Departure:
    """A single public transport departure from a BVG station.

    Represents one row on the departure board. Created by parse_departure()
    from raw BVG API JSON. Times are ISO 8601 strings with timezone info.

    The `when` field is the real-time (actual) departure time, which may
    differ from the scheduled `planned_when` by `delay_seconds`. If no
    real-time data is available, `when` is None and `planned_when` is used
    as the fallback.

    Attributes:
        line_name: Display name of the line, already prefixed by parse_departure()
            (e.g. "S7", "M21" for tram, "B240" for bus).
        line_product: BVG product type string. One of: "suburban" (S-Bahn),
            "subway" (U-Bahn), "tram", "bus", "regional", "express".
        direction: Cleaned destination name. Loop arrows and S/U prefixes
            are stripped by parse_departure() for brevity since the line
            name already identifies the product type.
        when: Real-time ISO 8601 departure timestamp, or None if no
            real-time data is available from the BVG API.
        planned_when: Scheduled ISO 8601 departure timestamp. Always present
            unless the API returns incomplete data.
        delay_seconds: Delay in seconds relative to planned_when. None means
            no real-time info, 0 means on time, positive means late.
        platform: Platform or track identifier string, or None if not reported.
        remarks: Filtered list of human-readable remarks. Only includes
            bicycle permission and warning-type disruption notices.
            Informational hints are excluded to reduce noise.
        is_cancelled: True if this departure has been cancelled. Cancelled
            departures are still shown on the board with "Fällt aus" alternation.
    """

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

    # Filter remarks to only actionable information: 'FK' is the BVG code
    # for Fahrradmitnahme (bicycle transport allowed). 'warning' type remarks
    # contain disruption notices. Other types are noise.
    remarks: list[str] = []
    for r in remarks_raw:
        if r.get("code") == "FK":
            remarks.append("Fahrradmitnahme möglich")
        elif r.get("type") == "warning" and r.get("text"):
            remarks.append(html.unescape(r["text"]))

    line_name = line.get("name", "")
    line_product = line.get("product", "")
    # BVG API returns bare tram numbers (e.g. '21') but Berlin uses MetroTram
    # branding with 'M' prefix. Add 'M' unless already present.
    if line_product == "tram" and line_name and not line_name.startswith("M"):
        line_name = f"M{line_name}"
    # Bus lines get 'B' prefix for visual distinction. Skip lines with existing
    # letter prefix: night buses ('N'), MetroBus ('M').
    if line_product == "bus" and line_name and not line_name.startswith(("B", "N", "M")):
        line_name = f"B{line_name}"

    return Departure(
        line_name=line_name,
        line_product=line_product,
        # Clean direction: remove loop arrows (ring lines S41/S42), strip
        # 'S+U'/'S'/'U' prefixes (redundant with line name column).
        direction=raw.get("direction", "").replace("⟲", "").replace("⟳", "").strip().removeprefix("S+U ").removeprefix("S ").removeprefix("U "),
        when=raw.get("when"),
        planned_when=raw.get("plannedWhen"),
        delay_seconds=raw.get("delay"),
        platform=raw.get("platform"),
        remarks=remarks,
        is_cancelled=raw.get("cancelled", False),
    )


@dataclass
class StationContext:
    """Runtime state for a single station in the multi-station rotation.

    Holds the cached departure list and tracks when data was last fetched
    to implement the refresh interval. One StationContext is created per
    configured station at startup and persists for the app's lifetime.

    Attributes:
        station_id: BVG 9-digit station ID (e.g. "900023201").
        station_name: Resolved display name for the station header.
        walking_minutes: Walking time from home, used for hurry-zone filtering.
        lines: Per-station line filter (empty list means show all lines).
        departures: Cached list of parsed Departure objects from the last fetch.
        last_fetch: Unix timestamp of the last successful API fetch.
            Initialized to 0.0 so the first refresh always triggers.
    """

    station_id: str
    station_name: str
    walking_minutes: int = 5
    lines: list[str] = field(default_factory=list)
    departures: list[Departure] = field(default_factory=list)
    last_fetch: float = 0.0

    def needs_refresh(self, interval_seconds: int) -> bool:
        """Check if departures need to be refreshed."""
        return time.time() - self.last_fetch >= interval_seconds
