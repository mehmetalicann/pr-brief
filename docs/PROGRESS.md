# Progress log

Short, dated record of what was done per phase. Details live in git history; rules and scope live in `PROJECT_SPEC.md`.

## Open items (review before starting the next phase)

Items that were not finished when their phase was closed. Before a new phase starts, the
assistant must list these to the maintainer and ask whether to do them first. When one is done,
move it to the log below with the date.

1. **Phase 3: real vendor endpoints never called** (OpenAI-compatible, Anthropic). Request and
   response shapes follow the vendors' documented APIs and are covered by mocks only. Gemini and
   Ollama were checked live. The README and `docs/providers.md` now say so under "Verification
   status" (a test keeps both honest). Closing it needs a paid key and one `tests/providers/`
   live test per vendor. Optional, does not block the release.
2. **Phase 6 is started, not finished** (see the entry below): the release workflow, its gate and
   the docs exist, but no tag has been cut. Still to do: bump the version to 1.0.0 in
   `pyproject.toml` and `src/pr_brief/__init__.py`, date the CHANGELOG section, delete the README's
   "Status: pre-release" notice, set up a signing key for `git tag -s`, then tag. Also open: issue
   labels, `codeql.yml` (needs a public repository), the manual Marketplace publication.

## 2026-11-20 - Maintainer decisions on the open items, release structure (Phase 6 started, not committed yet)
- Item "demo GIF": generated instead of recorded. `scripts/make_demo_gif.py` runs the real pipeline (mock provider, canned model text) on a tiny demo diff, draws a PR page around the real comment, screenshots it with headless Edge and joins 6 frames with ffmpeg: `docs/assets/demo.gif` (83 KB, 800x900, ~20 s, loops). Every frame says "Illustration, not a screen recording"; the README says the same. No Python dependency added. I looked at the frames: no personal data or secrets.
- Item "real vendor endpoints": README and `docs/providers.md` got a "Verification status" table (Ollama and Gemini live, OpenAI-compatible and Anthropic mock-only, with a request to open an issue).
- Item "`@<full-commit-sha>` placeholder": the README now says `@v1`, explains pinning to a full commit SHA and how to find it, and carries a pre-release notice instead of a placeholder. To make sure the repository cannot go public or release with a broken snippet: `scripts/release.py verify --tag vX.Y.Z` (stdlib only) fails unless `pyproject.toml`, `__init__.py`, a dated CHANGELOG section and the README's `@vMAJOR` agree and the pre-release notice is gone; a test proves it rejects the repository as it is today. `.github/workflows/release.yml`: tag `vX.Y.Z` (or a manual dry run with a tag name) -> commit must be on `main` -> gate -> `just check` -> only for a tag push: GitHub release from the CHANGELOG section and the major tag moved through the API (only for the newest release of its line). Read-only token except in the publish job, no `${{ }}` inside scripts, actions pinned to SHAs, `zizmor` clean. `docs/releasing.md` (steps, signing, dry run), `docs/going-public.md` (do not publish before the tag exists; tag ruleset that protects `vX.Y.Z` but not `v1`).
- SBOM: `scripts/sbom.py` writes a CycloneDX 1.5 file from the hash-locked `requirements.lock` (names, versions, purls, SHA-256 hashes); `release.yml` attaches it to the release as `sbom.cdx.json`. Marketplace: a test checks `action.yml` against the Marketplace limits (description at most 125 characters, valid colour and icon, file at the root); the listing text is in `docs/marketplace.md`; the name's uniqueness can only be checked in the listing form.
- Not verified on a real runner yet: `release.yml` (it needs to be on `main` for the dry run; planned after the push). Not done: tag signing key (needs the maintainer).
- `just check` passes: 720 tests (+4 skipped, 2 deselected), coverage ~98%, bandit, pip-audit, gitleaks clean.

