# SPDX-License-Identifier: GPL-3.0-or-later
"""Consegna su Telegram via connettore Sprites Custom API.

Il bot token è statico e lunga durata: perfetto per un Custom API
(base URL + token + dove va). Il gateway allega il token: qui non
compare mai nessuna credenziale. Il percorso chiamato è "sendMessage"
e il corpo è quello standard di Bot API.
"""

from __future__ import annotations

from .gateway import GatewayClient, GatewayError

TELEGRAM_MAX_LENGTH = 4096


class TelegramError(RuntimeError):
    """L'invio su Telegram non è riuscito."""


def send_message(
    gateway: GatewayClient,
    connection_id: str,
    chat_id: str,
    text: str,
) -> dict:
    """POST sendMessage. Ritorna la risposta del gateway.

    Telegram accetta al massimo 4096 caratteri: oltre, il testo viene
    troncato con una nota (meglio un briefing corto che un invio fallito).
    """
    if len(text) > TELEGRAM_MAX_LENGTH:
        text = text[: TELEGRAM_MAX_LENGTH - 40] + "\n…[testo troncato]"
    try:
        data = gateway.call(
            "telegram",
            connection_id,
            "sendMessage",
            method="POST",
            json_body={"chat_id": chat_id, "text": text},
        )
    except GatewayError as exc:
        raise TelegramError(f"Telegram: {exc}") from exc
    if isinstance(data, dict) and data.get("ok") is False:
        raise TelegramError(f"Telegram: {data.get('description', data)!r}")
    return data if isinstance(data, dict) else {"ok": True, "result": data}
