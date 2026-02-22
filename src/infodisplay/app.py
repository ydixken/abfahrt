"""Main application orchestrator with multi-station rotation."""

from __future__ import annotations

import logging
import time

from infodisplay.api import BVGClient
from infodisplay.config import Config
from infodisplay.display import DepartureDisplay, render_error
from infodisplay.models import StationContext
from infodisplay.renderer import DepartureRenderer

logger = logging.getLogger(__name__)


class InfoDisplayApp:
    """Orchestrates fetching, rendering, and displaying departure boards."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.client = BVGClient(config)
        self.renderer = DepartureRenderer(
            width=config.display.width,
            height=config.display.height,
            header_size=config.fonts.header_size,
            departure_size=config.fonts.departure_size,
            remark_size=config.fonts.remark_size,
        )
        self.display = DepartureDisplay(
            width=config.display.width,
            height=config.display.height,
            fullscreen=config.display.fullscreen,
        )
        self.stations: list[StationContext] = []
        self.active_station_index = 0
        self.last_rotation_time = 0.0
        self.clock = __import__("pygame").time.Clock()

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
                StationContext(station_id=station_cfg.id, station_name=name)
            )

    def _refresh_station(self, ctx: StationContext) -> None:
        """Fetch fresh departures for a station if needed."""
        if not ctx.needs_refresh(self.config.refresh.interval_seconds):
            return
        try:
            ctx.departures = self.client.fetch_parsed_departures(ctx.station_id)
            ctx.last_fetch = time.time()
            logger.info(
                "Fetched %d departures for %s", len(ctx.departures), ctx.station_name
            )
        except Exception:
            logger.warning("Failed to fetch departures for %s", ctx.station_name)
            if not ctx.departures:
                ctx.last_fetch = time.time()

    def _check_rotation(self) -> None:
        """Rotate to the next station if the interval has elapsed."""
        if len(self.stations) <= 1:
            return
        now = time.time()
        if now - self.last_rotation_time >= self.config.rotation.interval_seconds:
            self.active_station_index = (self.active_station_index + 1) % len(self.stations)
            self.last_rotation_time = now
            logger.info("Rotated to station: %s", self.stations[self.active_station_index].station_name)

    def run(self) -> None:
        """Run the main application loop."""
        try:
            self._resolve_stations()

            if not self.stations:
                logger.error("No stations configured")
                return

            self.last_rotation_time = time.time()

            # Initial fetch for all stations
            for ctx in self.stations:
                self._refresh_station(ctx)

            running = True
            while running:
                running = self.display.handle_events()
                if not running:
                    break

                # Refresh stations that need it
                for ctx in self.stations:
                    self._refresh_station(ctx)

                # Check rotation timer
                self._check_rotation()

                # Render the active station
                ctx = self.stations[self.active_station_index]
                if ctx.departures:
                    img = self.renderer.render(ctx.departures, ctx.station_name)
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

                self.display.update(img)
                self.clock.tick(self.config.display.fps)
        finally:
            self.display.close()
