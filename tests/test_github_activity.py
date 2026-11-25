# SPDX-License-Identifier: GPL-3.0-or-later
"""Test attività GitHub via gateway finto (offline)."""

import pytest

from alba.fixtures import SAMPLE_COMMITS
from alba.gateway import Connection, GatewayError
from alba.github_activity import (
    GitHubError,
    fetch_repo_commits,
    format_activity,
    summarize_activity,
)


class FakeGateway:
    def __init__(self, calls=None, fail_repos=()):
        self.calls = calls or {}  # path -> payload
        self.fail_repos = fail_repos
        self.requested = []

    def list_connections(self):
        return [Connection("gh-1", "github", "alba-github")]

    def find_connection(self, connections, provider, hint):
        return connections[0] if connections else None

    def call(self, provider, connection_id, path, method="GET", json_body=None, headers=None):
        self.requested.append(path)
        for repo in self.fail_repos:
            if f"repos/{repo}/commits" in path:
                raise GatewayError("boom")
        return self.calls.get(path, [])


def test_fetch_commits_parses_sample():
    gw = FakeGateway({"repos/o/r/commits?since=2026-11-24T07:17:00&per_page=20": SAMPLE_COMMITS})
    commits = fetch_repo_commits(gw, "gh-1", "o/r", "2026-11-24T07:17:00")
    assert len(commits) == 2
    assert commits[0].message == "feat(pkg): package manager v1"
    assert commits[0].author == "Giuliano"
    assert commits[0].sha == "abc1234"
    assert commits[0].format() == "Giuliano: feat(pkg): package manager v1"


def test_fetch_commits_uses_since_param():
    gw = FakeGateway()
    fetch_repo_commits(gw, "gh-1", "o/r", "2026-11-24T07:17:00+01:00")
    assert gw.requested[0].startswith("repos/o/r/commits?since=2026-11-24T07:17:00+01:00")


def test_fetch_invalid_repo_name():
    with pytest.raises(GitHubError, match="owner/repo"):
        fetch_repo_commits(FakeGateway(), "gh-1", "senza-slash", "2026-11-24")


def test_fetch_github_api_error_message():
    gw = FakeGateway({"repos/o/r/commits?since=x&per_page=20": {"message": "Not Found"}})
    with pytest.raises(GitHubError, match="Not Found"):
        fetch_repo_commits(gw, "gh-1", "o/r", "x")


def test_summarize_one_repo_failing_does_not_block_others():
    gw = FakeGateway(
        {"repos/o/ok/commits?since=s&per_page=20": SAMPLE_COMMITS},
        fail_repos=("o/ko",),
    )
    summary = summarize_activity(gw, "gh-1", ["o/ok", "o/ko"], "s")
    assert len(summary["o/ok"]["commits"]) == 2
    assert "error" in summary["o/ko"]


def test_format_activity_lines():
    from alba.github_activity import Commit

    summary = {
        "o/full": {"commits": [Commit("a1", "fix: x", "G", "2026-11-24")]},
        "o/empty": {"commits": []},
        "o/broken": {"error": "boom"},
    }
    lines = format_activity(summary)
    assert lines[0] == "o/full: 1 commit — G: fix: x"
    assert lines[1] == "o/empty: nessun commit da ieri"
    assert "non controllato" in lines[2]
