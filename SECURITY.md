# Security Policy

## Supported versions

Only the latest `v1` release (the `v1` tag) is supported. Fixes are published as a new patch
version; please update before reporting.

## Reporting a vulnerability

Please report privately through GitHub:
**Security tab → "Report a vulnerability"**
(<https://github.com/mehmetalicann/pr-brief/security/advisories/new>).

- Do **not** open public issues, discussions or pull requests for security problems.
- If the button is not available, open an issue titled "Security contact request" with **no
  technical details**, and a private channel will be arranged.
- Include the affected version or commit, a reproduction (workflow YAML with placeholder secrets)
  and the impact. Never include real API keys, tokens or private code.

## In scope

- Secrets or personal data reaching an LLM provider despite redaction.
- Prompt injection that makes the generated comment leak data, notify users or teams, embed external
  images or links, or fake an approval.
- API keys or tokens appearing in logs, error messages, caches or comments.
- Permission escalation or secret exposure on fork pull requests, in the action or its workflows.
- Supply-chain problems: unpinned actions, vulnerable or malicious dependencies.

## What to expect

This project is maintained by one person on a best-effort basis. The goal is to acknowledge a report
within 7 days, agree on a fix and a coordinated disclosure date, and credit you in the release notes
unless you prefer to stay anonymous.

## Security model

The threat model, the controls and their known limits are documented in
[`docs/security-model.md`](docs/security-model.md).
