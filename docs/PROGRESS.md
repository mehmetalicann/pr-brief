# Progress log

Short, dated record of what was done per phase. Details live in git history; rules and scope live in `PROJECT_SPEC.md`.

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
