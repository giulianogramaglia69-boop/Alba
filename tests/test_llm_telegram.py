# SPDX-License-Identifier: GPL-3.0-or-later
"""Test LLM OpenRouter e Telegram via gateway finto (offline)."""

import pytest

from alba.gateway import GatewayError
from alba.llm import DEFAULT_MODEL, LLMError, complete
from alba.telegram import TELEGRAM_MAX_LENGTH, TelegramError, send_message


class FakeGateway:
    def __init__(self, payload=None, fail_with=None):
        self.payload = payload
        self.fail_with = fail_with
        self.requested = []

    def call(self, provider, connection_id, path, method="GET", json_body=None, headers=None):
        self.requested.append((provider, connection_id, path, method, json_body))
        if self.fail_with is not None:
            raise self.fail_with
        return self.payload


# --- LLM -----------------------------------------------------------------

def test_llm_complete_returns_text_and_correct_path():
    gw = FakeGateway({"choices": [{"message": {"content": "  ciao mondo  "}}]})
    text = complete(gw, "or-1", "some-model", [{"role": "user", "content": "x"}])
    assert text == "ciao mondo"
    provider, conn, path, method, body = gw.requested[0]
    assert provider == "openrouter"
    assert path == "api/v1/chat/completions"
    assert method == "POST"
    assert body["model"] == "some-model"
    assert body["messages"][0]["content"] == "x"


def test_llm_default_model_is_free():
    assert DEFAULT_MODEL.endswith(":free")


def test_llm_error_field_raises():
    gw = FakeGateway({"error": {"message": "model not found"}})
    with pytest.raises(LLMError, match="model not found"):
        complete(gw, "or-1", "nope", [])


def test_llm_empty_choices_raises():
    gw = FakeGateway({"choices": []})
    with pytest.raises(LLMError):
        complete(gw, "or-1", "m", [])


def test_llm_gateway_failure_raises():
    gw = FakeGateway(fail_with=GatewayError("403"))
    with pytest.raises(LLMError):
        complete(gw, "or-1", "m", [])


# --- Telegram ------------------------------------------------------------

def test_telegram_send_message_payload():
    gw = FakeGateway({"ok": True, "result": {"message_id": 1}})
    out = send_message(gw, "tg-1", "12345", "buongiorno")
    assert out["ok"] is True
    provider, conn, path, method, body = gw.requested[0]
    assert provider == "telegram"
    assert path == "sendMessage"
    assert method == "POST"
    assert body == {"chat_id": "12345", "text": "buongiorno"}


def test_telegram_truncates_overlong_text():
    gw = FakeGateway({"ok": True})
    send_message(gw, "tg-1", "1", "x" * (TELEGRAM_MAX_LENGTH + 500))
    sent = gw.requested[0][4]["text"]
    assert len(sent) <= TELEGRAM_MAX_LENGTH
    assert sent.endswith("…[testo troncato]")


def test_telegram_ok_false_raises():
    gw = FakeGateway({"ok": False, "description": "chat not found"})
    with pytest.raises(TelegramError, match="chat not found"):
        send_message(gw, "tg-1", "1", "ciao")


def test_telegram_gateway_failure_raises():
    gw = FakeGateway(fail_with=GatewayError("403"))
    with pytest.raises(TelegramError):
        send_message(gw, "tg-1", "1", "ciao")
