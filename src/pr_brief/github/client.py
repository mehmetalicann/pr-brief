"""Minimal GitHub REST client (spec FR2, L1, L5, L6).

Read endpoints for the pull request, issue-comment writes and, only when `inline-comments` is on,
review comments (one COMMENT review; the bot's own marked comments may be deleted). The token
travels in the `Authorization` header only; errors never include headers, bodies or exception
texts; redirects are never followed; responses are size-capped; the PR's code is never fetched or
executed.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx

from pr_brief import __version__
from pr_brief.errors import ConfigError, GitHubError
from pr_brief.logging import get_logger
from pr_brief.providers.http import validate_base_url

DEFAULT_API_URL = "https://api.github.com"
API_VERSION = "2022-11-28"
JSON_ACCEPT = "application/vnd.github+json"
DIFF_ACCEPT = "application/vnd.github.diff"
RAW_ACCEPT = "application/vnd.github.raw+json"
MAX_RETRIES = 2
MAX_JSON_BYTES = 2_000_000
MAX_FILE_BYTES = 128 * 1024
MAX_DIFF_BYTES = 10_000_000
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


def _is_bot(user: object) -> bool:
    """True for GitHub App accounts such as `dependabot[bot]` (the author is set by GitHub)."""
    if not isinstance(user, dict):
        return False
    login = user.get("login")
    return user.get("type") == "Bot" or (isinstance(login, str) and login.endswith("[bot]"))


_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}$")


@dataclass(frozen=True)
class PullRequest:
    number: int
    title: str
    body: str | None
    draft: bool
    labels: tuple[str, ...]
    base_ref: str
    base_sha: str
    head_ref: str
    is_fork: bool
    author_is_bot: bool = False
    head_sha: str = ""


def check_repo(repo: str) -> str:
    if not _REPO_RE.match(repo or "") or {".", ".."} & set(repo.split("/")):
        raise ConfigError(
            "The repository name is not in the form owner/name.",
            hint="this action must run inside a GitHub Actions workflow.",
        )
    return repo


class GitHubClient:
    def __init__(
        self,
        *,
        token: str,
        api_url: str = DEFAULT_API_URL,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        timeout: float = 30.0,
        max_diff_bytes: int = MAX_DIFF_BYTES,
    ) -> None:
        self._token = (token or "").strip()
        if not self._token:
            raise ConfigError(
                "A GitHub token is required.",
                hint="pass github-token (default: the workflow's GITHUB_TOKEN).",
            )
        self._api_url = validate_base_url(api_url)
        self._transport = transport
        self._sleep = sleep
        self._timeout = timeout
        self._max_diff_bytes = max_diff_bytes

    def __repr__(self) -> str:
        return f"GitHubClient(api_url={self._api_url!r})"

    # -- reads ---------------------------------------------------------------------------------

    def get_pull(self, repo: str, number: int) -> PullRequest:
        data = self._json(self._request("GET", f"/repos/{check_repo(repo)}/pulls/{int(number)}"))
        try:
            base, head = data["base"], data["head"]
            head_repo = (head.get("repo") or {}).get("full_name")
            base_repo = (base.get("repo") or {}).get("full_name") or repo
            return PullRequest(
                number=int(data["number"]),
                title=str(data["title"]),
                body=data["body"] if isinstance(data.get("body"), str) else None,
                draft=bool(data.get("draft", False)),
                labels=tuple(str(x["name"]) for x in data.get("labels") or []),
                base_ref=str(base["ref"]),
                base_sha=str(base["sha"]),
                head_ref=str(head["ref"]),
                is_fork=not isinstance(head_repo, str) or head_repo.lower() != base_repo.lower(),
                author_is_bot=_is_bot(data.get("user")),
                head_sha=str(head.get("sha") or ""),
            )
        except (KeyError, TypeError, AttributeError, ValueError):
            raise _unexpected() from None

    def get_diff(self, repo: str, number: int) -> str:
        raw = self._request(
            "GET",
            f"/repos/{check_repo(repo)}/pulls/{int(number)}",
            accept=DIFF_ACCEPT,
            max_bytes=self._max_diff_bytes,
        )
        return raw.decode("utf-8", errors="replace")

    def get_file(self, repo: str, path: str, ref: str) -> str | None:
        """Text of `path` at `ref` (a commit SHA), or None when it does not exist."""
        try:
            raw = self._request(
                "GET",
                f"/repos/{check_repo(repo)}/contents/{quote(path, safe='/')}",
                params={"ref": ref},
                accept=RAW_ACCEPT,
                max_bytes=MAX_FILE_BYTES,
            )
        except _NotFound:
            return None
        return raw.decode("utf-8", errors="replace")

    def list_issue_comments(self, repo: str, number: int, *, page: int) -> list[Any]:
        data = self._json(
            self._request(
                "GET",
                f"/repos/{check_repo(repo)}/issues/{int(number)}/comments",
                params={"per_page": 100, "page": page},
            )
        )
        if not isinstance(data, list):
            raise _unexpected()
        return data

    def list_review_comments(self, repo: str, number: int, *, page: int) -> list[Any]:
        """Comments on the diff (not on the conversation), 100 per page."""
        data = self._json(
            self._request(
                "GET",
                f"/repos/{check_repo(repo)}/pulls/{int(number)}/comments",
                params={"per_page": 100, "page": page},
            )
        )
        if not isinstance(data, list):
            raise _unexpected()
        return data

    # -- writes --------------------------------------------------------------------------------

    def create_issue_comment(self, repo: str, number: int, body: str) -> int:
        data = self._json(
            self._request(
                "POST",
                f"/repos/{check_repo(repo)}/issues/{int(number)}/comments",
                payload={"body": body},
            )
        )
        return _comment_id(data)

    def update_issue_comment(self, repo: str, comment_id: int, body: str) -> int:
        data = self._json(
            self._request(
                "PATCH",
                f"/repos/{check_repo(repo)}/issues/comments/{int(comment_id)}",
                payload={"body": body},
            )
        )
        return _comment_id(data)

    def create_review(
        self, repo: str, number: int, *, commit_id: str, comments: list[dict[str, Any]]
    ) -> None:
        """One review of type COMMENT (it never approves or requests changes) with diff comments."""
        self._request(
            "POST",
            f"/repos/{check_repo(repo)}/pulls/{int(number)}/reviews",
            payload={"commit_id": commit_id, "event": "COMMENT", "comments": comments},
        )

    def delete_review_comment(self, repo: str, comment_id: int) -> None:
        self._request("DELETE", f"/repos/{check_repo(repo)}/pulls/comments/{int(comment_id)}")

    # -- plumbing ------------------------------------------------------------------------------

    @staticmethod
    def _json(raw: bytes) -> Any:
        try:
            return json.loads(raw)
        except ValueError:
            raise GitHubError(
                "GitHub returned a response that is not valid JSON.",
                hint="check the GITHUB_API_URL of your runner and retry.",
            ) from None

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
        accept: str = JSON_ACCEPT,
        max_bytes: int = MAX_JSON_BYTES,
    ) -> bytes:
        headers = {
            "authorization": f"Bearer {self._token}",
            "accept": accept,
            "x-github-api-version": API_VERSION,
            "user-agent": f"pr-brief/{__version__}",
        }
        timeout = httpx.Timeout(self._timeout, connect=min(self._timeout, 10.0))
        with httpx.Client(
            transport=self._transport, timeout=timeout, follow_redirects=False, trust_env=False
        ) as client:
            for attempt in range(MAX_RETRIES + 1):
                last = attempt == MAX_RETRIES
                try:
                    with client.stream(
                        method, self._api_url + path, params=params, json=payload, headers=headers
                    ) as response:
                        status = response.status_code
                        if status in RETRYABLE_STATUS and not last:
                            get_logger().warning(
                                "github: HTTP %d, retry %d of %d", status, attempt + 1, MAX_RETRIES
                            )
                        else:
                            return self._finish(response, status, max_bytes)
                except (httpx.TimeoutException, httpx.TransportError):
                    if last:
                        raise GitHubError(
                            "Could not reach the GitHub API.",
                            hint="check the runner's network access and GitHub's status page.",
                        ) from None
                except httpx.HTTPError:
                    raise GitHubError("The GitHub API request failed.") from None
                self._sleep(2.0**attempt)
        raise GitHubError("No response from the GitHub API.")  # pragma: no cover

    @staticmethod
    def _finish(response: httpx.Response, status: int, max_bytes: int) -> bytes:
        if 300 <= status < 400:
            raise GitHubError(
                f"The GitHub API redirected the request (HTTP {status}).",
                hint="redirects are never followed; check the repository name and API URL.",
            )
        if status >= 400:
            raise _http_error(status)
        too_large = GitHubError(
            "A GitHub API response is too large to process.",
            hint="split the pull request into smaller ones.",
        )
        declared = response.headers.get("content-length", "")
        if declared.isdigit() and int(declared) > max_bytes:
            raise too_large
        chunks: list[bytes] = []
        total = 0
        for chunk in response.iter_bytes():
            total += len(chunk)
            if total > max_bytes:
                raise too_large
            chunks.append(chunk)
        return b"".join(chunks)


class _NotFound(GitHubError):
    """HTTP 404 (kept distinct so that `get_file` can treat it as 'missing')."""


def _http_error(status: int) -> GitHubError:
    if status == 401:
        return GitHubError(
            "GitHub rejected the token (authentication failed, HTTP 401).",
            hint="check the github-token input.",
        )
    if status == 403:
        return GitHubError(
            "GitHub refused the request: the token lacks permission (HTTP 403).",
            hint="grant `pull-requests: write` and `contents: read` in the workflow permissions. "
            "Pull requests from forks only get a read-only token.",
        )
    if status == 404:
        return _NotFound(
            "GitHub could not find the requested item (not found, HTTP 404).",
            hint="check the repository, the pull request number and the token's access.",
        )
    if status == 429 or status >= 500:
        return GitHubError(
            f"The GitHub API is unavailable or rate limiting (HTTP {status}).",
            hint="re-run the workflow later.",
        )
    return GitHubError(
        f"GitHub rejected the request (HTTP {status}).",
        hint="the pull request may be too large or closed; see docs/troubleshooting.md.",
    )


def _unexpected() -> GitHubError:
    return GitHubError(
        "GitHub returned data in an unexpected shape.",
        hint="check the GITHUB_API_URL of your runner.",
    )


def _comment_id(data: Any) -> int:
    try:
        return int(data["id"])
    except (KeyError, TypeError, ValueError):
        raise _unexpected() from None
