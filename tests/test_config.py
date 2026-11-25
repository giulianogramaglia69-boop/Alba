# SPDX-License-Identifier: GPL-3.0-or-later
"""Test caricamento configurazione TOML."""

import pytest

from alba.config import ConfigError, load_config

MINIMAL_VALID = """[calendar]
ics_url = "https://example.invalid/cal.ics"
[github]
repos = ["o/r"]
[telegram]
telegram_chat_id = "123"
"""


def _write(tmp_path, text, name="alba.toml"):
    path = tmp_path / name
    path.write_text(text)
    return str(path)


def test_load_minimal_valid_config(tmp_path):
    cfg = load_config(_write(tmp_path, MINIMAL_VALID))
    assert cfg.timezone == "Europe/Rome"
    assert cfg.briefing_hour == 7 and cfg.briefing_minute == 17
    assert cfg.latitude == 37.27
    assert cfg.repos == ["o/r"]
    assert cfg.missing_required() == []


def test_load_example_config_flags_placeholders(tmp_path):
    import shutil

    src = "/home/hatch/workspace/Alba/config/alba.toml.example"
    cfg = load_config(shutil.copy(src, tmp_path / "alba.toml"))
    missing = cfg.missing_required()
    assert any("ics_url" in m for m in missing)
    assert any("telegram_chat_id" in m for m in missing)


def test_missing_file_raises(tmp_path):
    with pytest.raises(ConfigError, match="config non trovato"):
        load_config(tmp_path / "nope.toml")


def test_invalid_toml_raises(tmp_path):
    with pytest.raises(ConfigError, match="TOML non valido"):
        load_config(_write(tmp_path, "[briefing\nchiusa male"))


def test_bad_hour_raises(tmp_path):
    with pytest.raises(ConfigError, match="briefing_hour"):
        load_config(_write(tmp_path, MINIMAL_VALID + "\n[briefing]\nbriefing_hour = 25\n"))


def test_bad_repos_raises(tmp_path):
    with pytest.raises(ConfigError, match="repos"):
        load_config(_write(tmp_path, MINIMAL_VALID.replace('repos = ["o/r"]', 'repos = ["senza-slash"]')))


def test_missing_required_lists_all(tmp_path):
    cfg = load_config(_write(tmp_path, ""))
    missing = cfg.missing_required()
    assert len(missing) == 3  # ics_url, telegram_chat_id, repos
