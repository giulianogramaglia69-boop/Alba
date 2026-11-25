# SPDX-License-Identifier: GPL-3.0-or-later
"""`alba doctor` — controlli prima di partire.

Verifica, in ordine, con messaggi chiari (mai traceback oscuri):
1. la configurazione esiste, è valida e non ha più placeholder;
2. il gateway Sprites è raggiungibile (da fuori di uno Sprite torna 403);
3. i tre connettori richiesti (GitHub, OpenRouter, Telegram) sono presenti;
4. NESSUN token grezzo nelle variabili d'ambiente: se trova
   TELEGRAM_BOT_TOKEN, GITHUB_TOKEN, OPENROUTER_API_KEY o simili,
   è un errore — le credenziali vivono nel gateway, non in env.

Ogni controllo è (nome, ok, dettaglio). Exit code 0 solo se tutti i
controlli obbligatori passano.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

from .config import Config, ConfigError, load_config
from .gateway import GatewayClient, GatewayError

# Nomi di variabili che NON devono mai esistere: un token in env significa
# che qualcuno ha aggirato il gateway. Si controlla il nome, non il valore
# (il valore non viene mai stampato).
FORBIDDEN_ENV_PATTERNS = (
    re.compile(r"TOKEN", re.IGNORECASE),
    re.compile(r"API[_-]?KEY", re.IGNORECASE),
    re.compile(r"SECRET", re.IGNORECASE),
    re.compile(r"PASSWORD", re.IGNORECASE),
    re.compile(r"CLIENT[_-]?SECRET", re.IGNORECASE),
)


@dataclass
class Check:
    name: str
    ok: bool
    detail: str
    required: bool = True


def find_raw_tokens(env: dict | None = None) -> list[str]:
    """Nomi di variabili d'ambiente sospette (token/secret). Mai i valori."""
    env = os.environ if env is None else env
    found = []
    for key in env:
        if key.startswith(("ALBA_", "SPRITE_")):
            continue  # variabili operative di Alba/Sprite, non credenziali
        if any(p.search(key) for p in FORBIDDEN_ENV_PATTERNS):
            found.append(key)
    return sorted(found)


def run_doctor(
    config_path: str = "config/alba.toml",
    gateway: GatewayClient | None = None,
    env: dict | None = None,
) -> list[Check]:
    checks: list[Check] = []

    try:
        config = load_config(config_path)
    except ConfigError as exc:
        return [Check("config", False, str(exc))]
    checks.append(Check("config", True, f"config valido ({config_path})"))
    missing = config.missing_required()
    if missing:
        checks.append(
            Check(
                "config-completo",
                False,
                "campi da compilare in config/alba.toml: " + ", ".join(missing),
            )
        )
    else:
        checks.append(Check("config-completo", True, "tutti i campi richiesti compilati"))

    raw_tokens = find_raw_tokens(env)
    if raw_tokens:
        checks.append(
            Check(
                "no-raw-tokens",
                False,
                "token grezzo nelle variabili d'ambiente (toglilo: le credenziali "
                "vivono nel gateway): " + ", ".join(raw_tokens),
            )
        )
    else:
        checks.append(Check("no-raw-tokens", True, "nessun token nelle variabili d'ambiente"))

    gateway = gateway or GatewayClient(config.gateway_base_url)
    try:
        connections = gateway.list_connections()
    except GatewayError as exc:
        checks.append(
            Check(
                "gateway",
                False,
                f"gateway non raggiungibile: {exc} — le chiamate al gateway "
                "devono partire da dentro uno Sprite (dal laptop tornano 403)",
            )
        )
        return checks
    checks.append(Check("gateway", True, f"gateway raggiungibile ({len(connections)} connessioni)"))

    for provider, hint, label in (
        ("github", config.github_connection, "GitHub"),
        ("openrouter", config.openrouter_connection, "OpenRouter"),
        ("telegram", config.telegram_connection, "Telegram"),
    ):
        conn = gateway.find_connection(connections, provider, hint)
        if conn is None:
            checks.append(
                Check(
                    f"connector-{provider}",
                    False,
                    f"connettore {label} non trovato: crealo nella dashboard Sprites "
                    f"(nome che contiene '{hint}') e imposta la policy per questo Sprite",
                )
            )
        else:
            checks.append(
                Check(
                    f"connector-{provider}",
                    True,
                    f"connettore {label} trovato: {conn.name or conn.id}",
                )
            )
    return checks


def format_report(checks: list[Check]) -> str:
    lines = []
    for check in checks:
        mark = "OK  " if check.ok else "FAIL"
        lines.append(f"[{mark}] {check.name}: {check.detail}")
    failed = [c for c in checks if not c.ok and c.required]
    if failed:
        lines.append(f"\n{len(failed)} controllo/i fallito/i — sistema prima di partire.")
    else:
        lines.append("\nTutto ok: Alba è pronta.")
    return "\n".join(lines)


def doctor_ok(checks: list[Check]) -> bool:
    return all(c.ok for c in checks if c.required)
