"""Pull live weather (Open-Meteo) for the simulation locale."""

from __future__ import annotations

import time

import httpx

from sim.config import WEATHER_LAT, WEATHER_LON


def fetch_weather() -> str:
    try:
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={WEATHER_LAT}&longitude={WEATHER_LON}"
            "&current=temperature_2m,weather_code,wind_speed_10m"
            "&timezone=auto"
        )
        with httpx.Client(timeout=10.0) as client:
            data = client.get(url).json()
        cur = data.get("current", {})
        temp = cur.get("temperature_2m", "?")
        code = int(cur.get("weather_code", 0))
        desc = _wmo_desc(code)
        wind = cur.get("wind_speed_10m", 0)
        return f"{desc}, {temp}°C, wind {wind} km/h"
    except Exception:
        return "Weather unavailable (using last known conditions)"


def _wmo_desc(code: int) -> str:
    if code == 0:
        return "Clear"
    if code in (1, 2, 3):
        return "Partly cloudy"
    if code in (45, 48):
        return "Fog"
    if code in (51, 53, 55, 61, 63, 65):
        return "Rain"
    if code in (80, 81, 82):
        return "Showers"
    if code >= 95:
        return "Thunderstorm"
    return "Variable"
