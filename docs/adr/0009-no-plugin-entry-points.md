# 9. No plugin entry-points for custom providers

## Status
Accepted (2026-11-22)

## Context
A Phase 7 idea was to let users add providers through Python entry-points, so that an installed
package can register an adapter. In a GitHub Action this means importing and running code from a
package chosen by whoever writes the workflow (or, worse, by anything that can change the
dependency list), inside a job that holds the LLM key and a write token.

## Decision
Not built. Providers live in this repository and are reviewed like any other code. Anyone who
needs another service uses `provider: openai-compatible` with `base-url`, which most hosted and
self-hosted APIs speak, or sends a pull request with an adapter (`docs/providers.md`).

## Consequences
- The supply chain stays at three runtime dependencies with hash-locked installs (ADR 4) and no code
  that is chosen at run time.
- A service with a very different API needs a contribution instead of a plug-in.
- The decision can be revisited only together with a sandboxing story for third-party code.
