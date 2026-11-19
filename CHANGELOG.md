# Changelog

All notable changes are documented here. Format: [Keep a Changelog](https://keepachangelog.com/),
versioning: [SemVer](https://semver.org/).

## [Unreleased]

### Added
- Project bootstrap: package skeleton, tooling, CI.
- Offline core: unified-diff parser, file filters, token-budget chunker with map-reduce planning,
  output schema with JSON extraction and one repair attempt, versioned prompts, Markdown renderer,
  settings loader (`.pr-brief.yml` + `PR_BRIEF_*` environment), mock provider and a local
  `--diff` runner (`just run-local`).
- Security layer: secret/PII redaction that runs before parsing, chunking and any provider call;
  sensitive files are never sent; hardened prompts (random delimiter, hidden-character and
  look-alike-delimiter stripping); output sanitiser (no images/HTML, repo-only links, defused
  mentions, flattened fields); secret-safe logger; `docs/security-model.md`.
- Providers: Ollama, OpenAI-compatible, Anthropic and Gemini adapters on a shared HTTP layer
  (base-URL rules, timeouts, two retries with backoff, 1 MB response cap, no redirects, safe
  errors), registry, `--base-url` for the local runner, `docs/providers.md`.
- Community and security files: `SECURITY.md`, `CODE_OF_CONDUCT.md`, `CODEOWNERS`, issue-template
  config, and `docs/going-public.md`.
- GitHub integration and packaging: REST client (token only in the `Authorization` header, no
  redirects, size caps), marker-based comment upsert (one comment per PR, edited in place),
  `action.yml` (composite, hash-locked `requirements.lock`, workspace isolated from the run),
  config read from the base commit, graceful skip for forks, drafts and other events, step
  summary, result cache for identical input, `dogfood.yml` and an `action-smoke` CI job,
  `docs/action.md`.

### Fixed
- CI: upgrade the venv's bundled pip/setuptools before `pip-audit`.
