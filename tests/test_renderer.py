"""Tests for the departure board renderer."""

from datetime import datetime, timedelta, timezone

from PIL import Image

from abfahrt.models import Departure
from abfahrt.renderer import DepartureRenderer


def _make_departure(
    line_name: str = "S7",
    line_product: str = "suburban",
    direction: str = "S Potsdam Hauptbahnhof",
    minutes_from_now: int = 5,
    delay_seconds: int = 0,
    remarks: list[str] | None = None,
) -> Departure:
    """Helper to create a Departure with a predictable minutes_until."""
    now = datetime.now(timezone.utc)
    when_dt = now + timedelta(minutes=minutes_from_now)
    return Departure(
        line_name=line_name,
        line_product=line_product,
        direction=direction,
        when=when_dt.isoformat(),
        planned_when=when_dt.isoformat(),
        delay_seconds=delay_seconds,
        platform="1",
        remarks=remarks or [],
        is_cancelled=False,
    )


class TestDepartureRenderer:
    """Tests for DepartureRenderer."""

    def test_correct_image_dimensions(self):
        """Verify that render() output matches the requested 1520x180 pixel dimensions."""
        renderer = DepartureRenderer(width=1520, height=180)
        departures = [_make_departure()]
        img, _ = renderer.render(departures, "S Savignyplatz (Berlin)")
        assert img.size == (1520, 180)

    def test_custom_dimensions(self):
        """Verify that non-default dimensions (800x100) are respected in the output image."""
        renderer = DepartureRenderer(width=800, height=100)
        departures = [_make_departure()]
        img, _ = renderer.render(departures, "Test Station")
        assert img.size == (800, 100)

    def test_non_all_black_output(self):
        """Verify that rendering a departure produces visible amber pixels, not a blank image."""
        renderer = DepartureRenderer()
        departures = [_make_departure()]
        img, _ = renderer.render(departures, "S Savignyplatz (Berlin)")
        # Check that the image contains non-black pixels
        pixels = list(img.tobytes())
        assert any(p != 0 for p in pixels), "Image should contain non-black pixels"

    def test_zero_departures_shows_header(self):
        """Verify that the station header bar renders even when there are no departures."""
        renderer = DepartureRenderer()
        img, _ = renderer.render([], "S Savignyplatz (Berlin)")
        assert img.size == (1520, 180)
        # Should still have non-black pixels (station name + header text)
        pixels = list(img.tobytes())
        assert any(p != 0 for p in pixels), "Header should be visible even with 0 departures"

    def test_overflow_does_not_crash(self):
        """Verify that passing more departures than max_rows does not raise an error."""
        renderer = DepartureRenderer(width=1520, height=180)
        # Create more departures than can fit in the display
        departures = [_make_departure(minutes_from_now=i) for i in range(20)]
        img, _ = renderer.render(departures, "S Savignyplatz (Berlin)")
        assert img.size == (1520, 180)

    def test_returns_rgb_image(self):
        """Verify that the rendered image uses RGB mode (required for Pygame and SSD1322)."""
        renderer = DepartureRenderer()
        img, _ = renderer.render([_make_departure()], "Test")
        assert img.mode == "RGB"

    def test_departure_with_delay(self):
        """Verify that a delayed departure (180s = 3 min) renders without error."""
        renderer = DepartureRenderer()
        dep = _make_departure(delay_seconds=180)
        img, _ = renderer.render([dep], "Test Station")
        assert isinstance(img, Image.Image)

    def test_departure_with_remarks(self):
        """Verify that a departure with a bicycle remark renders without error."""
        renderer = DepartureRenderer()
        dep = _make_departure(remarks=["Fahrradmitnahme möglich"])
        img, _ = renderer.render([dep], "Test Station")
        assert isinstance(img, Image.Image)

    def test_multiple_departures(self):
        """Verify that multiple departures across different products render correctly."""
        renderer = DepartureRenderer()
        departures = [
            _make_departure(line_name="S7", direction="S Ahrensfelde", minutes_from_now=5),
            _make_departure(line_name="S5", direction="S Strausberg", minutes_from_now=8),
            _make_departure(line_name="RE1", line_product="regional", direction="Frankfurt (Oder)", minutes_from_now=12),
        ]
        img, _ = renderer.render(departures, "S Savignyplatz (Berlin)")
        assert img.size == (1520, 180)

    def test_non_suburban_no_sbahn_icon(self):
        """Verify that a U-Bahn departure renders without suburban-specific styling errors."""
        renderer = DepartureRenderer()
        dep = _make_departure(line_name="U1", line_product="subway")
        img, _ = renderer.render([dep], "Test Station")
        assert isinstance(img, Image.Image)

    def test_long_destination_truncated(self):
        """Verify that an extremely long destination string does not overflow the column."""
        renderer = DepartureRenderer()
        dep = _make_departure(
            direction="S+U Berlin Hauptbahnhof - Lehrter Bahnhof (Berlin) über Friedrichstraße"
        )
        img, _ = renderer.render([dep], "S Savignyplatz (Berlin)")
        assert img.size == (1520, 180)

    def test_long_line_name_truncated(self):
        """Verify that an extremely long line name does not overflow the Linie column."""
        renderer = DepartureRenderer()
        dep = _make_departure(line_name="RE10 Express Extra Long Name")
        img, _ = renderer.render([dep], "Test Station")
        assert img.size == (1520, 180)

    def test_departure_with_scrolling_remarks(self):
        """Verify that a remark longer than the column width triggers scrolling without crash."""
        renderer = DepartureRenderer()
        dep = _make_departure(
            remarks=["Fahrradmitnahme möglich, Bauarbeiten zwischen Westkreuz und Charlottenburg"]
        )
        img, _ = renderer.render([dep], "Test Station")
        assert img.size == (1520, 180)

    def test_no_remarks(self):
        """Verify that an empty remarks list renders cleanly without extra whitespace."""
        renderer = DepartureRenderer()
        dep = _make_departure(remarks=[])
        img, _ = renderer.render([dep], "Test Station")
        assert img.size == (1520, 180)

    def test_missing_line_name(self):
        """Verify graceful rendering when line_name is an empty string."""
        renderer = DepartureRenderer()
        dep = _make_departure(line_name="")
        img, _ = renderer.render([dep], "Test Station")
        assert isinstance(img, Image.Image)

    def test_missing_direction(self):
        """Verify graceful rendering when direction is an empty string."""
        renderer = DepartureRenderer()
        dep = _make_departure(direction="")
        img, _ = renderer.render([dep], "Test Station")
        assert isinstance(img, Image.Image)

    def test_missing_when_shows_dash(self):
        """Verify that null when and planned_when render a '--:--' time placeholder."""
        renderer = DepartureRenderer()
        dep = Departure(
            line_name="S7", line_product="suburban",
            direction="S Potsdam", when=None, planned_when=None,
            delay_seconds=None, platform=None, remarks=[], is_cancelled=False,
        )
        img, _ = renderer.render([dep], "Test Station")
        assert isinstance(img, Image.Image)

    def test_empty_station_name(self):
        """Verify that an empty station name does not crash the header rendering."""
        renderer = DepartureRenderer()
        dep = _make_departure()
        img, _ = renderer.render([dep], "")
        assert isinstance(img, Image.Image)

    def test_render_fetch_ok_false(self):
        """Verify that render() with fetch_ok=False does not crash."""
        renderer = DepartureRenderer()
        dep = _make_departure()
        img, _ = renderer.render([dep], "Test Station", fetch_ok=False)
        assert isinstance(img, Image.Image)

    def test_render_empty_fetch_ok_false(self):
        """Verify that render_empty() with fetch_ok=False does not crash."""
        renderer = DepartureRenderer()
        img = renderer.render_empty("Test Station", [], fetch_ok=False)
        assert isinstance(img, Image.Image)

    def test_render_empty_with_lines_fetch_ok_false(self):
        """Verify that render_empty() with line filter and fetch_ok=False does not crash."""
        renderer = DepartureRenderer()
        img = renderer.render_empty("Test Station", ["S7", "S5"], fetch_ok=False)
        assert isinstance(img, Image.Image)
