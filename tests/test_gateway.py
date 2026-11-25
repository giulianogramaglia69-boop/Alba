# SPDX-License-Identifier: GPL-3.0-or-later
"""Test client gateway Sprites (offline: trasporto finto)."""

import json

import pytest

from alba.gateway import Connection, GatewayClient, GatewayError


class FakeTransport:
    def __init__(self, routes):
        self.routes = routes  # {(method, url): (status, body_bytes)}
        self.calls = []

    def __call__(self, method, url, body, headers):
        self.calls.append((method, url, body, headers))
        key = (method, url)
        if key in self.routes:
            return self.routes[key]
        return 404, b'{"error": "not found"}'


def test_call_builds_gateway_url():
    transport = FakeTransport(
        {("GET", "https://api.sprites.dev/v1/gateway/github/conn-1/repos/o/r/commits"): (200, b"[]")}
    )
    client = GatewayClient(http_request=transport)
    client.call("github", "conn-1", "repos/o/r/commits")
    assert transport.calls[0][1] == (
        "https://api.sprites.dev/v1/gateway/github/conn-1/repos/o/r/commits"
    )
    # Mai Authorization.
    assert "Authorization" not in transport.calls[0][3]


def test_call_refuses_authorization_header():
    client = GatewayClient(http_request=FakeTransport({}))
    with pytest.raises(ValueError, match="Authorization"):
        client.call("github", "c", "x", headers={"Authorization": "Bearer abc"})


def test_call_posts_json_body():
    transport = FakeTransport(
        {("POST", "https://api.sprites.dev/v1/gateway/openrouter/c/api/v1/chat/completions"): (200, b'{"ok": true}')}
    )
    client = GatewayClient(http_request=transport)
    out = client.call("openrouter", "c", "api/v1/chat/completions", method="POST", json_body={"model": "m"})
    assert out == {"ok": True}
    assert json.loads(transport.calls[0][2]) == {"model": "m"}
    assert transport.calls[0][3]["Content-Type"] == "application/json"


def test_call_http_error_raises():
    transport = FakeTransport({("GET", "https://api.sprites.dev/v1/gateway/github/c/x"): (403, b"forbidden")})
    client = GatewayClient(http_request=transport)
    with pytest.raises(GatewayError, match="403"):
        client.call("github", "c", "x")


def test_list_connections_parses_list():
    body = json.dumps(
        [
            {"id": "a1", "provider": "github", "name": "alba-github"},
            {"id": "a2", "provider": "openrouter", "name": "alba-llm"},
        ]
    ).encode()
    transport = FakeTransport({("GET", "https://api.sprites.dev/v1/gateway/list"): (200, body)})
    conns = GatewayClient(http_request=transport).list_connections()
    assert [c.provider for c in conns] == ["github", "openrouter"]
    assert conns[0].name == "alba-github"


def test_list_connections_non_json_raises():
    transport = FakeTransport({("GET", "https://api.sprites.dev/v1/gateway/list"): (200, b"html")})
    with pytest.raises(GatewayError):
        GatewayClient(http_request=transport).list_connections()


def test_find_connection_by_provider_and_name():
    client = GatewayClient(http_request=FakeTransport({}))
    conns = [
        Connection("1", "github", "alba-github"),
        Connection("2", "openrouter", "alba-llm"),
        Connection("3", "github", "altro"),
    ]
    assert client.find_connection(conns, "github", "alba").id == "1"
    assert client.find_connection(conns, "openrouter", "llm").id == "2"
    assert client.find_connection(conns, "telegram", "alba") is None
    assert client.find_connection(conns, "github", "inesistente") is None
