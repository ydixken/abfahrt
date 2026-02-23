"""Weather client using Open-Meteo API (no API key required)."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import requests

logger = logging.getLogger(__name__)

# Open-Meteo free forecast API — no API key required, no rate limit
# for reasonable use. Docs: https://open-meteo.com/en/docs
BASE_URL = "https://api.open-meteo.com/v1/forecast"


@dataclass
class WeatherData:
    """Current weather snapshot with daily extremes and precipitation forecast."""

    current_temp: float   # Current temperature in °C
    daily_low: float      # Today's minimum temperature in °C
    daily_high: float     # Today's maximum temperature in °C
    precip_next_12h: list[float]  # Hourly precipitation in mm, next 12 hours
    fetch_time: float = 0.0       # Unix timestamp when this data was fetched (for cache expiry)

    @property
    def precip_max(self) -> float:
        """Max hourly precipitation in the next 12h."""
        return max(self.precip_next_12h) if self.precip_next_12h else 0.0

    @property
    def precip_total(self) -> float:
        """Total precipitation in the next 12h."""
        return sum(self.precip_next_12h)

    @property
    def precip_summary(self) -> str:
        """Short precipitation summary for display."""
        total = self.precip_total
        if total == 0:
            return ""
        return f"{round(total)}mm"


def fetch_weather(lat: float, lon: float) -> WeatherData:
    """Fetch current weather from Open-Meteo.

    Returns a WeatherData with current temp, daily low/high, and
    hourly precipitation for the next 12 hours.
    """
    # Open-Meteo API parameters: current=real-time temp at 2m, daily=min/max,
    # hourly=precipitation per hour (mm), timezone=Berlin for daily boundaries,
    # forecast_hours=12 limits hourly data.
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m",
        "daily": "temperature_2m_min,temperature_2m_max",
        "hourly": "precipitation",
        "timezone": "Europe/Berlin",
        "forecast_days": 1,
        "forecast_hours": 12,
    }
    headers = {"User-Agent": "abfahrt (https://github.com/ydixken/abfahrt)"}
    resp = requests.get(BASE_URL, params=params, headers=headers, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    current_temp = data["current"]["temperature_2m"]
    daily_low = data["daily"]["temperature_2m_min"][0]
    daily_high = data["daily"]["temperature_2m_max"][0]
    # Safety truncation: ensure max 12 hourly values even if API returns extras.
    precip = data["hourly"]["precipitation"][:12]

    return WeatherData(
        current_temp=current_temp,
        daily_low=daily_low,
        daily_high=daily_high,
        precip_next_12h=precip,
        fetch_time=time.time(),
    )
