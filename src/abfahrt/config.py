"""Configuration loading: defaults → YAML overlay → argparse overlay."""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class StationConfig:
    """Per-station settings loaded from config.yaml.

    Each station entry defines a BVG stop to monitor, with optional
    walking time (used for hurry-zone filtering) and an optional line
    filter to restrict which lines are shown.

    Attributes:
        id: BVG 9-digit station ID (e.g. "900023201" for S Savignyplatz).
            Use --search to look up IDs by name.
        name: Display name shown in the amber header bar. If empty, the
            name is auto-resolved from the BVG API at startup.
        walking_minutes: Walking time from home to this station in minutes.
            Controls the hurry-zone threshold: departures within
            [walking_minutes - 3, walking_minutes] minutes blink.
        lines: Optional list of line names to show (e.g. ["S41", "S42"]).
            When empty, all departures matching global filters are shown.
    """

    # Default station: S Savignyplatz
    id: str = "900023201"
    name: str = ""
    # Minutes to walk from home to this station
    walking_minutes: int = 5
    lines: list[str] = field(default_factory=list)


@dataclass
class DisplayConfig:
    """Display window and hardware settings.

    Controls the rendering surface dimensions, display backend selection,
    and visual preferences. The mode field selects between a Pygame
    desktop window and the SSD1322 hardware OLED.

    Attributes:
        mode: Display backend — "pygame" for a desktop window, "ssd1322"
            for the hardware OLED via SPI.
        width: Display width in pixels. Desktop default: 1520, hardware: 256.
        height: Display height in pixels. Also controls dynamic font scaling
            (all sizes scale relative to a 128px base). Desktop default: 180.
        fullscreen: Run Pygame in fullscreen mode (ignored for ssd1322).
        fps: Target frames per second for the main render loop. Higher values
            produce smoother scrolling and blinking but use more CPU.
        show_remarks: Whether to show the scrolling remarks column. Set to
            False on small displays (ssd1322) to give more space to destinations.
        show_items: Number of departure rows to display. Font size is computed
            dynamically to fill the available vertical space with this many rows.
        background_color: RGB background color as [R, G, B]. Default: black.
        text_color: RGB text color as [R, G, B]. Default: amber (255, 170, 0).
    """

    mode: str = "pygame"
    # Desktop window default width in pixels
    width: int = 1520
    # Desktop window default height in pixels; drives font scaling
    height: int = 180
    fullscreen: bool = False
    # Target render loop frame rate
    fps: int = 30
    show_remarks: bool = True
    # Number of departure rows visible at once
    show_items: int = 4
    # RGB black background
    background_color: list[int] = field(default_factory=lambda: [0, 0, 0])
    # RGB amber — matches real BVG display color
    text_color: list[int] = field(default_factory=lambda: [255, 170, 0])


@dataclass
class RefreshConfig:
    """API refresh interval settings.

    Attributes:
        interval_seconds: Seconds between departure API fetches per station.
            Lower values mean fresher data but more API calls.
        departure_count: Maximum number of departures to request from the
            BVG API per station (passed as the 'results' query parameter).
    """

    # Seconds between API calls per station
    interval_seconds: int = 30
    # Max departures requested from the BVG API
    departure_count: int = 20


@dataclass
class FilterConfig:
    """Global transport type filters.

    Each boolean maps to a BVG product type and is passed as a query
    parameter to the departures API endpoint. Set to False to exclude
    that transport type from all stations.

    Attributes:
        suburban: S-Bahn (urban rail).
        subway: U-Bahn (metro).
        tram: Tram and MetroTram.
        bus: Bus lines (disabled by default to reduce clutter on rail-focused displays).
        express: Express trains (RE, RB — regional express).
        regional: Regional trains.
    """

    suburban: bool = True
    subway: bool = True
    tram: bool = True
    # Disabled by default to reduce clutter on rail-focused displays
    bus: bool = False
    express: bool = True
    regional: bool = True


