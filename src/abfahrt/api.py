"""BVG Transport REST API client."""

from __future__ import annotations

import requests

from abfahrt.config import Config
from abfahrt.models import Departure, parse_departure

BASE_URL = "https://v6.bvg.transport.rest"


class BVGClient:
    """Client for the BVG Transport REST API v6."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})

    def get_departures(self, station_id: str) -> list[dict]:
        """Fetch raw departure dicts from the API.

        GET /stops/{id}/departures with filter params and 10s timeout.
        """
        filters = self.config.filters
        params = {
            "duration": 60,
            "results": self.config.refresh.departure_count,
            "suburban": str(filters.suburban).lower(),
            "subway": str(filters.subway).lower(),
            "tram": str(filters.tram).lower(),
            "bus": str(filters.bus).lower(),
            "ferry": str(filters.ferry).lower(),
            "express": str(filters.express).lower(),
            "regional": str(filters.regional).lower(),
        }
        resp = self.session.get(
            f"{BASE_URL}/stops/{station_id}/departures",
            params=params,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("departures", data) if isinstance(data, dict) else data

    def search_stations(self, query: str) -> list[dict]:
        """Search for stations by name.

        GET /locations?query={query}&results=5
        """
        resp = self.session.get(
            f"{BASE_URL}/locations",
            params={"query": query, "results": 5},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()

    def get_station_name(self, station_id: str) -> str:
        """Get the display name for a station.

        GET /stops/{id}
        """
        resp = self.session.get(
            f"{BASE_URL}/stops/{station_id}",
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("name", f"Station {station_id}")

    def fetch_parsed_departures(self, station_id: str) -> list[Departure]:
        """Fetch departures, parse, and sort by time."""
        raw_list = self.get_departures(station_id)
        departures = [parse_departure(raw) for raw in raw_list]
        departures.sort(key=lambda d: d.when or d.planned_when or "")
        return departures
