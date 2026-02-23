"""Configuration loading: defaults → YAML overlay → argparse overlay."""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class StationConfig:
    id: str = "900023201"
    name: str = ""
    walking_minutes: int = 5
    lines: list[str] = field(default_factory=list)


@dataclass
class DisplayConfig:
    mode: str = "pygame"  # "pygame" or "ssd1322"
    width: int = 1520
    height: int = 180
    fullscreen: bool = False
    fps: int = 30
    show_remarks: bool = True
    show_items: int = 4
    background_color: list[int] = field(default_factory=lambda: [0, 0, 0])
    text_color: list[int] = field(default_factory=lambda: [255, 170, 0])


@dataclass
class RefreshConfig:
    interval_seconds: int = 30
    departure_count: int = 20


@dataclass
class FilterConfig:
    suburban: bool = True
    subway: bool = True
    tram: bool = True
    bus: bool = False
    ferry: bool = False
    express: bool = True
    regional: bool = True


@dataclass
class RotationConfig:
    interval_seconds: int = 10


@dataclass
class FontConfig:
    font_header: str = "Transit_Wide_Bold.ttf"
    font_main: str = "Transit_Bold.ttf"
    font_remark: str = "Transit_Condensed_Normal.ttf"
    station_name_size: int = 20
    header_size: int = 13
    departure_size: int = 18
    remark_size: int = 13


@dataclass
class WeatherConfig:
    latitude: float = 52.5170  # Berlin Friedrichshain
    longitude: float = 13.4540
    refresh_seconds: int = 600  # 10 minutes


@dataclass
class Config:
    stations: list[StationConfig] = field(default_factory=lambda: [StationConfig()])
    rotation: RotationConfig = field(default_factory=RotationConfig)
    display: DisplayConfig = field(default_factory=DisplayConfig)
    refresh: RefreshConfig = field(default_factory=RefreshConfig)
    filters: FilterConfig = field(default_factory=FilterConfig)
    fonts: FontConfig = field(default_factory=FontConfig)
    weather: WeatherConfig = field(default_factory=WeatherConfig)
    # CLI-only flags (not in YAML)
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
        for key in ("suburban", "subway", "tram", "bus", "ferry", "express", "regional"):
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
