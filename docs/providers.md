# Providers

pr-brief talks to models over plain HTTP (`httpx`); there are no vendor SDKs. Pick one with the
`provider` input and set `model` (and `api-key` where needed).

| `provider` | Endpoint (default) | `api-key` | `base-url` | Notes |
|------------|--------------------|-----------|------------|-------|
| `mock` | none (offline) | no | no | Canned answers for tests and `just run-local`. |
| `ollama` | `http://localhost:11434` | optional | yes | Free and local; uses `/api/chat` with structured output. |
| `openai-compatible` | `https://api.openai.com/v1` | yes (not for localhost) | yes | OpenAI, Groq, OpenRouter, LM Studio, vLLM, … via `/chat/completions`. |
| `anthropic` | `https://api.anthropic.com` | yes | no | Messages API. |
| `gemini` | `https://generativelanguage.googleapis.com` | yes | no | `generateContent`; the key is sent in a header, never in the URL. |

Examples:

```yaml
# Free, on a self-hosted runner that runs Ollama
provider: ollama
model: llama3.2

# Groq through the OpenAI-compatible adapter
provider: openai-compatible
base-url: https://api.groq.com/openai/v1
model: llama-3.3-70b-versatile
api-key: ${{ secrets.LLM_API_KEY }}
```

## Guarantees shared by every adapter

- **Base URL rules:** `https` is required unless the host is `localhost`, `127.0.0.1` or `::1`.
  URLs with credentials, a query string or a fragment are rejected. `anthropic` and `gemini` have a
  fixed endpoint and refuse a `base-url`. Gemini model names are validated so they cannot change
  the URL path.
- **Timeout:** `timeout-seconds` (default 60) applies to each request; connecting is capped at 10 s.
- **Retries:** at most two, for HTTP 429/500/502/503/504 and for timeouts or connection errors,
  with 1 s then 2 s backoff. A `Retry-After` header is honoured up to 10 s. Authentication errors
  and other 4xx responses are never retried.
- **Response limit:** answers larger than 1 MB (after decompression) are rejected.
- **No redirects:** a redirect is an error; the request is never replayed to another host.
- **No proxies from the environment** (`HTTP_PROXY` and friends are ignored).
- **Safe errors:** messages name the provider and the HTTP status only, with a "How to fix" hint.
  They never include headers, request or response bodies, or exception texts.
- **Fail soft:** any provider error produces the neutral failure comment, and the job still exits 0
  unless `fail-on-error` is set.

Redaction and prompt hardening run before any adapter is called (see
[`security-model.md`](security-model.md)).

## Known limits

- Every adapter asks for JSON, but models may still answer with something else; the pipeline then
  makes one repair attempt and otherwise fails soft.
- The OpenAI-compatible adapter sends `max_tokens`. If a newer OpenAI model rejects it in favour
  of `max_completion_tokens`, the request fails with an HTTP 400 and a hint; use a compatible
  server or an older model until the adapter learns that parameter.
- The Anthropic adapter does not send `temperature` (some current models reject it).
- Costs are the provider's; pr-brief only limits tokens (`max-input-tokens`, `max-output-tokens`).

## Add a provider in 4 steps

1. Create `src/pr_brief/providers/<name>.py` with a subclass of `HttpProvider` that sets `name`,
   `default_base_url` (and `allows_base_url` / `key_required()` if they differ) and implements
   `build_request()` and `parse_response()`.
2. Register it in `providers/registry.py` (`HTTP_PROVIDERS`) and in the `ProviderName` literal in
   `config.py`.
3. Add a `Spec` entry in `tests/providers/conftest.py`; the shared contract tests then run against
   it (success, retries, timeouts, size limit, redirects, base-URL rules, key handling).
4. Add the request-shape tests to `tests/providers/test_adapters_http_mock.py` and a row to the
   table above.
