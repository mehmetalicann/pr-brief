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
- Docs and UX: Turkish output (`language: tr`), a rewritten README (quick start, settings table,
  FAQ, Turkish section), `.pr-brief.example.yml`, `docs/configuration.md`,
  `docs/troubleshooting.md`, `docs/architecture.md`, a demo-GIF guide, and tests that keep the
  docs in sync with `action.yml` and the settings model.
- An opt-in live Gemini test (`just live`) that reads the key from a git-ignored `.env`.
- `allow-fork-target` input: fork PRs are now also skipped under `pull_request_target` unless it is set.
- A guarded release workflow (`release.yml`) and release gate (`scripts/release.py`), plus
  `docs/releasing.md`; the release carries a CycloneDX SBOM (`scripts/sbom.py`) and the Marketplace
  listing text is in `docs/marketplace.md`.
- A generated demo GIF (`scripts/make_demo_gif.py`) and a provider "Verification status" table.
- An offline replay of the README quick start (`tests/integration/test_readme_quick_start.py`).

### Fixed
- CI: upgrade the venv's bundled pip/setuptools before `pip-audit`.
- The footer link of every comment now points to an existing README section (`#configuration`).
- Cross-repository references (`owner/repo#12`, `owner/repo@sha`) in the model's text are defused.
- The README workflow and the dogfood workflow cancel superseded runs per pull request, so a fast second push cannot create a second comment.
- Dependabot waits 7 days before proposing a new release (supply-chain cooldown).
