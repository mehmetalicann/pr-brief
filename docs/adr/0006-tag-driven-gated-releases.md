# 6. Tag-driven, gated releases with a moving major tag

## Status
Accepted (2026-11-20)

## Context
Users write `uses: mehmetalicann/pr-brief@v1`. A release must never ship with a wrong version, a
missing changelog section or an install snippet that does not resolve, and published version tags
must stay put.

## Decision
Pushing `vX.Y.Z` runs `release.yml`: the commit must be on `main`, `scripts/release.py verify`
checks the versions, a dated CHANGELOG section and the README's `@vMAJOR` reference, and `just check`
runs. Only then does a job with `contents: write` create the GitHub release from the CHANGELOG,
attach a CycloneDX SBOM and move `vMAJOR` (only for the newest release of that line). A manual run
is always a dry run. Tags `vX.Y.Z` are protected by a ruleset once the repository is public;
`vMAJOR` is not.

## Consequences
A release is one `git tag` plus a short checklist (`docs/releasing.md`). A bad release is fixed
forward with a new patch version. Signing tags needs a signing key on the maintainer's account.
