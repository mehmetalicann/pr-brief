# 2. Plain HTTP with `httpx`, no vendor SDKs

## Status
Accepted (2026-11-15)

## Context
The action supports Ollama, OpenAI-compatible APIs, Anthropic and Gemini. Vendor SDKs would add
large dependency trees to a job that runs on every pull request and holds an API key.

## Decision
Every provider is a small adapter over one shared `HttpProvider` (`httpx` only): it describes the
request and response shape, while the base class owns retries, timeouts, size caps, redirects
(never followed) and key handling. The key travels in a header, never in a URL or an error text.
Runtime dependencies stay at `httpx`, `pydantic`, `pyyaml`.

## Consequences
A small attack surface and one contract test suite that runs against all adapters. The cost: when a
vendor changes its API, we change the adapter ourselves. Adapters that were not called live are
documented as mock-only (README, "Verification status").
