# SPDX-License-Identifier: GPL-3.0-or-later
"""Client per il gateway dei connettori Fly.io Sprites.

Come funziona (da docs.fly.io): la credenziale vive nell'organizzazione
Sprites. Lo Sprite chiama il gateway e il gateway allega la credenziale
alla richiesta verso il provider. Lo Sprite NON vede mai il token.

Regola d'oro di questo modulo: NON invia mai un header Authorization.
Se il codice chiamante prova a passarne uno, la chiamata viene rifiutata
con ValueError prima ancora di partire. Così un token non può finire
per sbaglio nel traffico o nei log.

Le chiamate al gateway devono partire da dentro uno Sprite (la richiesta
è firmata da Fly.io): dal laptop o dalla VM di sviluppo tornano 403.
`alba doctor` lo verifica e lo dice in chiaro.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass


class GatewayError(RuntimeError):
    """Errore del gateway Sprites (rete, HTTP, risposta non valida)."""


@dataclass
class Connection:
    id: str
    provider: str
    name: str = ""
    labels: dict | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "Connection":
        return cls(
            id=str(data.get("id", "")),
            provider=str(data.get("provider", "")),
            name=str(data.get("name", "") or data.get("label", "") or ""),
            labels=data.get("labels") if isinstance(data.get("labels"), dict) else None,
        )


class GatewayClient:
    """Client minimale per https://api.sprites.dev/v1/gateway.

    `http_request` è iniettabile (method, url, body: bytes|None, headers)
    -> (status, body: bytes): i test usano un finto trasporto, niente rete.
    """

    def __init__(self, base_url: str = "https://api.sprites.dev", http_request=None):
        self.base_url = base_url.rstrip("/")
        self._http_request = http_request or _default_http_request

    # -- discovery -----------------------------------------------------
    def list_connections(self) -> list[Connection]:
        """GET /v1/gateway/list — le connessioni visibili a questo Sprite."""
        status, body = self._http_request("GET", f"{self.base_url}/v1/gateway/list", None, {})
        if status != 200:
            raise GatewayError(f"gateway list: HTTP {status}: {body[:200]!r}")
        try:
            data = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise GatewayError(f"gateway list: risposta non JSON: {body[:200]!r}") from exc
        items = data if isinstance(data, list) else data.get("connections", [])
        if not isinstance(items, list):
            raise GatewayError(f"gateway list: formato inatteso: {data!r}")
        return [Connection.from_dict(c) for c in items if isinstance(c, dict)]

    def find_connection(
        self, connections: list[Connection], provider: str, name_hint: str
    ) -> Connection | None:
        """Trova una connessione per provider e frammento di nome (case-insensitive).

        Restituisce None se non c'è: è `doctor` a segnalarlo, non un crash.
        """
        hint = name_hint.lower()
        for conn in connections:
            if conn.provider.lower() != provider.lower():
                continue
            if hint in conn.name.lower() or hint in (conn.id or "").lower():
                return conn
        return None

    # -- chiamate ai provider ------------------------------------------
    def call(
        self,
        provider: str,
        connection_id: str,
        path: str,
        method: str = "GET",
        json_body: dict | None = None,
        headers: dict | None = None,
    ):
        """Chiama un provider attraverso il gateway.

        URL: {base}/v1/gateway/{provider}/{connection_id}/{path}.
        Il gateway allega la credenziale; qui non si allega MAI Authorization.
        Restituisce il JSON decodificato (o il testo grezzo se non è JSON).
        """
        headers = dict(headers or {})
        lowered = {k.lower() for k in headers}
        if "authorization" in lowered:
            raise ValueError(
                "rifiutato: non inviare header Authorization al gateway — "
                "la credenziale la allega il gateway, lo Sprite non la vede mai"
            )
        url = f"{self.base_url}/v1/gateway/{provider}/{connection_id}/{path.lstrip('/')}"
        body = json.dumps(json_body).encode("utf-8") if json_body is not None else None
        send_headers = {"Accept": "application/json"}
        if body is not None:
            send_headers["Content-Type"] = "application/json"
        send_headers.update(headers)
        status, raw = self._http_request(method.upper(), url, body, send_headers)
        if status >= 400:
            raise GatewayError(f"{provider} {path}: HTTP {status}: {raw[:300]!r}")
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return raw.decode("utf-8", errors="replace")


def _default_http_request(method: str, url: str, body: bytes | None, headers: dict):
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()
    except urllib.error.URLError as exc:
        raise GatewayError(f"richiesta a {url} fallita: {exc.reason}") from exc
