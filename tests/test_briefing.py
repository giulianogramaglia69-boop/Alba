# SPDX-License-Identifier: GPL-3.0-or-later
"""Test composizione briefing (offline, LLM finto)."""

import json

from alba.briefing import (
    build_prompt,
    compose_briefing,
    format_date_italian,
    gather_sources,
    render_template,
)
from alba.config import Config
from alba.fixtures import SAMPLE_COMMITS, SAMPLE_ICS, SAMPLE_WEATHER_JSON
from alba.gateway import Connection, GatewayError


class FakeGateway:
    def __init__(self, llm_reply=None, commits=None, fail_list=False):
        self.llm_reply = llm_reply
        self.commits = commits if commits is not None else SAMPLE_COMMITS
        self.fail_list = fail_list

    def list_connections(self):
        if self.fail_list:
            raise GatewayError("403 dal gateway")
        return [
            Connection("gh-1", "github", "alba-github"),
            Connection("or-1", "openrouter", "alba-llm"),
        ]

    def find_connection(self, connections, provider, hint):
        for c in connections:
            if c.provider == provider:
                return c
        return None

    def call(self, provider, connection_id, path, method="GET", json_body=None, headers=None):
        if provider == "openrouter":
            return self.llm_reply
        return self.commits


def _http_get(url):
    if "open-meteo" in url:
        return json.dumps(SAMPLE_WEATHER_JSON).encode()
    return SAMPLE_ICS.encode()


def _config():
    return Config(
        ics_url="https://example.invalid/cal.ics",
        repos=["giulianogramaglia69-boop/GG"],
        telegram_chat_id="123",
    )


def test_render_template_contains_all_sections():
    sources = gather_sources(_config(), FakeGateway(), http_get=_http_get)
    text = render_template(sources)
    assert "Agrigento" in text
    assert "Lezione di matematica" in text
    assert "Palestra" in text
    assert "GG" in text
    assert "package manager" in text


def test_render_template_marks_failed_source():
    sources = {
        "date": "oggi",
        "place": "Agrigento",
        "weather": {"error": "rete giù"},
        "events": [],
        "activity": {"error": "gateway giù"},
    }
    text = render_template(sources)
    assert "non disponibile" in text


def test_compose_uses_llm_when_available():
    sources = {"date": "oggi", "place": "Agrigento", "weather": {"error": "x"}, "events": [], "activity": {}}
    gw = FakeGateway(llm_reply={"choices": [{"message": {"content": "TESTO LLM"}}]})
    assert compose_briefing(sources, gw, "or-1", "m") == "TESTO LLM"


def test_compose_falls_back_to_template_when_llm_fails():
    sources = {"date": "oggi", "place": "Agrigento", "weather": {"error": "x"}, "events": [], "activity": {}}
    gw = FakeGateway(llm_reply={"error": {"message": "model not found"}})
    text = compose_briefing(sources, gw, "or-1", "m")
    assert "Buongiorno" in text


def test_compose_without_gateway_uses_template():
    sources = {"date": "oggi", "place": "Agrigento", "weather": {"error": "x"}, "events": [], "activity": {}}
    assert "Buongiorno" in compose_briefing(sources)


def test_gather_sources_never_raises():
    def broken(url):
        raise RuntimeError("tutto giù")

    sources = gather_sources(_config(), FakeGateway(fail_list=True), http_get=broken)
    assert "error" in sources["weather"]
    assert "error" in sources["events"]
    assert "error" in sources["activity"]


def test_build_prompt_is_italian_and_structured():
    sources = {"date": "oggi", "place": "Agrigento", "weather": {"error": "x"}, "events": [], "activity": {}}
    messages = build_prompt(sources)
    assert messages[0]["role"] == "system"
    assert "italiano" in messages[0]["content"]
    assert "meteo" in messages[0]["content"].lower()


def test_format_date_italian():
    from datetime import datetime

    assert format_date_italian(datetime(2026, 11, 25)) == "mercoledì 25 novembre 2026"
    assert format_date_italian(datetime(2026, 1, 1)) == "giovedì 1 gennaio 2026"
    assert format_date_italian(datetime(2026, 12, 31)) == "giovedì 31 dicembre 2026"
