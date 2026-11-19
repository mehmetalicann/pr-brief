# Security model

pr-brief sends part of a pull request to a third-party LLM and posts the answer on a public or
private pull request. Both directions are untrusted. This page lists what is protected, how, and
what is **not** guaranteed. Report problems as described in [`SECURITY.md`](../SECURITY.md).

## Layers

| Layer | Threat | Control | Status |
|-------|--------|---------|--------|
| L1 Trigger and permissions | Secrets leaking to fork PRs, privilege escalation | `pull_request` (not `pull_request_target`), minimal `permissions`, the PR's code is never checked out or run (diff and metadata come from the API), the action runs from a neutral directory with `PYTHONSAFEPATH`, graceful skip for forks and missing secrets | **Done** (Phase 4) |
| L2 Input minimisation and masking | Secrets/PII sent to the LLM | `security/redact.py` masks tokens, keys, JWTs, private keys, credential assignments, URL credentials, bearer tokens, e-mails, private IPv4 ranges and high-entropy strings **before parsing, chunking and any provider call**; sensitive files (`.env*`, `*.pem`, `*.key`, `id_rsa*`, …) are never sent | **Done** (Phase 2) |
| L3 Prompt-injection resistance | A malicious diff or PR text steers the model | One data block per prompt with a **random delimiter id**; look-alike delimiters, control, zero-width and bidi characters are removed from untrusted text; the system prompt names the id and says the block is data; no tools or network for the model; output must match a JSON schema | **Done** (Phase 2) |
| L4 Output sanitising | Exfiltration via links/images, mass mentions, HTML, spoofed sections | `security/sanitize.py`: no images or HTML, links only inside `github.com/<owner>/<repo>`, mentions wrapped in backticks, comment markers neutralised, fields flattened to one line and length-capped, file names made inert | **Done** (Phase 2) |
| L5 Secret handling | API key in logs, errors, caches | Key read from the environment only (rejected in `.pr-brief.yml`), `SecretStr`, a single logger whose filter masks registered secrets, credential headers and token shapes and never logs tracebacks, errors name the exception type only, final comment is masked once more | **Done** (Phases 2 and 4): the GitHub token is sent in the `Authorization` header only and registered with the log filter; the cache stores only the sanitised, masked brief JSON, under a SHA-256 key, validated and re-sanitised on read |
| L6 Network egress | Data sent to unexpected hosts | Fixed vendor endpoints for Anthropic and Gemini; `https` (or localhost) for custom `base-url`, no URL credentials or query strings; timeouts, at most two retries, 1 MB response cap, no redirects, no proxy variables; error messages never contain headers or bodies | **Done** (Phase 3) |
| L7 Cost / DoS | Huge or spammy PRs drain the budget | Token budgets, file and size caps, chunk cap with explicit "not analyzed" list | Partly done (budgets, caps, cache for identical input); skipping bot PRs is not implemented (optional in the spec) |
| L8 Supply chain | Malicious dependency or action | Three runtime dependencies, actions pinned to commit SHAs, Dependabot, `pip-audit`, `bandit`, `gitleaks` in CI | Partly done; hash-locked installs (`requirements.lock`) done in Phase 4, CodeQL and SBOM later |
| L9 Repository hygiene | Contributors leaking secrets, unclear reporting | `SECURITY.md`, pre-commit `gitleaks`, no real secrets in tests (fake ones are built at runtime) | **Done** |

## Order of operations (a security property)

```
diff + PR text -> redact -> parse -> filter (sensitive files dropped) -> chunk
   -> prompt (untrusted block) -> provider -> schema validation -> sanitise -> mask -> render
```

`tests/integration/test_redaction_order.py` proves that no provider call, in the single-call and
the map-reduce paths, and not even the chunker, ever sees a masked value.

## Known limits

- **`base-url` comes from configuration.** If `.pr-brief.yml` were read from the pull request's own
  branch, a PR could point `base-url` at a server it controls. The GitHub mode therefore reads the
  config file through the API at the **base commit's SHA**, never from the PR head or the
  workspace (`tests/integration/test_github_action.py` proves the head file is never requested).
  A PR that changes `.pr-brief.yml` only takes effect after it is merged.
- **The update target is identified by author and marker.** Only a comment that starts with the
  marker *and* was written by `github-actions[bot]` is edited. If you post with another identity
  (a PAT or a GitHub App token), the comment is not recognised and a new one is created each run.
- **`pull_request_target`** gives fork PRs secrets and a write token. The action supports it
  because it never checks out or runs PR code, but the default and recommended trigger is
  `pull_request`, where fork PRs are skipped.

- **Redaction is best effort.** Unknown token formats, secrets split across lines, or secrets
  embedded in prose can pass. High-entropy detection trades false negatives for fewer false
  positives; if code must never reach a third party, use a self-hosted model or do not enable the
  action.
- **False positives exist** (an identifier that looks like a key is masked); the summary then
  mentions `[REDACTED:…]`.
- **Prompt injection cannot be fully prevented**, only contained: the worst a hostile diff can do
  is produce misleading *text*, and that text is flattened, defanged and schema-bound.
- Masking runs on the raw diff text, including file names in the diff headers, but it can only
  recognise patterns it knows; see the first point.

## STRIDE summary

| | Threat | Mitigation |
|-|--------|------------|
| **S**poofing | Fake "approved" or fake pr-brief comment | Fields are single-line; the marker is neutralised in model output; only one marker, as the first line |
| **T**ampering | Diff text rewrites instructions | Random delimiter id, delimiter neutralisation, schema-bound output |
| **R**epudiation | No trace of what was sent | Run details list redaction counts, skipped files and token usage |
| **I**nformation disclosure | Secrets to the LLM, to logs, or into the comment | L2, L4, L5; sensitive files never sent |
| **D**enial of service | Giant or spam PRs | Budgets, caps, chunk limit, size limit on the diff |
| **E**levation of privilege | Fork PR gains secrets or write access | L1; no code execution of PR content, ever |

## How this is tested

`tests/unit/test_redact.py`, `test_sanitize.py` and `tests/security/` (prompt injection, output
exfiltration, token leakage) use hostile fixtures. They run in `just check` and in CI, and they
block a release (Phase 6).
