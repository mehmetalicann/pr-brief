# Progress log

Short, dated record of what was done per phase. Details live in git history; rules and scope live in `PROJECT_SPEC.md`.

## Open items (review before starting the next phase)

Items that were not finished when their phase was closed. Before a new phase starts, the
assistant must list these to the maintainer and ask whether to do them first. When one is done,
move it to the log below with the date.

1. **Phase 3: real vendor endpoints never called** (OpenAI-compatible, Anthropic, Gemini). Request
   and response shapes follow the vendors' documented APIs and are covered by mocks only. Optional
   check with a real key via `scripts/record_fixture.py` (not written yet) or a one-off call.
   Status 2026-11-15: maintainer will try later with a Gemini API key from Google AI Studio; Phase 4
   starts without it (conscious decision), remind again at the end of Phase 4.

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
