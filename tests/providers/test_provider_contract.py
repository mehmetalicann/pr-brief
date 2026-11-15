"""One contract, run against every HTTP adapter (no network: httpx.MockTransport)."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from pr_brief.errors import ConfigError, ProviderError

REPLY = '{"summary": "ok"}'
SCHEMA: dict[str, Any] = {"title": "BriefOutput", "type": "object"}

TIMEOUT = 7.5


def call(provider: object) -> object:
    return provider.complete("SYSTEM TEXT", "USER TEXT", json_schema=SCHEMA, timeout=TIMEOUT)  # type: ignore[attr-defined]


def test_success_returns_text_usage_and_model(spec: Any, rec: Any, make: Any, api_key: str) -> None:
    rec.then_json(spec.ok_body(REPLY))
    result = call(make(spec, rec))
    assert result.text == REPLY  # type: ignore[attr-defined]
    assert (result.input_tokens, result.output_tokens) == (11, 7)  # type: ignore[attr-defined]
    assert result.model.startswith("m-")  # type: ignore[attr-defined]
    assert len(rec.requests) == 1
    assert rec.requests[0].method == "POST"


def test_request_goes_to_the_expected_host_with_timeout(
    spec: Any, rec: Any, make: Any, api_key: str
) -> None:
    rec.then_json(spec.ok_body(REPLY))
    call(make(spec, rec))
    request = rec.requests[0]
    assert request.url.host == spec.host
    assert request.extensions["timeout"]["read"] == TIMEOUT


def test_prompt_text_and_model_are_sent_and_the_key_stays_out_of_url_and_body(
    spec: Any, rec: Any, make: Any, api_key: str
) -> None:
    rec.then_json(spec.ok_body(REPLY))
    call(make(spec, rec))
    request = rec.requests[0]
    sent = request.content.decode()
    assert "SYSTEM TEXT" in sent
    assert "USER TEXT" in sent
    assert "test-model" in sent or "test-model" in str(request.url)
    assert api_key not in str(request.url)
    assert api_key not in sent
    assert "321" in sent  # max output tokens
    if spec.needs_key:
        assert any(api_key in v for v in request.headers.values())


def test_429_is_retried_with_backoff_then_succeeds(
    spec: Any, rec: Any, make: Any, api_key: str
) -> None:
    rec.then_json({}, 429).then_json({}, 429).then_json(spec.ok_body(REPLY))
    result = call(make(spec, rec))
    assert result.text == REPLY  # type: ignore[attr-defined]
    assert len(rec.requests) == 3  # one call plus at most two retries
    assert rec.sleeps == [1.0, 2.0]


def test_retry_after_header_is_honoured_but_capped(
    spec: Any, rec: Any, make: Any, api_key: str
) -> None:
    rec.then_json({}, 429, **{"Retry-After": "3"}).then_json({}, 503, **{"Retry-After": "999"})
    rec.then_json(spec.ok_body(REPLY))
    call(make(spec, rec))
    assert rec.sleeps == [3.0, 10.0]


def test_persistent_server_error_gives_up_after_two_retries(
    spec: Any, rec: Any, make: Any, api_key: str
) -> None:
    rec.then_json({"error": f"boom {api_key}"}, 503)
    with pytest.raises(ProviderError, match="HTTP 503") as exc:
        call(make(spec, rec))
    assert len(rec.requests) == 3
    assert api_key not in exc.value.user_message()
    assert exc.value.hint


@pytest.mark.parametrize(("status", "word"), [(401, "authentication"), (403, "authentication")])
def test_auth_errors_are_not_retried(
    spec: Any, rec: Any, make: Any, api_key: str, status: int, word: str
) -> None:
    rec.then_json({"error": f"bad key {api_key}"}, status)
    with pytest.raises(ProviderError, match=word) as exc:
        call(make(spec, rec))
    assert len(rec.requests) == 1
    assert rec.sleeps == []
    assert api_key not in exc.value.user_message()


def test_client_errors_name_the_status_and_are_not_retried(
    spec: Any, rec: Any, make: Any, api_key: str
) -> None:
    rec.then_json({}, 400)
    with pytest.raises(ProviderError, match="HTTP 400"):
        call(make(spec, rec))
    assert len(rec.requests) == 1


def test_timeouts_are_retried_then_reported(spec: Any, rec: Any, make: Any, api_key: str) -> None:
    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    rec.then(boom)
    with pytest.raises(ProviderError, match="timed out"):
        call(make(spec, rec))
    assert len(rec.requests) == 3


def test_connection_errors_are_retried_then_reported(
    spec: Any, rec: Any, make: Any, api_key: str
) -> None:
    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"cannot reach {api_key}", request=request)

    rec.then(boom)
    with pytest.raises(ProviderError, match="connect") as exc:
        call(make(spec, rec))
    assert len(rec.requests) == 3
    assert api_key not in exc.value.user_message()


def test_response_that_is_not_json_is_an_error(
    spec: Any, rec: Any, make: Any, api_key: str
) -> None:
    rec.then(httpx.Response(200, content=b"<html>oops</html>"))
    with pytest.raises(ProviderError, match="valid JSON"):
        call(make(spec, rec))
    assert len(rec.requests) == 1


@pytest.mark.parametrize("body", [{}, {"unexpected": True}, [], "text"])
def test_unexpected_response_shape_is_an_error(
    spec: Any, rec: Any, make: Any, api_key: str, body: object
) -> None:
    rec.then(httpx.Response(200, json=body))
    with pytest.raises(ProviderError, match="unexpected"):
        call(make(spec, rec))


def test_empty_model_text_is_an_error(spec: Any, rec: Any, make: Any, api_key: str) -> None:
    rec.then_json(spec.ok_body("   "))
    with pytest.raises(ProviderError, match="empty"):
        call(make(spec, rec))


def test_oversized_response_is_rejected_while_streaming(
    spec: Any, rec: Any, make: Any, api_key: str
) -> None:
    rec.then(httpx.Response(200, content=b"x" * 2_000_000))
    with pytest.raises(ProviderError, match="too large"):
        call(make(spec, rec))


def test_oversized_content_length_is_rejected_up_front(
    spec: Any, rec: Any, make: Any, api_key: str
) -> None:
    rec.then(httpx.Response(200, content=b"{}", headers={"Content-Length": "99999999"}))
    with pytest.raises(ProviderError, match="too large"):
        call(make(spec, rec))


def test_redirects_are_never_followed(spec: Any, rec: Any, make: Any, api_key: str) -> None:
    rec.then(httpx.Response(302, headers={"Location": "https://evil.example/steal"}))
    with pytest.raises(ProviderError, match="redirect"):
        call(make(spec, rec))
    assert len(rec.requests) == 1
    assert all(r.url.host != "evil.example" for r in rec.requests)


def test_missing_model_is_a_config_error(spec: Any, rec: Any, make: Any, api_key: str) -> None:
    with pytest.raises(ConfigError, match="model"):
        make(spec, rec, model="")


def test_missing_key_is_a_config_error_where_one_is_required(
    spec: Any, rec: Any, make: Any, api_key: str
) -> None:
    if spec.needs_key:
        with pytest.raises(ConfigError, match="api-key"):
            make(spec, rec, api_key=None)
    else:
        make(spec, rec, api_key=None)  # local models need no key


@pytest.mark.parametrize(
    "url",
    [
        "http://evil.example",  # plain http to a remote host
        "https://user:pass@evil.example",  # credentials in the URL
        "https://evil.example/v1?key=1",  # query string
        "ftp://evil.example",
        "not a url",
        "https://",
    ],
)
def test_unsafe_base_urls_are_rejected(
    spec: Any, rec: Any, make: Any, api_key: str, url: str
) -> None:
    with pytest.raises(ConfigError):
        make(spec, rec, base_url=url)


def test_custom_base_url_support_matches_the_provider(
    spec: Any, rec: Any, make: Any, api_key: str
) -> None:
    if spec.allows_custom_base_url:
        provider = make(spec, rec, base_url="https://llm.example.org/v1/")
        rec.then_json(spec.ok_body(REPLY))
        call(provider)
        assert rec.requests[0].url.host == "llm.example.org"
    else:
        with pytest.raises(ConfigError, match="base-url"):
            make(spec, rec, base_url="https://llm.example.org")


@pytest.mark.parametrize("url", ["http://localhost:8080", "http://127.0.0.1:1234/v1"])
def test_plain_http_is_allowed_for_local_servers(
    spec: Any, rec: Any, make: Any, api_key: str, url: str
) -> None:
    if not spec.allows_custom_base_url:
        pytest.skip("no custom base URL for this provider")
    rec.then_json(spec.ok_body(REPLY))
    call(make(spec, rec, base_url=url))
    assert rec.requests[0].url.host in {"localhost", "127.0.0.1"}


def test_user_agent_is_generic(spec: Any, rec: Any, make: Any, api_key: str) -> None:
    rec.then_json(spec.ok_body(REPLY))
    call(make(spec, rec))
    assert rec.requests[0].headers["user-agent"].startswith("pr-brief/")


def test_non_numeric_retry_after_falls_back_to_exponential_backoff(
    spec: Any, rec: Any, make: Any, api_key: str
) -> None:
    rec.then_json({}, 503, **{"Retry-After": "soon"}).then_json(spec.ok_body(REPLY))
    call(make(spec, rec))
    assert rec.sleeps == [1.0]


def test_low_level_http_errors_are_not_retried(
    spec: Any, rec: Any, make: Any, api_key: str
) -> None:
    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.DecodingError("bad gzip", request=request)

    rec.then(boom)
    with pytest.raises(ProviderError, match="failed"):
        call(make(spec, rec))
    assert len(rec.requests) == 1


def test_invalid_port_in_base_url_is_rejected(spec: Any, rec: Any, make: Any, api_key: str) -> None:
    if spec.allows_custom_base_url:
        with pytest.raises(ConfigError):
            make(spec, rec, base_url="https://example.org:notaport/v1")


def test_provider_exposes_the_key_only_through_a_property_and_not_in_repr(
    spec: Any, rec: Any, make: Any, api_key: str
) -> None:
    provider = make(spec, rec)
    assert api_key not in repr(provider)
    assert provider.api_key == (api_key if spec.needs_key else None)
