# SPDX-License-Identifier: GPL-3.0-or-later
"""CLI di Alba: `alba doctor`, `alba briefing`, `alba serve`.

- doctor: controlli (config, gateway, connettori, niente token in env).
- briefing: genera il briefing e lo stampa. --dry-run usa dati fittizi
  (niente rete, niente LLM, niente invio). --send lo invia su Telegram.
- serve: loop giornaliero alle 07:17 + server HTTP :8080.
"""

from __future__ import annotations

import argparse
import sys

from . import __version__
from .briefing import build_briefing, compose_briefing
from .config import Config, ConfigError, load_config
from .doctor import doctor_ok, format_report, run_doctor
from .fixtures import SAMPLE_COMMITS, SAMPLE_ICS, SAMPLE_WEATHER_JSON
from .gateway import GatewayClient
from .serve import run_once, serve
from .weather import Weather


def _load_or_die(path: str) -> Config:
    try:
        return load_config(path)
    except ConfigError as exc:
        print(f"alba: {exc}", file=sys.stderr)
        sys.exit(2)


def _dry_run_briefing() -> str:
    """Briefing con dati fittizi: niente rete, niente LLM, niente invio."""
    from datetime import date

    from .calendar_ics import events_today, parse_ics
    from .github_activity import Commit

    weather_data = SAMPLE_WEATHER_JSON["daily"]
    weather = Weather(
        temp_min=float(weather_data["temperature_2m_min"][0]),
        temp_max=float(weather_data["temperature_2m_max"][0]),
        condition="Parzialmente nuvoloso",
        wind_gust_max=float(weather_data["wind_gusts_10m_max"][0]),
        precip_prob_max=int(weather_data["precipitation_probability_max"][0]),
    )
    # La fixture è datata 25 nov 2026: la giornata è fissata, così il
    # dry-run mostra sempre gli eventi (anche se lanciato un altro giorno).
    events = events_today(parse_ics(SAMPLE_ICS), "Europe/Rome", today=date(2026, 11, 25))
    commits = [
        Commit(
            sha=c["sha"][:7],
            message=c["commit"]["message"].splitlines()[0],
            author=c["commit"]["author"]["name"],
            date=c["commit"]["author"]["date"],
        )
        for c in SAMPLE_COMMITS
    ]
    sources = {
        "date": "mercoledì 25 novembre 2026",
        "place": "Agrigento",
        "weather": weather,
        "events": events,
        "activity": {"giulianogramaglia69-boop/GG": {"commits": commits}},
    }
    return compose_briefing(sources)


def cmd_doctor(args: argparse.Namespace) -> int:
    checks = run_doctor(args.config)
    print(format_report(checks))
    return 0 if doctor_ok(checks) else 1


def cmd_briefing(args: argparse.Namespace) -> int:
    if args.dry_run:
        print(_dry_run_briefing())
        return 0
    config = _load_or_die(args.config)
    gateway = GatewayClient(config.gateway_base_url)
    text = build_briefing(config, gateway)
    print(text)
    if args.send:
        run_once(config, gateway, send=True)
        print("\n[inviato su Telegram]", file=sys.stderr)
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    config = _load_or_die(args.config)
    gateway = GatewayClient(config.gateway_base_url)
    serve(config, gateway)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="alba", description="Mini-agente di briefing del mattino")
    parser.add_argument("--version", action="version", version=f"alba {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_doctor = sub.add_parser("doctor", help="controlla config, gateway e connettori")
    p_doctor.add_argument("--config", default="config/alba.toml")
    p_doctor.set_defaults(func=cmd_doctor)

    p_briefing = sub.add_parser("briefing", help="genera il briefing e lo stampa")
    p_briefing.add_argument("--config", default="config/alba.toml")
    p_briefing.add_argument("--dry-run", action="store_true", help="dati fittizi, niente rete")
    p_briefing.add_argument("--send", action="store_true", help="invia anche su Telegram")
    p_briefing.set_defaults(func=cmd_briefing)

    p_serve = sub.add_parser("serve", help="loop giornaliero + server HTTP :8080")
    p_serve.add_argument("--config", default="config/alba.toml")
    p_serve.set_defaults(func=cmd_serve)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
