# 3. `pull_request` by default, forks skipped, config from the base commit

## Status
Accepted (2026-11-19), amended 2026-11-20

## Context
The action holds a provider key and a token that can write comments, and it reads text that a pull
request author controls. `pull_request_target` gives fork PRs secrets and a write token. A
`.pr-brief.yml` in the PR head could point `base-url` at a server the author controls.

## Decision
- The documented trigger is `pull_request`; the action never checks out or runs PR code (the diff
  and the text come from the API).
- Fork PRs are skipped with a neutral notice (exit 0) under `pull_request`, and also under
  `pull_request_target` unless the maintainer sets `allow-fork-target: true`.
- `.pr-brief.yml` is read through the API at the base commit, never from the head.
- Every failure is soft (exit 0) unless `fail-on-error` is set.

## Consequences
Fork contributors get no brief unless a maintainer re-runs the PR from a branch or opts in. A PR
that edits `.pr-brief.yml` only takes effect after it is merged. See `docs/security-model.md`.
