# SPDX-License-Identifier: GPL-3.0-or-later
"""Meteo da Open-Meteo (https://api.open-meteo.com/v1/forecast).

Niente auth, chiamata HTTP diretta dallo Sprite. Un solo giorno
(forecast_days=1), fuso orario locale per coerenza con il calendario.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass


class WeatherError(RuntimeError):
    """Il meteo non è disponibile (rete o risposta non valida)."""


# Codici WMO -> descrizione italiana (https://open-meteo.com/en/docs).
WMO_DESCRIPTIONS = {
    0: "Sereno",
    1: "Prevalentemente sereno",
    2: "Parzialmente nuvoloso",
    3: "Nuvoloso",
    45: "Nebbia",
    48: "Nebbia con brina",
    51: "Pioviggine leggera",
    53: "Pioviggine",
    55: "Pioviggine intensa",
    61: "Pioggia leggera",
    63: "Pioggia",
    65: "Pioggia intensa",
    66: "Pioggia gelata leggera",
    67: "Pioggia gelata",
    71: "Neve leggera",
    73: "Neve",
    75: "Neve intensa",
    77: "Grandine fine",
    80: "Rovesci leggeri",
    81: "Rovesci",
    82: "Rovesci intensi",
    85: "Rovesci di neve",
    86: "Rovesci di neve intensi",
    95: "Temporale",
    96: "Temporale con grandine leggera",
    99: "Temporale con grandine",
}


@dataclass
class Weather:
    temp_min: float
    temp_max: float
    condition: str
    wind_gust_max: float  # km/h
    precip_prob_max: int  # %

    def format(self, place_name: str) -> str:
        """Una riga leggibile, stile briefing."""
        text = (
            f"{place_name}: {self.condition.lower()}, "
            f"min {self.temp_min:.0f}° / max {self.temp_max:.0f}°"
        )
        if self.precip_prob_max > 0:
            text += f", probabilità di pioggia {self.precip_prob_max}%"
        if self.wind_gust_max >= 40:
            text += f", raffiche fino a {self.wind_gust_max:.0f} km/h"
        return text


def _default_http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        raise WeatherError(f"Open-Meteo: HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise WeatherError(f"Open-Meteo non raggiungibile: {exc.reason}") from exc


def fetch_weather(
    latitude: float,
    longitude: float,
    timezone: str = "Europe/Rome",
    http_get=None,
) -> Weather:
    """Scarica il meteo di oggi e lo restituisce come Weather."""
    http_get = http_get or _default_http_get
    params = urllib.parse.urlencode(
        {
            "latitude": latitude,
            "longitude": longitude,
            "daily": ",".join(
                [
                    "temperature_2m_max",
                    "temperature_2m_min",
                    "precipitation_probability_max",
                    "weathercode",
                    "wind_gusts_10m_max",
                ]
            ),
            "timezone": timezone,
            "forecast_days": "1",
        }
    )
    raw = http_get(f"https://api.open-meteo.com/v1/forecast?{params}")
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WeatherError(f"Open-Meteo: risposta non JSON: {raw[:200]!r}") from exc
    daily = data.get("daily")
    if not isinstance(daily, dict):
        raise WeatherError(f"Open-Meteo: campo 'daily' mancante: {data!r}")
    try:
        return Weather(
            temp_min=float(daily["temperature_2m_min"][0]),
            temp_max=float(daily["temperature_2m_max"][0]),
            condition=WMO_DESCRIPTIONS.get(int(daily["weathercode"][0]), "Condizioni variabili"),
            wind_gust_max=float(daily["wind_gusts_10m_max"][0]),
            precip_prob_max=int(daily["precipitation_probability_max"][0] or 0),
        )
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise WeatherError(f"Open-Meteo: risposta incompleta: {data!r}") from exc
