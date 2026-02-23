"""Main application orchestrator with multi-station rotation."""

from __future__ import annotations

import logging
import time

from infodisplay.api import BVGClient
from infodisplay.config import Config
from infodisplay.display import render_error
from infodisplay.models import StationContext
from infodisplay.renderer import DepartureRenderer
from infodisplay.weather import WeatherData, fetch_weather

logger = logging.getLogger(__name__)


class InfoDisplayApp:
    """Orchestrates fetching, rendering, and displaying departure boards."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.client = BVGClient(config)
        self.renderer = DepartureRenderer(
            width=config.display.width,
            height=config.display.height,
            font_header=config.fonts.font_header,
            font_main=config.fonts.font_main,
            font_remark=config.fonts.font_remark,
            station_name_size=config.fonts.station_name_size,
            header_size=config.fonts.header_size,
            departure_size=config.fonts.departure_size,
            remark_size=config.fonts.remark_size,
            show_remarks=config.display.show_remarks,
        )
        if config.display.mode == "ssd1322":
            from infodisplay.ssd1322_display import SSD1322Display
            self.display = SSD1322Display(
                width=config.display.width,
                height=config.display.height,
            )
        else:
            from infodisplay.display import DepartureDisplay
            self.display = DepartureDisplay(
                width=config.display.width,
                height=config.display.height,
                fullscreen=config.display.fullscreen,
            )
        self.stations: list[StationContext] = []
        self.active_station_index = 0
        self.last_rotation_time = 0.0
        self.weather: WeatherData | None = None
        self.frame_interval = 1.0 / config.display.fps

    def _resolve_stations(self) -> None:
        """Resolve station names for all configured stations."""
        for station_cfg in self.config.stations:
            name = station_cfg.name
            if not name:
                try:
                    name = self.client.get_station_name(station_cfg.id)
                    logger.info("Resolved station %s → %s", station_cfg.id, name)
                except Exception:
                    logger.warning("Could not resolve name for station %s", station_cfg.id)
                    name = f"Station {station_cfg.id}"
            self.stations.append(
                StationContext(
                    station_id=station_cfg.id,
                    station_name=name,
                    walking_minutes=station_cfg.walking_minutes,
                    lines=station_cfg.lines,
                )
            )

    def _refresh_station(self, ctx: StationContext) -> None:
        """Fetch fresh departures for a station if needed."""
        if not ctx.needs_refresh(self.config.refresh.interval_seconds):
            return
        try:
            logger.debug("Fetching departures for %s ...", ctx.station_name)
            t0 = time.time()
            ctx.departures = self.client.fetch_parsed_departures(ctx.station_id)
            elapsed = time.time() - t0
            ctx.last_fetch = time.time()
            logger.info(
                "Fetched %d departures for %s (%.1fs)",
                len(ctx.departures), ctx.station_name, elapsed,
            )
        except Exception:
            logger.warning(
                "Failed to fetch departures for %s", ctx.station_name, exc_info=True
            )
            if not ctx.departures:
                ctx.last_fetch = time.time()

    def _refresh_weather(self) -> None:
        """Fetch weather if stale or missing."""
        cfg = self.config.weather
        if self.weather and time.time() - self.weather.fetch_time < cfg.refresh_seconds:
            return
        try:
            logger.debug("Fetching weather ...")
            self.weather = fetch_weather(cfg.latitude, cfg.longitude)
            logger.info(
                "Weather: %.0f° (%.0f/%.0f°), precip %s",
                self.weather.current_temp, self.weather.daily_low,
                self.weather.daily_high, self.weather.precip_summary,
            )
        except Exception:
            logger.warning("Failed to fetch weather", exc_info=True)

    def _check_rotation(self, scrolling_done: bool) -> None:
        """Rotate to the next station if the interval has elapsed and scrolling is done."""
        if len(self.stations) <= 1:
            return
        now = time.time()
        if now - self.last_rotation_time >= self.config.rotation.interval_seconds and scrolling_done:
            self.active_station_index = (self.active_station_index + 1) % len(self.stations)
            self.last_rotation_time = now
            self.renderer._scroll_start = time.time()
            logger.info("Rotated to station: %s", self.stations[self.active_station_index].station_name)

    def run(self) -> None:
        """Run the main application loop."""
        try:
            logger.info(
                "Starting InfoDisplayApp with %d station(s), refresh=%ds, rotation=%ds",
                len(self.config.stations),
                self.config.refresh.interval_seconds,
                self.config.rotation.interval_seconds,
            )
            self._resolve_stations()

            if not self.stations:
                logger.error("No stations configured")
                return

            self.last_rotation_time = time.time()

            # Initial fetch for weather + all stations
            self._refresh_weather()
            for ctx in self.stations:
                self._refresh_station(ctx)

            logger.info("Entering main loop")
            running = True
            while running:
                running = self.display.handle_events()
                if not running:
                    break

                # Refresh weather + stations that need it
                self._refresh_weather()
                for ctx in self.stations:
                    self._refresh_station(ctx)

                # Render the active station (filter by walking time + line)
                # Show departures within hurry tolerance (3 min before walking time)
                ctx = self.stations[self.active_station_index]
                walk = ctx.walking_minutes
                hurry = max(0, walk - 3)
                visible = [
                    d for d in ctx.departures
                    if d.minutes_until is None or d.minutes_until >= hurry
                ]
                if ctx.lines:
                    visible = [d for d in visible if d.line_name in ctx.lines]
                # Fall back to all departures if filter removes everything
                if not visible:
                    visible = ctx.departures

                scrolling_done = True
                if visible:
                    img, scrolling_done = self.renderer.render(visible, ctx.station_name, walk, self.weather)
                elif ctx.last_fetch > 0:
                    img = render_error(
                        "Keine Abfahrten",
                        self.config.display.width,
                        self.config.display.height,
                    )
                else:
                    img = render_error(
                        "Netzwerkfehler",
                        self.config.display.width,
                        self.config.display.height,
                    )

                # Check rotation after rendering (needs scroll status)
                self._check_rotation(scrolling_done)

                self.display.update(img)
                time.sleep(self.frame_interval)
        finally:
            self.display.close()
