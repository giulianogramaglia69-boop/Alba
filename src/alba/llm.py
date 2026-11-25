# SPDX-License-Identifier: GPL-3.0-or-later
"""LLM via connettore Sprites OpenRouter (managed).

Il connettore managed dà accesso al catalogo modelli OpenRouter senza
account OpenRouter; il costo sta nel piano Sprites. Il gateway allega la
chiave: qui non compare mai nessuna credenziale.

Modello di default: un modello free del catalogo (i modelli free ruotano:
se OpenRouter risponde "model not found", cambialo in config/alba.toml).
"""

from __future__ import annotations

from .gateway import GatewayClient, GatewayError

DEFAULT_MODEL = "meta-llama/llama-3.3-70b-instruct:free"


class LLMError(RuntimeError):
    """L'LLM non ha risposto o ha risposto in modo non valido."""


def complete(
    gateway: GatewayClient,
    connection_id: str,
    model: str,
    messages: list[dict],
    temperature: float = 0.3,
    max_tokens: int = 800,
) -> str:
    """Una chat completion OpenRouter via gateway. Ritorna il testo."""
    try:
        data = gateway.call(
            "openrouter",
            connection_id,
            "api/v1/chat/completions",
            method="POST",
            json_body={
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
        )
    except GatewayError as exc:
        raise LLMError(f"OpenRouter: {exc}") from exc
    if isinstance(data, dict) and "error" in data:
        err = data["error"]
        msg = err.get("message", err) if isinstance(err, dict) else err
        raise LLMError(f"OpenRouter: {msg}")
    try:
        text = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError(f"OpenRouter: risposta inattesa: {data!r}") from exc
    if not isinstance(text, str) or not text.strip():
        raise LLMError("OpenRouter: risposta vuota")
    return text.strip()
