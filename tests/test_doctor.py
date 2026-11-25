# SPDX-License-Identifier: GPL-3.0-or-later
"""Test `alba doctor` (offline: config in tmp, gateway finto)."""

from pathlib import Path

from alba.doctor import doctor_ok, find_raw_tokens, format_report, run_doctor
from alba.gateway import Connection, GatewayError

VALID_TOML = """[briefing]
timezone = "Europe/Rome"
briefing_hour = 7
briefing_minute = 17

[weather]
latitude = 37.27
longitude = 13.62
place_name = "Agrigento"

[calendar]
ics_url = "https://calendar.google.com/calendar/ical/xyz/private-abc/basic.ics"

[github]
repos = ["o/r"]

[telegram]
telegram_chat_id = "12345"

[llm]
model = "m"

[gateway]
gateway_base_url = "https://api.sprites.dev"
sprite_name_prefix = "alba"

[connections]
github_connection = "github"
openrouter_connection = "openrouter"
telegram_connection = "telegram"

[serve]
http_port = 8080
"""


class FakeGateway:
    def __init__(self, connections=None, fail=False):
        self._connections = connections or []
        self.fail = fail

    def list_connections(self):
        if self.fail:
            raise GatewayError("403 dal gateway (non sei in uno Sprite)")
        return self._connections

    def find_connection(self, connections, provider, hint):
        for c in connections:
            if c.provider == provider and hint in c.name:
                return c
        return None


def _write_config(tmp_path, text=VALID_TOML):
    path = tmp_path / "alba.toml"
    path.write_text(text)
    return str(path)


def test_doctor_missing_config_fails_clearly(tmp_path):
    checks = run_doctor(str(tmp_path / "manca.toml"), gateway=FakeGateway(), env={})
    assert len(checks) == 1
    assert not checks[0].ok
    assert "config non trovato" in checks[0].detail
    assert "alba.toml.example" in checks[0].detail


def test_doctor_placeholders_reported(tmp_path):
    text = VALID_TOML.replace(
        'ics_url = "https://calendar.google.com/calendar/ical/xyz/private-abc/basic.ics"',
        'ics_url = "REPLACE_ME"',
    )
    checks = run_doctor(_write_config(tmp_path, text), gateway=FakeGateway(), env={})
    failed = [c for c in checks if not c.ok]
    assert any(c.name == "config-completo" for c in failed)


def test_doctor_env_token_detected_but_value_never_shown(tmp_path):
    env = {"TELEGRAM_BOT_TOKEN": "123456:ABC-segreto", "HOME": "/home/x"}
    checks = run_doctor(_write_config(tmp_path), gateway=FakeGateway(), env=env)
    bad = [c for c in checks if c.name == "no-raw-tokens"]
    assert bad and not bad[0].ok
    assert "TELEGRAM_BOT_TOKEN" in bad[0].detail
    assert "ABC-segreto" not in bad[0].detail  # il valore non si stampa mai
    assert "123456" not in bad[0].detail


def test_doctor_gateway_unreachable_explains_sprite(tmp_path):
    checks = run_doctor(_write_config(tmp_path), gateway=FakeGateway(fail=True), env={})
    bad = [c for c in checks if c.name == "gateway"]
    assert bad and not bad[0].ok
    assert "Sprite" in bad[0].detail


def test_doctor_missing_connector_reported(tmp_path):
    conns = [Connection("1", "github", "alba-github")]
    checks = run_doctor(_write_config(tmp_path), gateway=FakeGateway(conns), env={})
    names = {c.name: c.ok for c in checks}
    assert names["connector-github"] is True
    assert names["connector-openrouter"] is False
    assert names["connector-telegram"] is False


def test_doctor_all_ok(tmp_path):
    conns = [
        Connection("1", "github", "alba-github"),
        Connection("2", "openrouter", "alba-openrouter"),
        Connection("3", "telegram", "alba-telegram"),
    ]
    checks = run_doctor(_write_config(tmp_path), gateway=FakeGateway(conns), env={})
    assert doctor_ok(checks)
    assert "Tutto ok" in format_report(checks)


def test_find_raw_tokens_ignores_alba_vars():
    env = {"ALBA_DEBUG": "1", "SPRITE_NAME": "alba-dev", "OPENROUTER_API_KEY": "sk-x"}
    assert find_raw_tokens(env) == ["OPENROUTER_API_KEY"]
