"""Tests for infodisplay.models."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from infodisplay.models import Departure, StationContext, parse_departure


class TestParseDeparture:
    def test_normal_departure(self, sample_departure_raw):
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
        dep = parse_departure(sample_departure_raw)
        assert "Fahrradmitnahme möglich" in dep.remarks

    def test_warning_remark(self, sample_departure_raw):
        dep = parse_departure(sample_departure_raw)
        assert "Bauarbeiten" in dep.remarks

    def test_null_when(self, sample_departure_null_when):
        dep = parse_departure(sample_departure_null_when)
        assert dep.when is None
        assert dep.planned_when is not None

    def test_null_delay(self, sample_departure_null_when):
        dep = parse_departure(sample_departure_null_when)
        assert dep.delay_seconds is None

    def test_empty_remarks(self, sample_departure_no_remarks):
        dep = parse_departure(sample_departure_no_remarks)
        assert dep.remarks == []

    def test_cancelled(self, sample_departure_cancelled):
        dep = parse_departure(sample_departure_cancelled)
        assert dep.is_cancelled is True

    def test_missing_line_fields(self):
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
    def test_future_departure(self):
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
    def test_positive_delay(self):
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
    def test_creation(self):
        ctx = StationContext(station_id="900023201", station_name="Savignyplatz")
        assert ctx.station_id == "900023201"
        assert ctx.station_name == "Savignyplatz"
        assert ctx.departures == []
        assert ctx.last_fetch == 0.0

    def test_needs_refresh_initial(self):
        ctx = StationContext(station_id="900023201", station_name="Savignyplatz")
        assert ctx.needs_refresh(30) is True

    @patch("infodisplay.models.time.time", return_value=1000.0)
    def test_needs_refresh_recent(self, mock_time):
        ctx = StationContext(
            station_id="900023201",
            station_name="Savignyplatz",
            last_fetch=990.0,
        )
        assert ctx.needs_refresh(30) is False

    @patch("infodisplay.models.time.time", return_value=1000.0)
    def test_needs_refresh_stale(self, mock_time):
        ctx = StationContext(
            station_id="900023201",
            station_name="Savignyplatz",
            last_fetch=960.0,
        )
        assert ctx.needs_refresh(30) is True
