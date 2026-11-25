# SPDX-License-Identifier: GPL-3.0-or-later
"""Test meteo Open-Meteo (offline: http_get finto)."""

import json

import pytest

from alba.fixtures import SAMPLE_WEATHER_JSON
from alba.weather import WMO_DESCRIPTIONS, Weather, WeatherError, fetch_weather


def _http_get(payload):
    def fake(url):
        fake.last_url = url
        return json.dumps(payload).encode()

    fake.last_url = None
    return fake


def test_parse_sample_json():
    w = fetch_weather(37.27, 13.62, http_get=_http_get(SAMPLE_WEATHER_JSON))
    assert w.temp_min == 15.0
    assert w.temp_max == 19.0
    assert w.condition == "Parzialmente nuvoloso"
    assert w.wind_gust_max == 43.0
    assert w.precip_prob_max == 10


def test_wmo_descriptions():
    assert WMO_DESCRIPTIONS[0] == "Sereno"
    assert WMO_DESCRIPTIONS[95] == "Temporale"
    assert WMO_DESCRIPTIONS[61] == "Pioggia leggera"


def test_format_includes_wind_when_strong():
    w = Weather(15, 19, "Parzialmente nuvoloso", 43.0, 10)
    text = w.format("Agrigento")
    assert "min 15° / max 19°" in text
    assert "43 km/h" in text
    assert "10%" in text


def test_format_omits_precip_and_wind_when_calm():
    w = Weather(10, 20, "Sereno", 12.0, 0)
    text = w.format("Agrigento")
    assert "pioggia" not in text
    assert "km/h" not in text
    assert "Sereno" in text or "sereno" in text


def test_missing_daily_raises():
    with pytest.raises(WeatherError):
        fetch_weather(37.27, 13.62, http_get=_http_get({"foo": 1}))


def test_invalid_json_raises():
    with pytest.raises(WeatherError):
        fetch_weather(37.27, 13.62, http_get=lambda url: b"non json {")
