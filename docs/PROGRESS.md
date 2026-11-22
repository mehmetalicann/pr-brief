# Progress log

Short, dated record of what was done per phase. Details live in git history; rules and scope live in `PROJECT_SPEC.md`.

## Open items (review before starting the next phase)

Items that were not finished when their phase was closed. Before a new phase starts, the
assistant must list these to the maintainer and ask whether to do them first. When one is done,
move it to the log below with the date.

1. **Phase 3: real vendor endpoints never called** (OpenAI-compatible, Anthropic). The live tests are written (`tests/providers/test_openai_live.py`, `test_anthropic_live.py`, `just live`) but need a paid key from the maintainer; until they pass, the "Verification status" tables keep saying mock-only. Optional.
2. **Item 1 knowingly left open** (no paid key for now), see above.

## 2026-11-22 - Phase 7: inline review comments built, plugin entry-points closed (maintainer approved both)
- **Inline review comments** (`inline-comments`, opt-in, default `false`; design approved by the maintainer, ADR 8, `docs/inline-comments.md`): the model may quote one diff line per risk (`path`, `quote`, optional fields on `Risk`); `core/inline.py` finds the line number in the parsed diff and drops short, missing or ambiguous quotes and hunks whose line count disagrees with the header; at most 5 comments, high before medium; one `COMMENT` review on the head commit; `github/inline.py` posts new comments first, keeps identical ones and deletes stale ones, only if they carry our marker and were written by `github-actions[bot]`; failures are logged and shown in the job summary, never fatal. The prompt asks for quotes only when the setting is on and the brief is a single call (chunked briefs get none, also not in their repair step); the cache key includes the setting only when it is on. One new setting and input, two new optional output fields.
- **Plugin entry-points: closed, not built** (ADR 9): running code from a package chosen at run time conflicts with the supply-chain rule; `openai-compatible` with `base-url` covers other services.
- Tests first (red, then green): 911 pass (+4 skipped, 4 deselected), coverage 98.3%, bandit, pip-audit, gitleaks clean. Mutation-checked, 13 mutants killed (accepting ambiguous quotes, skipping the hunk-count check, tiny quotes, no cap, commenting on low risks, ignoring author or marker, deleting kept comments, reposting identical ones, `APPROVE` instead of `COMMENT`, fatal inline errors, cache key ignoring the flag, quotes asked for in chunked briefs).
- Found by the mutation run: (1) a test fixture whose hunk header did not match its lines, so the ambiguity test passed for the wrong reason; (2) the chunked repair path was not covered. Both fixed. **Pitfall:** a mutant of the same length restored within the same second keeps a stale `.pyc` (an `APPROVE`/`COMMENT` swap made a normal run fail although the source was fine); run mutation checks with a fresh `PYTHONPYCACHEPREFIX` per mutant and `-B`.
- Not verified against real GitHub or a real model yet (fake GitHub API and mock provider only): a first trial on a sandbox PR with `inline-comments: true` and a real key is the next step before releasing it (needs the maintainer's secret, see the notes on trials below).
- Not committed yet. Release (`v1.3.0`: version bump, CHANGELOG, Marketplace box) only on the maintainer's request.

## 2026-11-22 - Review fixes committed, Dependabot PRs merged, SHA pinning enforced
- Review fixes committed and pushed (`7791e3e` code and tests, `9ece50e` docs). The pre-commit gitleaks hook flagged three fake test values in `tests/unit/test_redact.py`; they carry an inline `# gitleaks:allow (fake test value)` (no change to `.gitleaks.toml`).
- Dependabot PRs #6 and #7 (`codeql-action` 4.39.1 to 4.39.3) squash-merged; the new SHA was checked against the `v4.39.3` tag before merging. CI on `main` green.
- Repository setting `sha_pinning_required` switched on (private repo; all `uses:` are SHA-pinned, only `./` local uses remain). CI stayed green afterwards.
- Pre-flight for going public re-checked: only noreply author addresses, no personal paths or e-mail in files, gitleaks clean, `v1` and `v1.0.0` tags on the remote. Branch protection and rulesets are still missing (not available on the private free plan); set them from `docs/going-public.md` before the visibility switch.
- **`v1.2.0` released with a signed tag** (cut by the maintainer on `a38610b`): `release.yml` passed (`verify`, `publish`), the release (not draft) carries `sbom.cdx.json`, `v1` moved to the same commit, GitHub reports the tag as verified (`reason: valid`). Open item 3 (tag not cut) is closed.
- **Repository made public (2026-11-22)** after the pre-flight (check, history authors, no personal data, tags, release gate, CI green). Applied and read back through the API: ruleset `release tags` (no delete, update or non-fast-forward on `v*.*.*`; `v1` stays movable for `release.yml`), ruleset `main` (no deletion, no force-push, `check (3.11)` and `check (3.12)` required), private vulnerability reporting, Dependabot alerts and security updates, secret scanning with push protection, fork PR approval for all external contributors, read-only workflow token, SHA pinning required, wiki and projects off, description and topics.
- **Correction:** the earlier note that the `main` ruleset would not block direct pushes was wrong: a required status check rejects a push of a commit that has no result yet. Fix: the repository admin role is a bypass actor (`actor_id` 5, `always`), so the maintainer can push directly while PRs from others must pass the checks. `docs/going-public.md` updated.
- The `main` ruleset was proven by a real direct push (`e635da3`): GitHub printed "Bypassed rule violations" and accepted it. First CodeQL run on the public repository succeeded; its single alert (`py/clear-text-logging-sensitive-data`, high) points at `tests/security/test_token_leak.py`, where the test logs a fake runtime-built secret on purpose to prove masking. Dismissed as "false positive" with that comment (reversible in the Security tab); no change to the CodeQL configuration. Secret scanning and Dependabot alerts: 0 open. Community profile 100%.
- **Marketplace listing published (2026-11-22)** by the maintainer on release `v1.2.0` (name "PR Brief" was free). Checked: `github.com/marketplace/actions/pr-brief` answers 200, belongs to this repository, categories Code review and Utilities, usage example `@v1`, release still carries `sbom.cdx.json`, `v1` and `v1.2.0` unchanged. Open items 2 (Marketplace) and 3 (public settings) are closed. Each new release needs the Marketplace box ticked again on the release form.
- Still open: optional live OpenAI/Anthropic check (no paid key), Phase 7 leftovers (inline review comments need a design talk; plugin entry-points not recommended).

## 2026-11-20 - WHERE WE STOPPED (superseded by the 2026-11-22 entry above for items 1 and Dependabot)
- **Uncommitted work on `main`** (HEAD `4fc95af`, pushed): the security review fixes and docs of the entry below (redaction patterns, sanitiser clip, backtracking-free glob matcher, nesting errors, COLLABORATOR wording, CHANGELOG `[1.2.0]` Security section, `docs/security-model.md`, this log). `just check` passed with all of it (856 tests, coverage 98.4%, release gate for `v1.2.0` OK). It waits for the maintainer's "commit and push".
- **Next steps, in order:** (1) commit and push the review fixes; (2) the maintainer signs and pushes `v1.2.0` (`! git tag -s v1.2.0 -m "v1.2.0"`, then `git push origin v1.2.0`; `release.yml` publishes and moves `v1`); (3) Marketplace walk-through (`docs/marketplace.md`), before going public; (4) optional: live OpenAI/Anthropic check, going public (`docs/going-public.md`), Phase 7 leftovers (inline review comments need a design talk; plugin entry-points not recommended).
- **Nothing was cut off mid-way.** No trial or test was interrupted and no run is pending: sandbox PR #4 and #5, their branches, the temporary trial workflow and the `LLM_API_KEY` repository secret are all deleted (checked: 0 secrets, 0 open PRs, no `v1.2.0` tag yet). Last full runs all passed.
- **If a new session finds anything half-done** (an open sandbox PR or branch, a leftover `refresh-trial.yml` or secret, a failing or hanging test, a scratch probe still running, a command that was denied or timed out): do not trust earlier results, run `git status`, `gh pr list`, `gh secret list` and `just check` first, then redo the interrupted step from the start and log it.
- Handy facts for trials: the maintainer sets the secret with a pipe from `.env` (`! sed -n 's/^PR_BRIEF_API_KEY=//p' .env | tr -d "
\"'" | gh secret set LLM_API_KEY --repo mehmetalicann/pr-brief`; `!` cannot prompt); the assistant never reads `.env`; comments that start with `/` need `MSYS_NO_PATHCONV=1` in Git Bash; delete the secret and sandbox PR afterwards.

## 2026-11-20 - Security review and open items (maintainer: revise, close holes, close open items)
- Method: scanners again (bandit, pip-audit, gitleaks, zizmor: nothing new) plus adversarial probes written for this review (hostile model text through the sanitiser and renderer, fence breakout in the commit block, timing of every regex-heavy stage on inputs doubling in size).
- Clean: the output sanitiser removed every image, HTML tag, comment, external link, mention and cross-repository reference in 47 payloads; the commit message fence cannot be closed from inside; `action.yml` and the workflows pass inputs only through `env`; caches are scope-isolated and re-sanitised on read.
- Found and fixed (tests first, each red before green): quadratic redaction on hostile text (`a.a.a...` 32 KB: 73 s; `password=` x 120k: hours); quadratic link patterns in the sanitiser on model output (`[a](` x 40k: 3 minutes; the schema does not cap `risks[].note` or `area`); exponential `ignore` glob matching (now a backtracking-free matcher, equal to the old regex on 6000 random cases, hybrid for speed); `RecursionError` on deeply nested JSON/YAML.
- Wording corrected: GitHub's `COLLABORATOR` association can be read-only, so the refresh trust boundary is "people the maintainer invited" (code comment, ADR 7, `docs/refresh.md`).
- Accepted: the comment upsert reads at most 1000 comments (`MAX_PAGES`); the zizmor `$/` style hints stay (the `./` form is the documented, tested one).
- Still open (the maintainer's): live OpenAI/Anthropic check (no paid key), Marketplace publication, signed tag `v1.2.0` and, later, going public.

## 2026-11-20 - Phase 7 started: usage report and presets (maintainer picked usage report, presets, `/pr-brief refresh`)
- Usage report: the job summary now lists the number of provider requests (chunks, reduce step, repairs) and, only when the maintainer sets `price-input-per-million` and `price-output-per-million` (both or neither, 0 to 1,000,000), an estimated cost from those prices; a cache hit shows `$0.0000`. Decision: no built-in price list (prices change and differ per model). Two new optional settings/inputs, tests first.
- Presets: `preset: balanced | cheap | strict` sets only the token budgets (cheap 3000/500, balanced 6000/900, strict 12000/1500); single settings from file, environment or inputs still win; a test proves presets cannot touch anything but the two budgets. One new setting/input.
- Committed as `ebbb947` (usage report, presets).
- `/pr-brief refresh` (design approved by the maintainer, ADR 7, `docs/refresh.md`): opt-in `issue_comment` trigger; exact command, new comments only, by a person with association OWNER/MEMBER/COLLABORATOR, on a PR; forks skipped unless `allow-fork-target`; cache bypassed; same comment edited. Tests first; mutation-checked (adding `NONE` to the allowed list, dropping the bot check, prefix matching and dropping the fork check each fail tests). The workflow filter and the action check the same rules, and a test compares the two. No new input or setting.
- **Verified on a real runner (sandbox PR #5, closed; trial workflow, branch and secret removed):** the pull request run posted the brief; `/pr-brief refresh` from the owner edited the same comment (still one); an unrelated comment posted during a running brief was skipped and did not cancel it (job-level `concurrency`); a mangled command text was ignored.
- Found on the way: Gemini answers a wrong or empty key with HTTP 400, and the message only suggested the model name and `max-output-tokens`. The hint now also mentions the `api-key` (contract test for all four adapters, troubleshooting row updated). Trial pitfalls, not product bugs: `!` commands cannot prompt (use a pipe from `.env`), and Git Bash rewrites `/pr-brief` into a path (set `MSYS_NO_PATHCONV=1`).
- `just check` passes: 820 tests (+4 skipped, 4 deselected), coverage 98%, bandit, pip-audit, gitleaks clean. Not committed yet.
- `just check` passes: 767 tests (+4 skipped, 4 deselected), coverage 98%, bandit, pip-audit, gitleaks clean.

## 2026-11-20 - v1.1.0 released with a signed tag
- Dedicated SSH signing key (passphrase protected, private key never read by the assistant), registered on GitHub as a *signing key*; repo-local git config (`gpg.format ssh`, `user.signingkey`, `.git/allowed_signers`, not committed).
- Signed annotated tag `v1.1.0` on `d028be1`; `release.yml` passed (`verify`, `publish`), release has `sbom.cdx.json`, `v1` moved to the same commit. GitHub reports the tag as verified (`reason: valid`). `v1.0.0` stays unsigned and must not be re-pointed.
- Signing now needs the maintainer to type the passphrase: the assistant cannot create signed tags without it (no ssh-agent); the maintainer runs `git tag -s` with `!`.

## 2026-11-20 - Open items worked off before Phase 7 (maintainer: "do these first")
- New `skip-bots` setting/input (default `true`, schema change approved): PRs whose author is a GitHub App (`type == Bot` or login `[bot]`) end with a neutral skip; tests first (config, client, integration incl. base-config override), docs in README, `docs/action.md`, `configuration.md`, `troubleshooting.md`, `.pr-brief.example.yml`; L7 row in the security model updated.
- CI keeps coverage without an external service: `coverage report --format=markdown` into the job summary and `coverage.xml` as an artifact (`actions/upload-artifact` pinned to a SHA, 3.12 job only); a test guards it.
- `codeql.yml` added (SHA-pinned, `security-extended`, least privilege, skips itself while the repository is private); a test guards it; zizmor still shows only the two low `$/` hints.
- Live tests for OpenAI-compatible and Anthropic written with separate env keys so another vendor's key can never be sent by accident; skipped without keys.
- `just check` passes: 744 tests (+4 skipped, 4 deselected), coverage 98%, bandit, pip-audit, gitleaks clean.

## 2026-11-20 - v1.0.0 released, `@v1` verified on a real runner
- Tag `v1.0.0` (annotated, unsigned) cut on `ead6fc5`; `release.yml` passed the gate and `just check`, published the GitHub release with `sbom.cdx.json` and moved the major tag `v1` to the same commit.
- Sandbox PR #4 used the README workflow verbatim with `@v1`: without a secret the run stayed green and logged the fail-soft `api-key is required` message; with a real Gemini key it posted one `github-actions[bot]` comment and a second push edited it in place (still one comment). PR, branch and secret deleted afterwards.
- Bug found by the trial: `dogfood.yml` shared its `concurrency` group with the README workflow, and a skipped workflow still took the group and cancelled the real run. Own group now, guarded by a test, documented in `docs/troubleshooting.md` (commit `6eda46a`).

## 2026-11-20 - Phase 6 prepared: gaps closed, tree ready for v1.0.0 (tag not cut)
- Real runner dry run of `release.yml` (manual, tag `v1.0.0`): found a bug on the way, `git fetch` without credentials failed on the private repository (checkout runs with `persist-credentials: false`); removed (checkout with `fetch-depth: 0` already has `origin/main`) and guarded by a test. Before the version bump the dry run was rejected by the gate for the right reasons (versions, CHANGELOG, README notice) and `publish` was skipped.
- Gaps against the spec closed: `docs/adr/` (6 records: just, plain HTTP, trigger and fork policy, composite action with locked dependencies, one comment by marker and author, gated releases) with a format test; `CONTRIBUTING.md` points to the provider guide and the ADRs; separate `security` CI job (`just sec`: pip-audit and gitleaks), as in spec 7.4; labels `provider` and `security` created on the repository (`good first issue` already existed).
- The release gate also rejects a `SECURITY.md` that still says pre-release; a test keeps `main` consistent with its own version at all times.
- Release prep: version 1.0.0 in `pyproject.toml` and `__init__.py`, CHANGELOG `[1.0.0] - 2026-11-20` plus an empty `[Unreleased]`, README pre-release notice removed, `SECURITY.md` supports the latest `v1`. `scripts/release.py verify --tag v1.0.0` exits 0, `scripts/sbom.py` writes a valid file.
- Still not done (not blocking): the spec's "coverage upload" in CI (needs an external service), bot-PR skipping (optional L7), real OpenAI/Anthropic calls.
- `just check` passes: 734 tests (+4 skipped, 2 deselected), coverage ~98%, bandit, pip-audit, gitleaks clean.

## 2026-11-20 - Maintainer decisions on the open items, release structure (Phase 6 started)
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
