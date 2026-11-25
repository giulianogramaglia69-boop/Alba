# SPDX-License-Identifier: GPL-3.0-or-later
"""Composizione del briefing: raccoglie le fonti, l'LLM scrive il testo.

Loop agente (semplice, senza framework): raccogli le fonti -> l'LLM
decide cosa è importante e scrive il briefing -> consegna. Se una fonte
fallisce, il briefing lo dice in una riga invece di morire. Se l'LLM
fallisce, c'è un fallback deterministico (template) così il briefing
arriva comunque, solo meno rifinito.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .calendar_ics import Event, fetch_today_events
from .config import Config
from .gateway import GatewayClient
from .github_activity import format_activity, summarize_activity
from .llm import DEFAULT_MODEL, complete
from .weather import Weather, fetch_weather

SYSTEM_PROMPT = (
    "Sei Alba, l'agente che scrive il briefing del mattino per Giuliano. "
    "Scrivi in italiano, conciso e diretto, niente filler, niente saluti. "
    "Struttura: prima il meteo (una riga), poi gli appuntamenti di oggi "
    "(orario e titolo, uno per riga), poi l'attività dei repo (una riga per "
    "repo). Tieni solo ciò che conta per la giornata: se non c'è niente, "
    "dillo in una riga. Se una fonte è mancata, segnalalo in una riga. "
    "Lunghezza massima: circa 15 righe."
)

# strftime dipende dalla locale del sistema (spesso inglese): la data del
# briefing si formatta a mano, sempre in italiano.
_GIORNI = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
_MESI = [
    "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
    "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre",
]


def format_date_italian(now: datetime) -> str:
    return f"{_GIORNI[now.weekday()]} {now.day} {_MESI[now.month - 1]} {now.year}"


def gather_sources(config: Config, gateway: GatewayClient | None, http_get=None) -> dict:
    """Raccoglie meteo, eventi e attività GitHub. Mai un'eccezione: ogni
    fonte che fallisce diventa {"error": "..."} e il briefing lo segnala."""
    tz = ZoneInfo(config.timezone)
    now = datetime.now(tz)
    sources: dict = {"date": format_date_italian(now), "place": config.place_name}

    try:
        weather = fetch_weather(config.latitude, config.longitude, config.timezone, http_get)
        sources["weather"] = weather
    except Exception as exc:  # noqa: BLE001 - una fonte non deve uccidere il briefing
        sources["weather"] = {"error": str(exc)}

    try:
        sources["events"] = fetch_today_events(config.ics_url, config.timezone, http_get)
    except Exception as exc:  # noqa: BLE001
        sources["events"] = {"error": str(exc)}

    if gateway is not None:
        try:
            connections = gateway.list_connections()
            github = gateway.find_connection(connections, "github", config.github_connection)
            if github is None:
                raise RuntimeError("connettore GitHub non trovato (vedi alba doctor)")
            since = (now - timedelta(days=1)).isoformat()
            sources["activity"] = summarize_activity(
                gateway, github.id, config.repos, since
            )
        except Exception as exc:  # noqa: BLE001
            sources["activity"] = {"error": str(exc)}
    else:
        sources["activity"] = {"error": "gateway non disponibile"}
    return sources


def _sources_as_text(sources: dict) -> str:
    lines = [f"Data: {sources.get('date', '')} — Luogo: {sources.get('place', '')}"]
    weather = sources.get("weather")
    if isinstance(weather, Weather):
        lines.append(f"Meteo: {weather.format(sources.get('place', ''))}")
    elif isinstance(weather, dict):
        lines.append(f"Meteo: non disponibile ({weather.get('error', '?')})")

    events = sources.get("events")
    if isinstance(events, list):
        if events:
            lines.append("Appuntamenti di oggi:")
            lines.extend(f"  - {e.format()}" for e in events)
        else:
            lines.append("Appuntamenti di oggi: nessuno")
    elif isinstance(events, dict):
        lines.append(f"Appuntamenti: non disponibili ({events.get('error', '?')})")

    activity = sources.get("activity")
    if isinstance(activity, dict) and "error" not in activity:
        lines.append("Attività GitHub (da ieri):")
        lines.extend(f"  - {line}" for line in format_activity(activity))
    elif isinstance(activity, dict):
        lines.append(f"Attività GitHub: non disponibile ({activity.get('error', '?')})")
    return "\n".join(lines)


def build_prompt(sources: dict) -> list[dict]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": _sources_as_text(sources)},
    ]


def render_template(sources: dict) -> str:
    """Fallback deterministico senza LLM: briefing leggibile, non rifinito."""
    title = f"☀️ Buongiorno — {sources.get('date', '')}"
    return f"{title}\n\n{_sources_as_text(sources)}"


def compose_briefing(
    sources: dict,
    gateway: GatewayClient | None = None,
    openrouter_connection_id: str | None = None,
    model: str = DEFAULT_MODEL,
) -> str:
    """Scrive il briefing. Con gateway + connessione OpenRouter usa l'LLM,
    altrimenti (o se l'LLM fallisce) usa il template."""
    if gateway is not None and openrouter_connection_id:
        try:
            return complete(gateway, openrouter_connection_id, model, build_prompt(sources))
        except Exception:
            pass  # fallback: meglio un briefing semplice che niente
    return render_template(sources)


def build_briefing(config: Config, gateway: GatewayClient | None = None) -> str:
    """Raccoglie le fonti e compone il briefing (LLM se disponibile)."""
    sources = gather_sources(config, gateway)
    openrouter_id = None
    if gateway is not None:
        try:
            connections = gateway.list_connections()
            conn = gateway.find_connection(connections, "openrouter", config.openrouter_connection)
            openrouter_id = conn.id if conn else None
        except Exception:
            openrouter_id = None
    return compose_briefing(sources, gateway, openrouter_id, config.model)
