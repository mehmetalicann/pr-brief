# Changelog

All notable changes are documented here. Format: [Keep a Changelog](https://keepachangelog.com/),
versioning: [SemVer](https://semver.org/).

## [Unreleased]

### Fixed
- With `inline-comments` on, the prompt now states that every risk needs `note` as well as `path` and `quote`; a 7B model (qwen2.5) had dropped `note` and failed the schema check. Found in a trial with a real model.

## [1.3.0] - 2026-11-22

### Added
- `inline-comments` setting and input (opt-in, default `false`): up to 5 review comments on the diff lines that medium and high risks are about. The model quotes a line, the code finds its number; comments are synchronised on every push and only the bot's own marked comments are ever deleted. Briefs split into chunks get none. Small models may leave the quote empty; then no comment is posted. See `docs/inline-comments.md` and ADR 8.
- ADR 9: plugin entry-points for custom providers are deliberately not built.

## [1.2.0] - 2026-11-20

### Security
- Denial of service through hostile input, found by probing the code with adversarial text: (1) redaction was quadratic on some inputs (a 32 KB line such as `a.a.a.a...` kept a job busy for over a minute, longer inputs for hours); the patterns are now bounded and linear; (2) the output sanitiser was quadratic on long runs of brackets coming from the model (`[a](` repeated: minutes), so text is clipped before the link patterns run; (3) a crafted `ignore` glob could make path matching exponential; matching no longer backtracks; (4) absurdly nested JSON or YAML ended in an unhandled `RecursionError`, now a normal schema or config error. Each has a regression test.

### Fixed
- An HTTP 400 from a provider now also hints at the `api-key` (Gemini answers an invalid key with 400 instead of 401).

### Added
- `/pr-brief refresh` comment command (opt-in via the `issue_comment` trigger, owners, members and collaborators only, forks skipped, cache bypassed): see `docs/refresh.md` and ADR 7.
- `preset` setting and input (`cheap`, `balanced`, `strict`): ready-made token budgets that single settings can still override.
- Usage report in the job summary: number of provider requests and, when `price-input-per-million` and `price-output-per-million` are set, an estimated cost from your own prices.

## [1.1.0] - 2026-11-20

### Added
- Opt-in live tests for the OpenAI-compatible and Anthropic adapters (`just live`, separate keys).
- A `codeql.yml` workflow that runs only on public repositories; CI keeps the coverage report as a job-summary table and an artifact.
- `skip-bots` input and setting (default `true`): pull requests opened by bots such as Dependabot are skipped.

### Fixed
- `dogfood.yml` no longer shares its `concurrency` group with the README workflow: a skipped
  workflow still takes the group and cancelled the real run (found on a real runner). Documented
  in `docs/troubleshooting.md`.

## [1.0.0] - 2026-11-20

First release.

### Added
- Project bootstrap: package skeleton, tooling, CI (a separate `security` job runs `pip-audit` and
  gitleaks), architecture decision records in `docs/adr/`.
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
