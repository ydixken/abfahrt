"""Tests for abfahrt.models."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from abfahrt.models import Departure, StationContext, parse_departure


class TestParseDeparture:
    """Tests for parse_departure() converting raw BVG API JSON dicts to Departure objects."""

    def test_normal_departure(self, sample_departure_raw):
        """Verify that a standard S-Bahn departure parses all fields correctly."""
        dep = parse_departure(sample_departure_raw)
        assert dep.line_name == "S7"
        assert dep.line_product == "suburban"
        assert dep.direction == "Potsdam Hauptbahnhof"
        assert dep.when == "2026-02-22T21:05:00+01:00"
        assert dep.planned_when == "2026-02-22T21:03:00+01:00"
        assert dep.delay_seconds == 120
        assert dep.platform == "1"
        assert dep.is_cancelled is False

    def test_fk_remark(self, sample_departure_raw):
        """Verify that the BVG 'FK' remark code is translated to 'Fahrradmitnahme möglich'."""
        dep = parse_departure(sample_departure_raw)
        assert "Fahrradmitnahme möglich" in dep.remarks

    def test_warning_remark(self, sample_departure_raw):
        """Verify that a warning-type remark ('Bauarbeiten') is preserved in the remarks list."""
        dep = parse_departure(sample_departure_raw)
        assert "Bauarbeiten" in dep.remarks

    def test_null_when(self, sample_departure_null_when):
        """Verify that a departure with no real-time data has when=None but retains planned_when."""
        dep = parse_departure(sample_departure_null_when)
        assert dep.when is None
        assert dep.planned_when is not None

    def test_null_delay(self, sample_departure_null_when):
        """Verify that a departure with no real-time data has delay_seconds=None."""
        dep = parse_departure(sample_departure_null_when)
        assert dep.delay_seconds is None

    def test_empty_remarks(self, sample_departure_no_remarks):
        """Verify that a departure with no remarks produces an empty remarks list."""
        dep = parse_departure(sample_departure_no_remarks)
        assert dep.remarks == []

    def test_cancelled(self, sample_departure_cancelled):
        """Verify that a cancelled departure has is_cancelled=True."""
        dep = parse_departure(sample_departure_cancelled)
        assert dep.is_cancelled is True

    def test_missing_line_fields(self):
        """Verify graceful handling when the API response omits the line object entirely."""
        raw = {
            "when": None,
            "plannedWhen": None,
            "delay": None,
            "platform": None,
            "direction": "",
            "remarks": [],
        }
        dep = parse_departure(raw)
        assert dep.line_name == ""
        assert dep.line_product == ""


class TestMinutesUntil:
    """Tests for the Departure.minutes_until computed property."""

    def test_future_departure(self):
        """Verify that minutes_until returns floored minutes for a departure 5.5 minutes away."""
        future = (datetime.now(timezone.utc) + timedelta(minutes=5, seconds=30)).isoformat()
        dep = Departure(
            line_name="S7",
            line_product="suburban",
            direction="Test",
            when=future,
            planned_when=future,
            delay_seconds=0,
            platform="1",
            remarks=[],
            is_cancelled=False,
        )
        assert dep.minutes_until == 5

    def test_past_departure(self):
        """Verify that minutes_until clamps to zero for an already-departed train."""
        past = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
        dep = Departure(
            line_name="S7",
            line_product="suburban",
            direction="Test",
            when=past,
            planned_when=past,
            delay_seconds=0,
            platform="1",
            remarks=[],
            is_cancelled=False,
        )
        assert dep.minutes_until == 0

    def test_null_when_uses_planned(self):
        """Verify that minutes_until falls back to planned_when when when is None."""
        future = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
        dep = Departure(
            line_name="U1",
            line_product="subway",
            direction="Test",
            when=None,
            planned_when=future,
            delay_seconds=None,
            platform=None,
            remarks=[],
            is_cancelled=False,
        )
        assert dep.minutes_until is not None
        assert dep.minutes_until >= 9

    def test_both_null_returns_none(self):
        """Verify that minutes_until returns None when both when and planned_when are missing."""
        dep = Departure(
            line_name="U1",
            line_product="subway",
            direction="Test",
            when=None,
            planned_when=None,
            delay_seconds=None,
            platform=None,
            remarks=[],
            is_cancelled=False,
        )
        assert dep.minutes_until is None


class TestDelayMinutes:
    """Tests for the Departure.delay_minutes computed property."""

    def test_positive_delay(self):
        """Verify that 180 delay_seconds converts to 3 delay_minutes."""
        dep = Departure(
            line_name="S7",
            line_product="suburban",
            direction="Test",
            when=None,
            planned_when=None,
            delay_seconds=180,
            platform="1",
            remarks=[],
            is_cancelled=False,
        )
        assert dep.delay_minutes == 3

    def test_zero_delay(self):
        """Verify that zero delay_seconds produces zero delay_minutes."""
        dep = Departure(
            line_name="S7",
            line_product="suburban",
            direction="Test",
            when=None,
            planned_when=None,
            delay_seconds=0,
            platform="1",
            remarks=[],
            is_cancelled=False,
        )
        assert dep.delay_minutes == 0

    def test_null_delay(self):
        """Verify that None delay_seconds defaults to zero delay_minutes."""
        dep = Departure(
            line_name="S7",
            line_product="suburban",
            direction="Test",
            when=None,
            planned_when=None,
            delay_seconds=None,
            platform="1",
            remarks=[],
            is_cancelled=False,
        )
        assert dep.delay_minutes == 0


class TestStationContext:
    """Tests for StationContext creation and refresh-interval logic."""

    def test_creation(self):
        """Verify that StationContext initializes with empty departures and zero last_fetch."""
        ctx = StationContext(station_id="900023201", station_name="Savignyplatz")
        assert ctx.station_id == "900023201"
        assert ctx.station_name == "Savignyplatz"
        assert ctx.departures == []
        assert ctx.last_fetch == 0.0

    def test_needs_refresh_initial(self):
        """Verify that a newly created context (last_fetch=0) always needs refresh."""
        ctx = StationContext(station_id="900023201", station_name="Savignyplatz")
        assert ctx.needs_refresh(30) is True

    @patch("abfahrt.models.time.time", return_value=1000.0)
    def test_needs_refresh_recent(self, mock_time):
        """Verify that refresh is skipped when last fetch was 10s ago (within 30s interval)."""
        ctx = StationContext(
            station_id="900023201",
            station_name="Savignyplatz",
            last_fetch=990.0,
        )
        assert ctx.needs_refresh(30) is False

    @patch("abfahrt.models.time.time", return_value=1000.0)
    def test_needs_refresh_stale(self, mock_time):
        """Verify that refresh is triggered when last fetch was 40s ago (exceeds 30s interval)."""
        ctx = StationContext(
            station_id="900023201",
            station_name="Savignyplatz",
            last_fetch=960.0,
        )
        assert ctx.needs_refresh(30) is True
