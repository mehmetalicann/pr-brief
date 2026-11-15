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
- Community and security files: `SECURITY.md`, `CODE_OF_CONDUCT.md`, `CODEOWNERS`, issue-template
  config, and `docs/going-public.md`.

### Fixed
- CI: upgrade the venv's bundled pip/setuptools before `pip-audit`.
