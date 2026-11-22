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
        self.review_comments: list[dict[str, Any]] = []  # inline (diff) comments
        self.reviews: list[dict[str, Any]] = []  # bodies of the review POSTs
        self.review_status = 200  # set to 422 to simulate a rejected review
        self.delete_status = 204
        self._next_id = 1000

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self._handle)

    def add_comment(self, body: str, login: str = BOT) -> dict[str, Any]:
        self._next_id += 1
        comment = {"id": self._next_id, "body": body, "user": {"login": login}}
        self.comments.append(comment)
        return comment

    def add_review_comment(
        self, path: str, line: int | None, body: str, login: str = BOT
    ) -> dict[str, Any]:
        self._next_id += 1
        comment = {
            "id": self._next_id,
            "path": path,
            "line": line,
            "body": body,
            "user": {"login": login},
        }
        self.review_comments.append(comment)
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
        if path == f"{base}/pulls/{self.number}/comments" and request.method == "GET":
            page = int(request.url.params.get("page", "1"))
            size = int(request.url.params.get("per_page", "30"))
            return httpx.Response(200, json=self.review_comments[(page - 1) * size : page * size])
        if path == f"{base}/pulls/{self.number}/reviews" and request.method == "POST":
            body = json.loads(request.content)
            self.reviews.append(body)
            if self.review_status >= 400:
                return httpx.Response(self.review_status, json={"message": "Unprocessable"})
            for item in body.get("comments", []):
                self.add_review_comment(item["path"], item["line"], item["body"])
            return httpx.Response(200, json={"id": 1})
        if request.method == "DELETE" and path.startswith(f"{base}/pulls/comments/"):
            if self.delete_status >= 400:
                return httpx.Response(self.delete_status, json={"message": "nope"})
            cid = int(path.rsplit("/", 1)[1])
            self.review_comments = [c for c in self.review_comments if c["id"] != cid]
            return httpx.Response(204)
        if request.method == "PATCH" and path.startswith(f"{base}/issues/comments/"):
            if self.write_status >= 400:
                return httpx.Response(self.write_status, json={"message": "forbidden"})
            cid = int(path.rsplit("/", 1)[1])
            for comment in self.comments:
                if comment["id"] == cid:
                    comment["body"] = json.loads(request.content)["body"]
                    return httpx.Response(200, json=comment)
        return httpx.Response(404, json={"message": "Not Found"})


def comment_env(
    tmp_path: Path,
    *,
    body: str = "/pr-brief refresh",
    association: str = "OWNER",
    user_type: str = "User",
    on_pull_request: bool = True,
    action: str = "created",
    **extra: str,
) -> dict[str, str]:
    """Environment of an `issue_comment` run: a comment on issue/PR number 7."""
    issue: dict[str, object] = {"number": 7}
    if on_pull_request:
        issue["pull_request"] = {"url": "https://api.github.com/repos/octo/demo/pulls/7"}
    payload = {
        "action": action,
        "issue": issue,
        "comment": {
            "body": body,
            "author_association": association,
            "user": {"login": "someone", "type": user_type},
        },
    }
    env = action_env(tmp_path, event_name="issue_comment", **extra)
    Path(env["GITHUB_EVENT_PATH"]).write_text(json.dumps(payload), encoding="utf-8")
    return env


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
