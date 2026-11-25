# SPDX-License-Identifier: GPL-3.0-or-later
"""Attività GitHub notturna via connettore Sprites GitHub (OAuth).

Chiamata: GET repos/{owner}/{repo}/commits?since=<ieri 07:17>&per_page=20
attraverso il gateway. Il gateway allega il token OAuth: qui non compare
mai nessuna credenziale.
"""

from __future__ import annotations

from dataclasses import dataclass

from .gateway import GatewayClient, GatewayError


class GitHubError(RuntimeError):
    """L'attività GitHub non è disponibile."""


@dataclass
class Commit:
    sha: str
    message: str  # prima riga
    author: str
    date: str  # ISO 8601

    def format(self) -> str:
        return f"{self.author}: {self.message}"


def fetch_repo_commits(
    gateway: GatewayClient,
    connection_id: str,
    repo: str,
    since: str,
    per_page: int = 20,
) -> list[Commit]:
    """Commit di un repo da `since` (ISO 8601). Solleva GitHubError."""
    if "/" not in repo:
        raise GitHubError(f"repo non valido (serve owner/repo): {repo!r}")
    try:
        data = gateway.call(
            "github",
            connection_id,
            f"repos/{repo}/commits?since={since}&per_page={per_page}",
        )
    except GatewayError as exc:
        raise GitHubError(f"{repo}: {exc}") from exc
    if isinstance(data, dict) and "message" in data:
        raise GitHubError(f"{repo}: {data.get('message')}")
    if not isinstance(data, list):
        raise GitHubError(f"{repo}: risposta inattesa dal gateway")
    commits = []
    for item in data:
        if not isinstance(item, dict):
            continue
        commit = item.get("commit", {}) if isinstance(item.get("commit"), dict) else {}
        author = commit.get("author", {}) if isinstance(commit.get("author"), dict) else {}
        message = str(commit.get("message", "")).splitlines()[0:1]
        commits.append(
            Commit(
                sha=str(item.get("sha", ""))[:7],
                message=message[0] if message else "(nessun messaggio)",
                author=str(author.get("name", "sconosciuto")),
                date=str(author.get("date", "")),
            )
        )
    return commits


def summarize_activity(
    gateway: GatewayClient,
    connection_id: str,
    repos: list[str],
    since: str,
) -> dict[str, dict]:
    """Per ogni repo: {"commits": [...]} oppure {"error": "..."}.

    Un repo che fallisce non blocca gli altri (il briefing lo segnala
    in una riga invece di morire).
    """
    summary: dict[str, dict] = {}
    for repo in repos:
        try:
            summary[repo] = {"commits": fetch_repo_commits(gateway, connection_id, repo, since)}
        except GitHubError as exc:
            summary[repo] = {"error": str(exc)}
    return summary


def format_activity(summary: dict[str, dict]) -> list[str]:
    """Una riga per repo, stile briefing."""
    lines = []
    for repo, info in summary.items():
        if "error" in info:
            lines.append(f"{repo}: non controllato ({info['error']})")
            continue
        commits = info.get("commits", [])
        if not commits:
            lines.append(f"{repo}: nessun commit da ieri")
            continue
        first = commits[0].format() if commits else ""
        extra = f" (+{len(commits) - 1} altri)" if len(commits) > 1 else ""
        lines.append(f"{repo}: {len(commits)} commit — {first}{extra}")
    return lines
