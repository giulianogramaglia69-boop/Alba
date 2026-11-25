# SPDX-License-Identifier: GPL-3.0-or-later
"""Caricamento e validazione della configurazione di Alba.

Il file di configurazione è TOML (stdlib: tomllib, Python >= 3.11).
Il file vero (config/alba.toml) resta FUORI dal repo: contiene l'URL ICS
privato di Google Calendar e il chat id Telegram. Nel repo va solo
config/alba.toml.example, con placeholder.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


class ConfigError(ValueError):
    """Configurazione mancante o non valida."""


# Valori che indicano "da compilare": se un campo richiesto li contiene,
# la configurazione è considerata incompleta (doctor lo segnala).
PLACEHOLDERS = ("", "REPLACE_ME", "CHANGEME", "TODO")


def _is_placeholder(value: str) -> bool:
    value = value.strip()
    return value in PLACEHOLDERS or value.startswith("<") or value.endswith(">")


@dataclass
class Config:
    timezone: str = "Europe/Rome"
    briefing_hour: int = 7
    briefing_minute: int = 17
    latitude: float = 37.27
    longitude: float = 13.62
    place_name: str = "Agrigento"
    ics_url: str = ""
    repos: list[str] = field(default_factory=list)
    telegram_chat_id: str = ""
    model: str = "meta-llama/llama-3.3-70b-instruct:free"
    gateway_base_url: str = "https://api.sprites.dev"
    sprite_name_prefix: str = "alba"
    # Nomi (o frammenti di nome) delle connessioni Sprites, come appaiono
    # in GET /v1/gateway/list. Sono nomi, non credenziali.
    github_connection: str = "github"
    openrouter_connection: str = "openrouter"
    telegram_connection: str = "telegram"
    http_port: int = 8080

    def missing_required(self) -> list[str]:
        """Campi richiesti mancanti o ancora placeholder."""
        missing = []
        if _is_placeholder(self.ics_url):
            missing.append("ics_url (link iCalendar privato di Google Calendar)")
        if _is_placeholder(self.telegram_chat_id):
            missing.append("telegram_chat_id")
        if not self.repos:
            missing.append("repos (almeno un repo owner/repo)")
        return missing


def load_config(path: str | Path) -> Config:
    """Carica config/alba.toml. Solleva ConfigError se manca o non è valido."""
    path = Path(path)
    if not path.exists():
        raise ConfigError(
            f"config non trovato: {path} — copia config/alba.toml.example "
            "in config/alba.toml e compila i campi"
        )
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"config TOML non valido ({path}): {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"config TOML non valido ({path}): radice non è una tabella")

    cfg = Config()
    for section, fields in (
        ("briefing", ("timezone", "briefing_hour", "briefing_minute")),
        ("weather", ("latitude", "longitude", "place_name")),
        ("calendar", ("ics_url",)),
        ("github", ("repos",)),
        ("telegram", ("telegram_chat_id",)),
        ("llm", ("model",)),
        ("gateway", ("gateway_base_url", "sprite_name_prefix")),
        ("connections", ("github_connection", "openrouter_connection", "telegram_connection")),
        ("serve", ("http_port",)),
    ):
        table = data.get(section, {})
        if not isinstance(table, dict):
            raise ConfigError(f"sezione [{section}] non valida in {path}")
        for key in fields:
            if key in table:
                setattr(cfg, key, table[key])

    # Validazione tipi di base (errori chiari, non traceback oscuri).
    if not isinstance(cfg.briefing_hour, int) or not 0 <= cfg.briefing_hour <= 23:
        raise ConfigError("briefing_hour deve essere un intero tra 0 e 23")
    if not isinstance(cfg.briefing_minute, int) or not 0 <= cfg.briefing_minute <= 59:
        raise ConfigError("briefing_minute deve essere un intero tra 0 e 59")
    if not isinstance(cfg.repos, list) or not all(
        isinstance(r, str) and "/" in r for r in cfg.repos
    ):
        raise ConfigError("repos deve essere una lista di 'owner/repo'")
    for key in ("ics_url", "telegram_chat_id", "model", "timezone"):
        if not isinstance(getattr(cfg, key), str):
            raise ConfigError(f"{key} deve essere una stringa")
    return cfg