@dataclass
class RotationConfig:
    """Multi-station rotation settings.

    Attributes:
        interval_seconds: Seconds to display each station before rotating
            to the next. Rotation is also gated on scroll completion — if
            remarks are still scrolling, rotation waits until they finish.
    """

    # Seconds before switching to the next station
    interval_seconds: int = 10


@dataclass
class FontConfig:
    """Font file and size configuration.

    Font files are loaded from the project's fonts/ directory. Sizes are
    base values that get scaled dynamically based on display height
    (see DepartureRenderer.__init__).

    Attributes:
        font_header: Filename for the header, line names, and column labels.
        font_main: Filename for departure text (destinations, times, minutes).
        font_remark: Filename for the scrolling remarks column.
        station_name_size: Base font size for the station name in the header bar.
        header_size: Base font size for column header labels.
        departure_size: Base font size for departure rows (dynamically overridden
            by DepartureRenderer to fill available vertical space).
        remark_size: Base font size for remarks text.
    """

    font_header: str = "JetBrainsMono-Bold.ttf"
    font_main: str = "JetBrainsMono-Medium.ttf"
    font_remark: str = "JetBrainsMono-Regular.ttf"
    # Base font size for station name in header bar
    station_name_size: int = 20
    # Base font size for column header labels
    header_size: int = 13
    # Base font size for departure rows (overridden dynamically)
    departure_size: int = 18
    # Base font size for scrolling remarks
    remark_size: int = 13


@dataclass
class WeatherConfig:
    """Weather display configuration.

    Coordinates default to Berlin Friedrichshain. Weather data is fetched
    from the Open-Meteo API and cached for refresh_seconds.

    Attributes:
        latitude: Latitude in decimal degrees for weather lookup.
        longitude: Longitude in decimal degrees for weather lookup.
        refresh_seconds: Cache duration in seconds before fetching new weather data.
    """

    # Berlin Friedrichshain coordinates
    latitude: float = 52.5170
    longitude: float = 13.4540
    # 10-minute cache before re-fetching weather
    refresh_seconds: int = 600


@dataclass
class Config:
    """Top-level application configuration.

    Assembled from three layers with increasing priority:
      1. Hardcoded defaults (dataclass field values)
      2. YAML file overlay (config.yaml or --config path)
      3. CLI argument overlay (--station-id, --refresh, etc.)

    Each layer only overrides values it explicitly sets; omitted values
    are inherited from the previous layer.

    Attributes:
        stations: List of stations to rotate between.
        rotation: Multi-station rotation settings.
        display: Display window/hardware settings.
        refresh: API refresh interval settings.
        filters: Global transport type filters.
        fonts: Font file and size configuration.
        weather: Weather display configuration.
        search: CLI-only: station name to search for (--search).
        fetch_test: CLI-only: if True, print departures to stdout and exit.
        render_test: CLI-only: if True, save test render to assets/ and exit.
        debug: CLI-only: if True, enable debug-level logging.
    """

    stations: list[StationConfig] = field(default_factory=lambda: [StationConfig()])
    rotation: RotationConfig = field(default_factory=RotationConfig)
    display: DisplayConfig = field(default_factory=DisplayConfig)
    refresh: RefreshConfig = field(default_factory=RefreshConfig)
    filters: FilterConfig = field(default_factory=FilterConfig)
    fonts: FontConfig = field(default_factory=FontConfig)
    weather: WeatherConfig = field(default_factory=WeatherConfig)
    # CLI-only flags (not persisted in YAML)
    search: str | None = None
    fetch_test: bool = False
    render_test: bool = False
    debug: bool = False