## 2026-11-20 - Open item closed: three security hardening decisions (maintainer said "do all three")
- Tests first (red, then green), then code. (a) Fork PRs under `pull_request_target` are now skipped unless the new action input `allow-fork-target: true` is set (`github/context.skip_reason`, `action.yml`, docs; same-repo PRs under that event are unaffected). (b) The output sanitiser wraps cross-repository references (`owner/repo#12`, `owner/repo@sha`) in backticks so GitHub creates no backlink; same-repo `#12` is left alone. (c) The README workflow and `dogfood.yml` have a per-PR `concurrency` group with `cancel-in-progress`; a test guards both.
- Spec impact: one new action input (`allow-fork-target`), one stricter default; documented in README, `docs/action.md`, `docs/configuration.md`, `docs/security-model.md`, `docs/troubleshooting.md`.

## 2026-11-20 - Phase 5 closed: README verified on a real runner, security pass
- README replayed offline: `tests/integration/test_readme_quick_start.py` reads the workflow out of README.md, maps its `with:` inputs through `action.yml`'s env wiring, and runs it against the fake GitHub API and a fake Gemini endpoint (one comment, push edits it, key only in the header, fork and missing-secret stay green). Mutation-checked: renamed input, hard-coded key, `pull_request_target`, bad model name each fail it.
- Real runner (sandbox PR #2, closed, branch and secret deleted): the README workflow, copied verbatim with only the commit SHA filled in, produced one `github-actions[bot]` comment with real `gemini-3.5-flash-lite` output 29 s after the PR was opened (3 chunks, 13.7k input tokens). A second push updated the same comment (still exactly one). Fork behaviour is still covered by tests only.
- Bug found by the trial: the footer link of every comment pointed to `README#configuration`, but the heading was "Settings". Now a test (`test_comment_footer_links_point_to_real_readme_sections`) guards it and the heading is "Configuration".
- Security pass: reviewed the GitHub client, comment upsert, cache, sanitiser, provider HTTP layer and workflows. Confirmed: token only in the Authorization header, redirects off, responses size-capped, config read from the base commit, cache entries validated and re-sanitised on read, update target restricted to the bot's own marker comment, all actions pinned to SHAs, no `${{ }}` inside scripts. `zizmor` (workflow scanner, run from a throwaway venv, not a project dependency) found only Dependabot cooldown (fixed: 7 days, with a test) and a style hint (`$/` instead of `./`, left as is). No exploitable hole found; the three hardening decisions were then made and done, see the entry above.
- `just check` and the Phase 5 acceptance are met; open: demo GIF (maintainer's screen recording) and the `@<full-commit-sha>` placeholder until the `v1` tag exists (Phase 6).

## 2026-11-20 - Phase 5: UX, docs, i18n (committed)
- Decision at the start: continued with the OpenAI-compatible/Anthropic live check still open (item 1); remind again now.
- Tests first (red, then green): `tests/unit/test_i18n.py` (same keys and placeholders in `en` and `tr`, fallback to English) and `tests/unit/test_docs.py` (YAML examples parse, README quick start uses real `action.yml` inputs and the required permissions, every input documented in README and `docs/configuration.md`, relative links resolve, example config loads and shows every setting). An old render test used `tr` as its "unknown language" example; it now uses `xx`, plus a new Turkish-comment test.
- `core/i18n.py` now has the Turkish table. New: `.pr-brief.example.yml`, `docs/configuration.md` (the file the error hints already pointed to), `docs/troubleshooting.md` (forks, secrets, quota/429, 403, Ollama on self-hosted runners, large PRs), `docs/architecture.md`, `scripts/make_demo_gif.md`. README rewritten: why, 5-step quick start, example comment, settings table, FAQ, free-tier data note, short Turkish section.
- Lint: ruff `RUF001` (ambiguous dotless i) is ignored for `core/i18n.py` and `tests/**` in `pyproject.toml`.
- Not done: `docs/assets/demo.gif` (needs a screen recording by the maintainer; see `scripts/make_demo_gif.md`), `docs/adr/` (not a Phase 5 output). The README quick start still says `@<full-commit-sha>` until the `v1` tag exists (Phase 6).
- Acceptance "a new user can follow the README in under 5 minutes" was verified afterwards, see the entry above.
- `just check` passes: 653 tests (+4 skipped, 2 deselected), coverage ~98%, bandit, pip-audit, gitleaks clean.

## 2026-11-20 - Open item partly closed: live Gemini test
- `just live` with a Google AI Studio key (kept in the git-ignored `.env`, never shown to the assistant): `gemini-3.5-flash-lite` returned a schema-valid brief (2 passed, ~11 s). The request path (`/v1beta/models/{model}:generateContent`, `x-goog-api-key`) works against the real API.
- Other models on the same key: `gemini-2.5-flash` and `gemini-2.5-flash-lite` answered 404 although they are listed by `models.list`; `gemini-flash-latest` and `gemini-3.5-flash` answered 503 (capacity) after the 2 retries. So the test default `gemini-2.5-flash` is outdated; set `PR_BRIEF_LIVE_GEMINI_MODEL` in `.env`.
- Still open: OpenAI-compatible and Anthropic real endpoints (no key yet).

## 2026-11-19 - Open item closed: Phase 4 on a real GitHub runner
- Committed and pushed Phase 4 (main CI green: `check` 3.11/3.12). Sandbox PR #1 on this repo (mock provider through `dogfood.yml`, temporary repository variables): the first run created exactly one comment by `github-actions[bot]`; a second push updated the same comment (same id, later `updated_at`), the result cache was restored from the previous run, and `action-smoke` was green. PR closed, branch and variables deleted.
- Fork/secret-less behaviour is covered by tests only (needs a second GitHub account to try for real).
- Also checked `claude doctor`: auto-updates were already enabled; the earlier `install_failed` was the running executable on Windows, `claude update` downloaded 2.1.328 (active after a restart).

## 2026-11-19 - Phase 4: GitHub integration and packaging (done, pushed)
- Decision at the start: continued with the Gemini/OpenAI/Anthropic real-endpoint check still open (item 1); remind again now.
- Tests first (red, then green): `test_github_client`, `test_comments`, `test_event`, `test_cache`, `test_action_yml`, `tests/integration/{test_github_action,test_fork_pr}` and config-loader cases, all against a fake GitHub API (`tests/_support/github_fake.py`).
- `github/{client,comments,context}.py`, `cache.py`, `action.py` (`python -m pr_brief --github`), `action.yml` (composite), `requirements.lock` (hash-locked, generated with Python 3.12 via `just lock`), `.github/workflows/dogfood.yml` (off unless `vars.PR_BRIEF_DOGFOOD == 'true'`, checks out the base commit because it holds a secret), `action-smoke` job in `ci.yml`, `docs/action.md`.
- Config is read through the API at the base commit SHA (new `config_loader` hook in `load_settings`); a head-branch config is never requested (tested).
- Fork PRs under `pull_request`, drafts (unless `include-drafts`) and unrelated events end with exit 0 and a summary notice; read-only token, missing key and provider errors fail soft; `fail-on-error` returns 1.
- Spec deviations/choices: cache key also covers language, PR text, repository, limits and ignore globs (stricter than the spec's diff + prompt version + model); only comments by `github-actions[bot]` that start with the marker are updated; bot-PR skipping (optional in L7) is not implemented; `pip-tools` added as a dev dependency; new `--github` CLI flag.
- `just check` passes: 580 tests (+4 skipped, 1 live deselected), coverage ~98%, bandit, pip-audit, gitleaks clean.

## 2026-11-17 — Open item closed: live Ollama smoke test
- Ollama 0.40.16 + `llama3.2` (2.0 GB): `RUN_LIVE=1 PR_BRIEF_LIVE_MODEL=llama3.2 pytest tests/providers/test_ollama_live.py -s` passes (1 passed, ~18 s). The model returned a schema-valid brief for `small.patch` (1 chunk, 498 input / 399 output tokens). Phase 3 acceptance criterion met.
- Test fix: `print(md)` crashed on the default Windows console (cp1254, emoji); it now prints an ASCII-safe copy.

## 2026-11-15 — Open item closed
- GitHub e-mail privacy settings ("Keep my email addresses private", "Block command line pushes that expose my email") enabled by the maintainer.

## 2026-11-15 — Phase 3: Providers (done and committed; acceptance items 1–2 above are open)
- Tests first (red, then green): one contract suite (`tests/providers/test_provider_contract.py`) runs against all four adapters with `httpx.MockTransport`: success and usage, host and timeout, key never in URL/body/errors, retry with 1 s/2 s backoff and `Retry-After` (capped 10 s), no retry on 401/403/4xx, timeouts, connection errors, non-JSON and odd shapes, empty answers, 1 MB response cap (streamed and by `Content-Length`), no redirects, base-URL rules. Request-shape tests per adapter, registry tests, and a pipeline test through the HTTP layer (repair path, no secret in any request body).
- `providers/http.py` (shared `HttpProvider`), `ollama.py` (first, `/api/chat` with structured output), `openai_compat.py`, `anthropic.py`, `gemini.py` (key in `x-goog-api-key`, model name validated), `registry.py` with `get_provider(settings, transport=)`. `Provider.name` is now a read-only property in the protocol. New CLI flag `--base-url` (local runner).
- Base-URL rules: `https` (or `http` for localhost only), no credentials/query/fragment; `anthropic` and `gemini` refuse a `base-url`; remote OpenAI-compatible endpoints require a key, localhost does not.
- Live smoke test `tests/providers/test_ollama_live.py` (`RUN_LIVE=1`) is written but **not executed**: Ollama is not installed on this machine, so the acceptance item "RUN_LIVE=1 smoke test works locally with Ollama" is still open. Real vendor endpoints (OpenAI, Anthropic, Gemini) were not called either; shapes follow the vendors' documented APIs and are covered by mocks only.
- Phase 4 requirement noted in `docs/security-model.md`: read `.pr-brief.yml` from the base branch, never from the PR head (it can set `base-url`).
- `just check` passes; 464 tests (+4 skipped, 1 live deselected), coverage ≈ 99%. `docs/providers.md` written; README, CHANGELOG, security model updated.

## 2026-11-15 — Phase 2: Security layer (done; awaiting review and "continue")
- Tests first (red, then green): `test_redact`, `test_sanitize`, `tests/security/{test_prompt_injection,test_output_exfiltration,test_token_leak}`, `tests/integration/test_redaction_order`.
- `security/{patterns,redact,sanitize}`, `logging.py`; sensitive files (`.env*`, `*.pem`, `*.key`, `id_rsa*`, …) are dropped by `filters` with reason "sensitive file (never sent)".
- Pipeline order is now: redact (diff + PR title/body/labels) → parse → filter → chunk → prompt → provider → schema → sanitise → mask → render. An integration test proves no provider call or chunker input ever contains a masked value, in both single-call and map-reduce paths.
- Redaction keeps line counts and diff prefixes (private-key blocks are masked line by line), is idempotent, and is deliberately conservative about false positives (quoted values must contain no whitespace; unquoted values need a digit and a letter; entropy ≥ 4.5 bits, ≥ 32 chars, ≥ 3 character classes). Checked against the project's own files: the only false positive found (`"tokens": "Tokens: input …"`) was fixed and turned into a test.
- Defaults chosen with the user's "continue": private IPv4 always masked (no new config key), no e-mail allowlist, `run(..., repo=)` / `--repo owner/name` decides which links survive (none when unset).
- New CLI flag `--repo` (local runner only; Phase 4 will pass the real repository).
- `just check` passes; 287 tests, coverage ≈ 99%. `docs/security-model.md` written, README/SECURITY/CHANGELOG updated.
- Known limits are documented (best-effort redaction, injection is contained not prevented). Real providers, GitHub client and cache are still not implemented.

## 2026-11-15 — Phase 1: Offline core (done, pushed)
- Added `core/{diff,filters,chunker,schema,prompts,render,i18n}`, `config`, `errors`, `providers/{base,mock,registry}`, `__main__` (pipeline + CLI) and `scripts/run_local.py`. Tests for the diff parser and chunker were written first and seen failing.
- Pipeline: parse → filter → chunk (≤ 8 chunks; files beyond the cap are listed as "not analyzed", oversized files truncated with a marker) → single call, or map-reduce with per-chunk summaries → one repair attempt on invalid JSON → Markdown. Local runs are always dry runs and fail soft (exit 0 unless `fail-on-error`).
- Config precedence: defaults < `.pr-brief.yml` < `PR_BRIEF_*` env < CLI overrides. `api-key` is env-only and is rejected in the file; `config-path` must stay inside the repo.
- `just check` passes; 117 tests, coverage ≈ 98%. Golden files: `tests/fixtures/golden/{small,medium}.md` (regenerate deliberately if the render format changes).
- Deliberately left for later phases: redaction/sanitizer/prompt hardening (Phase 2), real providers and the `tr` string table (Phase 3 / Phase 5), GitHub client and comment upsert (Phase 4).
- Phase 0 follow-up: CI is green after the pip/setuptools fix (run 43690729642).

## 2026-11-15 — Public-readiness pass (before Phase 2)
- Goal: the repository can be made public at any moment without problems. Checklist and GitHub settings commands: `docs/going-public.md`.
- Added `CODE_OF_CONDUCT.md`, `CODEOWNERS`, issue-template config (blank issues off, private security link), real `SECURITY.md`, an honest pre-release README with a data/privacy note, `.gitattributes`, extra `.gitignore` entries, Conventional-Commit prefixes for Dependabot, project URLs in `pyproject.toml`.
- Git identity switched to the GitHub `noreply` address; the two Phase 0 commits were rewritten to remove the personal email from history (needs one `--force-with-lease` push, then `git gc`).
- Found by gitleaks at commit time: a literal fake API key in tests. Fixed by building fake secrets at runtime instead of widening `.gitleaks.toml`.
- Not done on purpose (needs a public repo or paid plan): private vulnerability reporting, secret scanning/push protection, rulesets, CodeQL.

## 2026-11-14 — Phase 0: Bootstrap (done, awaiting "continue")
- Task runner: `just` (no `make` on the author's Windows machine); `rust-just` is a dev dependency. Targets mirror spec section 7.2.
- Added package skeleton (`src/pr_brief`), tooling config (ruff, mypy strict, pytest, coverage), pre-commit (ruff, gitleaks), `CLAUDE.md`, LICENSE (MIT), stub docs, issue/PR templates, Dependabot, `ci.yml` running `just check` on Python 3.11/3.12 (actions pinned to commit SHAs).
- `just check` passes locally (lint, `mypy --strict`, tests at 100% coverage, bandit, pip-audit, gitleaks).
- `.gitleaks.toml` allowlists two fake sample secrets quoted in `PROJECT_SPEC.md` (JWT, `sk-test-…`), nothing else.
- Deferred to later phases: `action.yml`, `codeql.yml`, `release.yml`, `dogfood.yml`, `docs/*`, `.pr-brief.example.yml`, hash-locked dependencies, splitting pip-audit/gitleaks into separate CI jobs.
- First CI run (2026-11-14) failed in `pip-audit`: the CI venv bundled old pip (24.0/25.0.1) and setuptools (79.0.1) with known CVEs. Local venv was current, so it passed locally. Fix: `pip install --upgrade pip setuptools` before installing the project in `ci.yml` (2026-11-15; not yet pushed/verified on GitHub).
