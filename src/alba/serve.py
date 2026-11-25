# SPDX-License-Identifier: GPL-3.0-or-later
"""Scheduler + server HTTP: `alba serve`.

Ogni giorno alle 07:17 (Europe/Rome) genera il briefing e lo invia su
Telegram. In più un server HTTP su :8080:
- GET /healthz  -> {"status": "ok"} (per lo Sprite / il controllo salute)
- GET /briefing -> genera un briefing on-demand e lo restituisce come JSON
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from zoneinfo import ZoneInfo

from .briefing import build_briefing
from .config import Config
from .gateway import GatewayClient
from .telegram import send_message


def next_run(now: datetime, hour: int = 7, minute: int = 17, tz_name: str = "Europe/Rome") -> datetime:
    """Il prossimo 07:17 (ora locale). Se oggi è già passato, domani.

    `now` deve essere consapevole del fuso; se è naive lo si interpreta
    nel fuso configurato. Gestisce il cambio ora legale/solare perché
    confronta orari locali, non timestamp assoluti.
    """
    tz = ZoneInfo(tz_name)
    now = now.astimezone(tz) if now.tzinfo is not None else now.replace(tzinfo=tz)
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if now >= target:
        target += timedelta(days=1)
    return target


def seconds_until_next_run(
    now: datetime, hour: int = 7, minute: int = 17, tz_name: str = "Europe/Rome"
) -> float:
    return (next_run(now, hour, minute, tz_name) - now).total_seconds()


def run_once(config: Config, gateway: GatewayClient | None = None, send: bool = True) -> str:
    """Genera il briefing; se send=True lo invia su Telegram. Ritorna il testo."""
    text = build_briefing(config, gateway)
    if send:
        if gateway is None:
            raise RuntimeError("invio impossibile: gateway non disponibile (vedi alba doctor)")
        connections = gateway.list_connections()
        conn = gateway.find_connection(connections, "telegram", config.telegram_connection)
        if conn is None:
            raise RuntimeError("connettore Telegram non trovato (vedi alba doctor)")
        send_message(gateway, conn.id, config.telegram_chat_id, text)
    return text


class _Handler(BaseHTTPRequestHandler):
    config: Config
    gateway: GatewayClient | None

    def log_message(self, *args):  # silenzioso: niente log per ogni health check
        pass

    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802 - nome richiesto da http.server
        if self.path == "/healthz":
            self._json(200, {"status": "ok"})
        elif self.path == "/briefing":
            try:
                text = run_once(self.config, self.gateway, send=False)
                self._json(200, {"briefing": text})
            except Exception as exc:  # noqa: BLE001 - errore in JSON, non traceback
                self._json(500, {"error": str(exc)})
        else:
            self._json(404, {"error": "not found"})


def make_server(config: Config, gateway: GatewayClient | None, port: int) -> ThreadingHTTPServer:
    handler = type("AlbaHandler", (_Handler,), {"config": config, "gateway": gateway})
    return ThreadingHTTPServer(("0.0.0.0", port), handler)


def serve(config: Config, gateway: GatewayClient | None = None) -> None:
    """Loop infinito: HTTP server in background + briefing alle 07:17."""
    import time

    server = make_server(config, gateway, config.http_port)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"Alba in ascolto su :{config.http_port} (/healthz, /briefing)")
    tz = ZoneInfo(config.timezone)
    while True:
        now = datetime.now(tz)
        target = next_run(now, config.briefing_hour, config.briefing_minute, config.timezone)
        wait = (target - now).total_seconds()
        print(f"Prossimo briefing: {target:%Y-%m-%d %H:%M %Z} (tra {wait / 3600:.1f} ore)")
        time.sleep(wait)
        try:
            text = run_once(config, gateway, send=True)
            print(f"Briefing inviato ({len(text)} caratteri)")
        except Exception as exc:  # noqa: BLE001 - domani si riprova
            print(f"Briefing fallito: {exc}")
