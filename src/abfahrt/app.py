"""Main application orchestrator with multi-station rotation."""

from __future__ import annotations

import logging
import signal
import time

try:
    import sdnotify
except ImportError:
    sdnotify = None

from abfahrt.api import BVGClient
from abfahrt.config import Config
from abfahrt.display import render_boot_screen, render_error
from abfahrt.models import StationContext
from abfahrt.renderer import DepartureRenderer
from abfahrt.weather import WeatherData, fetch_weather

logger = logging.getLogger(__name__)


class InfoDisplayApp:
    """Orchestrates fetching, rendering, and displaying departure boards."""

    def __init__(self, config: Config) -> None:
        """Initialize the departure display application.

        Creates the API client, renderer, and display backend. The display
        backend is selected at runtime based on config.display.mode, with
        lazy imports so neither Pygame nor luma.oled is required unless
        actually used. This allows the same codebase to run on a desktop
        (Pygame) or Raspberry Pi (SSD1322) without installing unused deps.

        Args:
            config: Fully assembled application configuration.
        """
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
            show_items=config.display.show_items,
        )
        # Lazy import: only import the selected display backend.
        # Avoids requiring pygame on Pi or luma.oled on desktop.
        if config.display.mode == "ssd1322":
            from abfahrt.ssd1322_display import SSD1322Display
            self.display = SSD1322Display(
                width=config.display.width,
                height=config.display.height,
            )
        else:
            from abfahrt.display import DepartureDisplay
            self.display = DepartureDisplay(
                width=config.display.width,
                height=config.display.height,
                fullscreen=config.display.fullscreen,
            )
        # Runtime state for multi-station rotation
        self.stations: list[StationContext] = []
        self.active_station_index = 0
        self.last_rotation_time = 0.0
        self.weather: WeatherData | None = None
        self.frame_interval = 1.0 / config.display.fps
        self._running = False
        # sd-notify: no-op if sdnotify not installed or NOTIFY_SOCKET not set
        self._notifier = sdnotify.SystemdNotifier() if sdnotify else None

    def _notify(self, state: str) -> None:
        """Send a notification to systemd (no-op outside systemd)."""
        if self._notifier:
            self._notifier.notify(state)

    def _show_boot(self, status: str) -> None:
        """Render and display a boot screen with the given status message."""
        self._notify(f"STATUS={status}")
        img = render_boot_screen(status, self.config.display.width, self.config.display.height)
        self.display.update(img)
        self.display.handle_events()

    def _resolve_stations(self) -> None:
        """Resolve station names for all configured stations."""
        for station_cfg in self.config.stations:
            name = station_cfg.name
            if not name:
                try:
                    name = self.client.get_station_name(station_cfg.id, timeout=3)
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

    def _refresh_station(self, ctx: StationContext, timeout: int = 10) -> None:
        """Fetch fresh departures for a station if needed."""
        if not ctx.needs_refresh(self.config.refresh.interval_seconds):
            return
        try:
            logger.debug("Fetching departures for %s ...", ctx.station_name)
            t0 = time.time()
            ctx.departures = self.client.fetch_parsed_departures(ctx.station_id, timeout=timeout)
            elapsed = time.time() - t0
            ctx.last_fetch = time.time()
            ctx.fetch_ok = True
            logger.info(
                "Fetched %d departures for %s (%.1fs)",
                len(ctx.departures), ctx.station_name, elapsed,
            )
        except Exception:
            logger.warning(
                "Failed to fetch departures for %s", ctx.station_name, exc_info=True
            )
            ctx.fetch_ok = False
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
        # Rotation is scroll-gated: only switch when all scrolling remarks
        # completed one full cycle.
        if now - self.last_rotation_time >= self.config.rotation.interval_seconds and scrolling_done:
            self.active_station_index = (self.active_station_index + 1) % len(self.stations)
            self.last_rotation_time = now
            # Reset scroll timer so new station's remarks start from beginning
            self.renderer._scroll_start = time.time()
            logger.info("Rotated to station: %s", self.stations[self.active_station_index].station_name)

    def run(self) -> None:
        """Run the main application loop."""
        signal.signal(signal.SIGTERM, lambda *_: setattr(self, '_running', False))
        try:
            logger.info(
                "Starting InfoDisplayApp with %d station(s), refresh=%ds, rotation=%ds",
                len(self.config.stations),
                self.config.refresh.interval_seconds,
                self.config.rotation.interval_seconds,
            )
            boot_start = time.time()
            self._show_boot("Stationen laden...")
            self._resolve_stations()

            if not self.stations:
                logger.error("No stations configured")
                return

            self.last_rotation_time = time.time()

            # Initial fetch for weather + all stations (non-blocking: main loop retries on failure)
            self._show_boot("Wetter laden...")
            self._refresh_weather()
            self._show_boot("Abfahrten laden...")
            for ctx in self.stations:
                self._refresh_station(ctx, timeout=3)
                self.display.handle_events()
            self._show_boot("Hacke-di-hack!")

            # Ensure boot screen is visible for at least 3 seconds total
            remaining = 3.0 - (time.time() - boot_start)
            if remaining > 0:
                # Pump events during the wait so the window stays responsive
                deadline = time.time() + remaining
                while time.time() < deadline:
                    self.display.handle_events()
                    time.sleep(0.05)

            self._notify("READY=1")
            self._notify("STATUS=Running")
            logger.info("Entering main loop")
            self._running = True
            while self._running:
                if not self.display.handle_events():
                    break

                # Refresh weather + stations that need it
                self._refresh_weather()
                for ctx in self.stations:
                    self._refresh_station(ctx)

                # Hurry-zone filtering: hide departures user cannot catch.
                # hurry = walking_minutes - 3, clamped to min 1.
                # Departures within [hurry, walking_minutes] blink.
                ctx = self.stations[self.active_station_index]
                walk = ctx.walking_minutes
                hurry = max(1, walk - 3)
                visible = [
                    d for d in ctx.departures
                    if d.minutes_until is not None and d.minutes_until >= hurry
                ]
                # Per-station line filter. If configured lines produce zero
                # results, show empty state.
                if ctx.lines:
                    line_filtered = [d for d in visible if d.line_name in ctx.lines]
                    if line_filtered:
                        visible = line_filtered
                    else:
                        visible = []

                # Three rendering paths:
                # 1) departures exist -> board
                # 2) no departures but fetch ok -> 'Keine Abfahrten'
                # 3) no fetch yet -> 'Netzwerkfehler'
                scrolling_done = True
                if visible:
                    img, scrolling_done = self.renderer.render(
                        visible, ctx.station_name, walk, self.weather,
                        # weather_page cycles with station index to alternate temp/precip display
                        weather_page=self.active_station_index,
                        fetch_ok=ctx.fetch_ok,
                    )
                elif ctx.last_fetch > 0:
                    img = self.renderer.render_empty(
                        ctx.station_name, ctx.lines,
                        weather=self.weather,
                        weather_page=self.active_station_index,
                        fetch_ok=ctx.fetch_ok,
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
                self._notify("WATCHDOG=1")
                time.sleep(self.frame_interval)
        finally:
            self._notify("STOPPING=1")
            self.display.close()
