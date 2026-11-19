"""GitHub REST client: request shapes, token handling, limits (no network)."""

from __future__ import annotations

import httpx
import pytest

from _support.github_fake import BASE_SHA, GH_TOKEN, FakeGitHub
from pr_brief.errors import ConfigError, GitHubError
from pr_brief.github.client import GitHubClient


def make(github: FakeGitHub, **kwargs: object) -> GitHubClient:
    return GitHubClient(
        token=GH_TOKEN,
        transport=github.transport(),
        sleep=lambda _s: None,
        **kwargs,  # type: ignore[arg-type]
    )


def test_get_pull_parses_metadata(github: FakeGitHub) -> None:
    pull = make(github).get_pull("octo/demo", 7)
    assert (pull.title, pull.body, pull.draft) == ("Add feature", "Longer description", False)
    assert pull.labels == ("enhancement",)
    assert (pull.base_ref, pull.base_sha, pull.head_ref) == ("main", BASE_SHA, "feature")
    assert pull.is_fork is False


def test_pull_from_another_repository_is_a_fork(github: FakeGitHub) -> None:
    github.pull["head"]["repo"] = {"full_name": "someone/demo"}
    assert make(github).get_pull("octo/demo", 7).is_fork is True


def test_pull_with_deleted_head_repository_is_a_fork(github: FakeGitHub) -> None:
    github.pull["head"]["repo"] = None
    assert make(github).get_pull("octo/demo", 7).is_fork is True


def test_get_diff_uses_the_diff_media_type(github: FakeGitHub) -> None:
    assert "diff --git" in make(github).get_diff("octo/demo", 7)
    assert "vnd.github.diff" in github.requests[-1].headers["accept"]


def test_token_only_travels_in_the_authorization_header(github: FakeGitHub) -> None:
    client = make(github)
    client.get_pull("octo/demo", 7)
    for request in github.requests:
        assert request.headers["authorization"] == f"Bearer {GH_TOKEN}"
        assert GH_TOKEN not in str(request.url)
        assert GH_TOKEN not in request.content.decode()


def test_get_file_reads_the_requested_ref_and_returns_none_when_missing(
    github: FakeGitHub,
) -> None:
    github.files[(BASE_SHA, ".pr-brief.yml")] = "language: tr\n"
    client = make(github)
    assert client.get_file("octo/demo", ".pr-brief.yml", BASE_SHA) == "language: tr\n"
    assert client.get_file("octo/demo", "nope.yml", BASE_SHA) is None
    assert github.requests[0].url.params["ref"] == BASE_SHA


def test_get_file_quotes_the_path(github: FakeGitHub) -> None:
    make(github).get_file("octo/demo", "dir with space/c#.yml", BASE_SHA)
    assert github.requests[-1].url.raw_path.startswith(
        b"/repos/octo/demo/contents/dir%20with%20space/c%23.yml"
    )


@pytest.mark.parametrize("repo", ["octo", "octo/demo/extra", "../etc/passwd", "a b/c", ""])
def test_rejects_malformed_repository_names(github: FakeGitHub, repo: str) -> None:
    with pytest.raises(ConfigError):
        make(github).get_pull(repo, 7)


@pytest.mark.parametrize("url", ["http://api.example.com", "ftp://x", "https://u:p@host", ""])
def test_rejects_unsafe_api_urls(github: FakeGitHub, url: str) -> None:
    with pytest.raises(ConfigError):
        make(github, api_url=url)


def test_requires_a_token(github: FakeGitHub) -> None:
    with pytest.raises(ConfigError):
        GitHubClient(token="  ", transport=github.transport())


@pytest.mark.parametrize(
    ("status", "needle"),
    [(401, "authentication"), (403, "permission"), (404, "not found"), (422, "rejected")],
)
def test_http_errors_become_hinted_errors_without_bodies(
    github: FakeGitHub, status: int, needle: str
) -> None:
    def handler(_r: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"message": GH_TOKEN})

    client = GitHubClient(token=GH_TOKEN, transport=httpx.MockTransport(handler))
    with pytest.raises(GitHubError) as info:
        client.get_pull("octo/demo", 7)
    assert needle in info.value.user_message().lower()
    assert GH_TOKEN not in info.value.user_message()


def test_retries_server_errors_twice_then_gives_up() -> None:
    calls: list[int] = []

    def handler(_r: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(503)

    client = GitHubClient(
        token=GH_TOKEN, transport=httpx.MockTransport(handler), sleep=lambda _s: None
    )
    with pytest.raises(GitHubError):
        client.get_pull("octo/demo", 7)
    assert len(calls) == 3


def test_recovers_after_a_transient_error() -> None:
    answers = [httpx.Response(502), httpx.Response(200, json={"number": 7})]

    client = GitHubClient(
        token=GH_TOKEN,
        transport=httpx.MockTransport(lambda _r: answers.pop(0)),
        sleep=lambda _s: None,
    )
    with pytest.raises(GitHubError, match="unexpected"):  # reached the parser, so it retried
        client.get_pull("octo/demo", 7)


def test_does_not_retry_client_errors() -> None:
    calls: list[int] = []

    def handler(_r: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(403)

    client = GitHubClient(token=GH_TOKEN, transport=httpx.MockTransport(handler))
    with pytest.raises(GitHubError):
        client.get_pull("octo/demo", 7)
    assert len(calls) == 1


def test_redirects_are_errors_and_never_followed() -> None:
    seen: list[str] = []

    def handler(r: httpx.Request) -> httpx.Response:
        seen.append(r.url.host)
        return httpx.Response(301, headers={"location": "https://evil.example/steal"})

    client = GitHubClient(token=GH_TOKEN, transport=httpx.MockTransport(handler))
    with pytest.raises(GitHubError, match="redirect"):
        client.get_pull("octo/demo", 7)
    assert seen == ["api.github.com"]


def test_oversized_responses_are_rejected(github: FakeGitHub) -> None:
    github.diff = "x" * 5_000
    with pytest.raises(GitHubError, match="too large"):
        make(github, max_diff_bytes=1_000).get_diff("octo/demo", 7)


def test_non_json_pull_response_is_an_error() -> None:
    client = GitHubClient(
        token=GH_TOKEN, transport=httpx.MockTransport(lambda _r: httpx.Response(200, text="<html>"))
    )
    with pytest.raises(GitHubError, match="JSON"):
        client.get_pull("octo/demo", 7)


def test_connection_errors_do_not_leak_details() -> None:
    def handler(_r: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"boom {GH_TOKEN}")

    client = GitHubClient(
        token=GH_TOKEN, transport=httpx.MockTransport(handler), sleep=lambda _s: None
    )
    with pytest.raises(GitHubError) as info:
        client.get_pull("octo/demo", 7)
    assert GH_TOKEN not in info.value.user_message()


def test_custom_api_url_is_used_for_enterprise_servers(github: FakeGitHub) -> None:
    with pytest.raises(GitHubError):  # the fake only serves api.github.com paths: 404
        make(github, api_url="https://ghe.example.com/api/v3/").get_pull("octo/demo", 7)
    assert github.requests[-1].url.host == "ghe.example.com"
    assert github.requests[-1].url.path.startswith("/api/v3/repos/")
