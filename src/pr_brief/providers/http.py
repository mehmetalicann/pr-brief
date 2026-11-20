"""Shared HTTP plumbing for provider adapters (spec L6: network egress).

Every adapter gets the same guarantees: a validated base URL, a strict timeout, at most two
retries with backoff, a hard cap on the response size, no redirects, and error messages that
never contain request headers, request bodies, response bodies or exception texts (any of which
could echo an API key).
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import Any, ClassVar
from urllib.parse import urlsplit

import httpx

from pr_brief import __version__
from pr_brief.core.chunker import estimate_tokens
from pr_brief.errors import ConfigError, ProviderError
from pr_brief.logging import get_logger
from pr_brief.providers.base import ProviderResult

MAX_RETRIES = 2
MAX_RESPONSE_BYTES = 1_000_000
MAX_RETRY_AFTER_SECONDS = 10.0
MAX_MODEL_LENGTH = 100
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})

ParsedResponse = tuple[str, int | None, int | None, str | None]


def validate_base_url(url: str) -> str:
    """Accept https URLs (and http only for localhost); no credentials, query or fragment."""
    candidate = url.strip()
    try:
        parts = urlsplit(candidate)
        host = (parts.hostname or "").lower()
        _ = parts.port  # raises ValueError for an invalid port
    except ValueError:
        host, parts = "", urlsplit("")
    if (
        parts.scheme not in ("http", "https")
        or not host
        or parts.username is not None
        or parts.password is not None
        or parts.query
        or parts.fragment
    ):
        raise ConfigError(
            "base-url is not a valid http(s) URL without credentials or query string.",
            hint="use a value like https://api.example.com/v1.",
        )
    if parts.scheme == "http" and host not in LOCAL_HOSTS:
        raise ConfigError(
            "base-url must use https unless it points to localhost.",
            hint="switch to an https:// URL, or run the model on localhost.",
        )
    return candidate.rstrip("/")


def as_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


class HttpProvider:
    """Base class: subclasses only describe the vendor's request and response shapes."""

    name: ClassVar[str]
    default_base_url: ClassVar[str]
    allows_base_url: ClassVar[bool] = True

    def __init__(
        self,
        *,
        model: str,
        api_key: str | None,
        base_url: str | None = None,
        max_output_tokens: int = 900,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        max_response_bytes: int = MAX_RESPONSE_BYTES,
    ) -> None:
        model = (model or "").strip()
        if not model or len(model) > MAX_MODEL_LENGTH:
            raise ConfigError(
                f"A model name is required for provider {self.name}.",
                hint="set the model input (for example in .pr-brief.yml).",
            )
        self.check_model(model)
        if base_url and not self.allows_base_url:
            raise ConfigError(
                f"base-url is not supported for provider {self.name}.",
                hint="remove the base-url input; the vendor endpoint is fixed.",
            )
        self.model = model
        self.base_url = validate_base_url(base_url or self.default_base_url)
        self.max_output_tokens = max_output_tokens
        self._api_key = (api_key or "").strip() or None
        if self._api_key is None and self.key_required():
            raise ConfigError(
                f"api-key is required for provider {self.name}.",
                hint="pass it through the api-key input from a repository secret.",
            )
        self._transport = transport
        self._sleep = sleep
        self._max_response_bytes = max_response_bytes

    def __repr__(self) -> str:
        return f"{type(self).__name__}(model={self.model!r}, base_url={self.base_url!r})"

    # -- hooks implemented by adapters ------------------------------------------------------

    def key_required(self) -> bool:
        return True

    def check_model(self, model: str) -> None:
        """Adapters may reject model names that would change the request URL."""

    def build_request(
        self, system: str, user: str, json_schema: dict[str, Any]
    ) -> tuple[str, dict[str, str], dict[str, Any]]:
        raise NotImplementedError

    def parse_response(self, data: Any) -> ParsedResponse:
        raise NotImplementedError

    # -- shared behaviour -------------------------------------------------------------------

    @property
    def api_key(self) -> str | None:
        return self._api_key

    def complete(
        self,
        system: str,
        user: str,
        *,
        json_schema: dict[str, Any],
        timeout: float,
    ) -> ProviderResult:
        path, headers, body = self.build_request(system, user, json_schema)
        headers = {"user-agent": f"pr-brief/{__version__}", "accept": "application/json", **headers}
        data = self._post(self.base_url + path, headers, body, timeout)
        try:
            text, in_tokens, out_tokens, model = self.parse_response(data)
        except ProviderError:
            raise
        except (KeyError, IndexError, TypeError, AttributeError, ValueError):
            raise ProviderError(
                f"{self.name}: the response has an unexpected shape.",
                hint="check the model name and base-url; the endpoint may not be compatible.",
            ) from None
        if not text.strip():
            raise ProviderError(
                f"{self.name}: the model returned an empty answer.",
                hint="try again or use a different model.",
            )
        return ProviderResult(
            text=text,
            input_tokens=in_tokens
            if in_tokens is not None
            else estimate_tokens(system) + estimate_tokens(user),
            output_tokens=out_tokens if out_tokens is not None else estimate_tokens(text),
            model=model or self.model,
        )

    def _post(self, url: str, headers: dict[str, str], body: dict[str, Any], timeout: float) -> Any:
        host = urlsplit(url).hostname or "the provider"
        timeout_config = httpx.Timeout(timeout, connect=min(timeout, 10.0))
        with httpx.Client(
            transport=self._transport,
            timeout=timeout_config,
            follow_redirects=False,
            trust_env=False,
        ) as client:
            for attempt in range(MAX_RETRIES + 1):
                last = attempt == MAX_RETRIES
                delay = 2.0**attempt
                try:
                    with client.stream("POST", url, headers=headers, json=body) as response:
                        status = response.status_code
                        if 300 <= status < 400:
                            raise ProviderError(
                                f"{self.name}: the server redirected the request (HTTP {status}).",
                                hint="redirects are never followed; fix the base-url.",
                            )
                        if status in RETRYABLE_STATUS and not last:
                            delay = self._retry_delay(response, attempt)
                            get_logger().warning(
                                "%s: HTTP %d, retry %d of %d in %.0fs",
                                self.name,
                                status,
                                attempt + 1,
                                MAX_RETRIES,
                                delay,
                            )
                        elif status >= 400:
                            raise self._http_error(status)
                        else:
                            return self._decode(self._read_limited(response))
                except httpx.TimeoutException:
                    if last:
                        raise ProviderError(
                            f"{self.name}: the request timed out after {timeout:g}s.",
                            hint="increase timeout-seconds or use a faster model.",
                        ) from None
                except httpx.TransportError:
                    if last:
                        raise ProviderError(
                            f"{self.name}: could not connect to {host}.",
                            hint="check the base-url and the runner's network access.",
                        ) from None
                except httpx.HTTPError:
                    raise ProviderError(f"{self.name}: the HTTP request failed.") from None
                self._sleep(delay)
        raise ProviderError(f"{self.name}: no response.")  # pragma: no cover - loop always returns

    @staticmethod
    def _retry_delay(response: httpx.Response, attempt: int) -> float:
        header = response.headers.get("retry-after", "")
        try:
            wanted = float(header)
        except ValueError:
            return 2.0**attempt
        return max(0.0, min(wanted, MAX_RETRY_AFTER_SECONDS))

    def _read_limited(self, response: httpx.Response) -> bytes:
        too_large = ProviderError(
            f"{self.name}: the response is too large.",
            hint="use a model that returns shorter answers or lower max-output-tokens.",
        )
        declared = response.headers.get("content-length", "")
        if declared.isdigit() and int(declared) > self._max_response_bytes:
            raise too_large
        chunks: list[bytes] = []
        total = 0
        for chunk in response.iter_bytes():
            total += len(chunk)
            if total > self._max_response_bytes:
                raise too_large
            chunks.append(chunk)
        return b"".join(chunks)

    def _decode(self, raw: bytes) -> Any:
        try:
            return json.loads(raw)
        except ValueError:  # includes UnicodeDecodeError
            raise ProviderError(
                f"{self.name}: the response is not valid JSON.",
                hint="check that base-url points to the vendor's API endpoint.",
            ) from None

    def _http_error(self, status: int) -> ProviderError:
        if status in (401, 403):
            return ProviderError(
                f"{self.name}: authentication failed (HTTP {status}).",
                hint="check that the api-key secret is set, valid and allowed to use this model.",
            )
        if status == 404:
            return ProviderError(
                f"{self.name}: model or endpoint not found (HTTP 404).",
                hint="check the model and base-url inputs.",
            )
        if status == 429:
            return ProviderError(
                f"{self.name}: rate limit or quota exceeded (HTTP 429).",
                hint="retry later or check your provider quota and billing.",
            )
        if status >= 500:
            return ProviderError(
                f"{self.name} is unavailable (HTTP {status}).",
                hint="retry later and check the provider's status page.",
            )
        return ProviderError(
            f"{self.name}: the request was rejected (HTTP {status}).",
            hint="check the model name, max-output-tokens and that the api-key is valid"
            " (some providers answer a wrong key with HTTP 400).",
        )
