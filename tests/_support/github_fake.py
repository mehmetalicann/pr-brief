"""Fake GitHub REST API for tests (no network). Importable as `_support.github_fake`."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

# Fake tokens are assembled at runtime so that secret scanners do not flag this file.
GH_TOKEN = "ghs_" + "A" * 36
BOT = "github-actions[bot]"
BASE_SHA = "b" * 40
HEAD_SHA = "c" * 40
DIFF_ACCEPT = "application/vnd.github.diff"


class FakeGitHub:
    """Scripted GitHub API for one repository and one pull request (number 7)."""

    def __init__(self, diff: str = "") -> None:
        self.repo = "octo/demo"
        self.number = 7
        self.diff = diff
        self.requests: list[httpx.Request] = []
        self.comments: list[dict[str, Any]] = []
        self.files: dict[tuple[str, str], str] = {}  # (ref, path) -> text
        self.pull: dict[str, Any] = {
            "number": 7,
            "title": "Add feature",
            "body": "Longer description",
            "draft": False,
            "user": {"login": "octocat", "type": "User"},
            "labels": [{"name": "enhancement"}],
            "base": {"ref": "main", "sha": BASE_SHA, "repo": {"full_name": "octo/demo"}},
            "head": {"ref": "feature", "sha": HEAD_SHA, "repo": {"full_name": "octo/demo"}},
        }
        self.write_status = 201  # set to 403 to simulate a read-only token
        self._next_id = 1000

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self._handle)

    def add_comment(self, body: str, login: str = BOT) -> dict[str, Any]:
        self._next_id += 1
        comment = {"id": self._next_id, "body": body, "user": {"login": login}}
        self.comments.append(comment)
        return comment

    def calls(self, method: str) -> list[httpx.Request]:
        return [r for r in self.requests if r.method == method]

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path, base = request.url.path, f"/repos/{self.repo}"
        if request.method == "GET" and path == f"{base}/pulls/{self.number}":
            if DIFF_ACCEPT in request.headers.get("accept", ""):
                return httpx.Response(200, text=self.diff)
            return httpx.Response(200, json=self.pull)
        if request.method == "GET" and path.startswith(f"{base}/contents/"):
            key = (request.url.params.get("ref", ""), path.removeprefix(f"{base}/contents/"))
            if key in self.files:
                return httpx.Response(200, text=self.files[key])
            return httpx.Response(404, json={"message": "Not Found"})
        if path == f"{base}/issues/{self.number}/comments":
            if request.method == "GET":
                page = int(request.url.params.get("page", "1"))
                size = int(request.url.params.get("per_page", "30"))
                return httpx.Response(200, json=self.comments[(page - 1) * size : page * size])
            if request.method == "POST":
                if self.write_status >= 400:
                    return httpx.Response(self.write_status, json={"message": "forbidden"})
                return httpx.Response(
                    201, json=self.add_comment(json.loads(request.content)["body"])
                )
        if request.method == "PATCH" and path.startswith(f"{base}/issues/comments/"):
            if self.write_status >= 400:
                return httpx.Response(self.write_status, json={"message": "forbidden"})
            cid = int(path.rsplit("/", 1)[1])
            for comment in self.comments:
                if comment["id"] == cid:
                    comment["body"] = json.loads(request.content)["body"]
                    return httpx.Response(200, json=comment)
        return httpx.Response(404, json={"message": "Not Found"})


def action_env(
    tmp_path: Path,
    *,
    event_name: str = "pull_request",
    action: str = "synchronize",
    fork: bool = False,
    draft: bool = False,
    **extra: str,
) -> dict[str, str]:
    """Environment of a GitHub Actions run for pull request 7, plus a step-summary file."""
    payload = {
        "action": action,
        "number": 7,
        "pull_request": {
            "number": 7,
            "draft": draft,
            "head": {"repo": {"full_name": "someone/demo" if fork else "octo/demo"}},
            "base": {"repo": {"full_name": "octo/demo"}},
        },
    }
    event = tmp_path / "event.json"
    event.write_text(json.dumps(payload), encoding="utf-8")
    summary = tmp_path / "summary.md"
    summary.write_text("", encoding="utf-8")
    return {
        "GITHUB_EVENT_NAME": event_name,
        "GITHUB_EVENT_PATH": str(event),
        "GITHUB_REPOSITORY": "octo/demo",
        "GITHUB_TOKEN": GH_TOKEN,
        "GITHUB_STEP_SUMMARY": str(summary),
        "PR_BRIEF_PROVIDER": "mock",
        **extra,
    }