def _apply_yaml(config: Config, yaml_path: str) -> None:
    """Overlay YAML config values onto the Config object."""
    if not os.path.exists(yaml_path):
        return

    with open(yaml_path, "r") as f:
        data = yaml.safe_load(f)

    if not data:
        return

    if "stations" in data:
        config.stations = [
            StationConfig(
                id=str(s.get("id", "900023201")),
                name=s.get("name", ""),
                walking_minutes=s.get("walking_minutes", 5),
                lines=s.get("lines", []),
            )
            for s in data["stations"]
        ]

    if "rotation" in data:
        rot = data["rotation"]
        if "interval_seconds" in rot:
            config.rotation.interval_seconds = rot["interval_seconds"]

    if "display" in data:
        d = data["display"]
        for key in ("mode", "width", "height", "fullscreen", "fps", "show_remarks", "show_items", "background_color", "text_color"):
            if key in d:
                setattr(config.display, key, d[key])

    if "refresh" in data:
        r = data["refresh"]
        for key in ("interval_seconds", "departure_count"):
            if key in r:
                setattr(config.refresh, key, r[key])

    if "filters" in data:
        flt = data["filters"]
        for key in ("suburban", "subway", "tram", "bus", "express", "regional"):
            if key in flt:
                setattr(config.filters, key, flt[key])

    if "fonts" in data:
        fonts = data["fonts"]
        for key in ("font_header", "font_main", "font_remark", "station_name_size", "header_size", "departure_size", "remark_size"):
            if key in fonts:
                setattr(config.fonts, key, fonts[key])

    if "weather" in data:
        w = data["weather"]
        for key in ("latitude", "longitude", "refresh_seconds"):
            if key in w:
                setattr(config.weather, key, w[key])



def _build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser.

    All arguments are optional overlays on top of YAML config.
    The parser defines --config, --station-id, --fullscreen, --refresh,
    --rotation, --search, --fetch-test, --render-test, and --debug.
    """
    parser = argparse.ArgumentParser(
        prog="abfahrt",
        description="BVG Train Departure Display",
    )
    parser.add_argument(
        "--config",
        type=str,
        help="Path to YAML config file",
    )
    parser.add_argument(
        "--station-id",
        type=str,
        help="Single station ID override (skips rotation)",
    )
    parser.add_argument(
        "--fullscreen",
        action="store_true",
        default=None,
        help="Run in fullscreen mode",
    )
    parser.add_argument(
        "--refresh",
        type=int,
        help="Refresh interval in seconds",
    )
    parser.add_argument(
        "--rotation",
        type=int,
        help="Rotation interval in seconds",
    )
    parser.add_argument(
        "--search",
        type=str,
        help="Search for a station by name",
    )
    parser.add_argument(
        "--fetch-test",
        action="store_true",
        default=False,
        help="Fetch and print live departures to stdout",
    )
    parser.add_argument(
        "--render-test",
        action="store_true",
        default=False,
        help="Render mock departures to test_output.png",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        default=False,
        help="Enable debug logging",
    )
    return parser


def _apply_args(config: Config, args: argparse.Namespace) -> None:
    """Overlay CLI arguments onto the Config object."""
    if args.station_id:
        config.stations = [StationConfig(id=args.station_id, name="")]

    if args.fullscreen is True:
        config.display.fullscreen = True

    if args.refresh is not None:
        config.refresh.interval_seconds = args.refresh

    if args.rotation is not None:
        config.rotation.interval_seconds = args.rotation

    if args.search:
        config.search = args.search

    config.fetch_test = args.fetch_test
    config.render_test = args.render_test
    config.debug = args.debug


def load_config(
    yaml_path: str | None = None,
    cli_args: list[str] | None = None,
) -> Config:
    """Load config: defaults → YAML overlay → argparse overlay.

    Args:
        yaml_path: Path to YAML config file. Defaults to config.yaml in project root.
        cli_args: CLI arguments list. None means use sys.argv.
    """
    config = Config()

    parser = _build_parser()
    args = parser.parse_args(cli_args if cli_args is not None else None)

    # Default YAML path: config.yaml in project root (three levels up from
    # this file). CLI --config overrides.
    if yaml_path is None:
        if args.config:
            yaml_path = args.config
        else:
            yaml_path = os.path.join(
                Path(__file__).resolve().parent.parent.parent, "config.yaml"
            )

    _apply_yaml(config, yaml_path)
    _apply_args(config, args)

    return config
