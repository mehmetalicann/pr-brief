# 1. `just` instead of `make`

## Status
Accepted (2026-11-14)

## Context
The spec names Makefile targets, but the maintainer works on Windows 11 with Git Bash, where `make`
is not installed.

## Decision
Use `just` (a `justfile` with the same target names). It is installed from PyPI as the dev
dependency `rust-just`, so `pip install -e ".[dev]"` is the only setup step. Where the spec says
`make check`, read `just check`.

## Consequences
One task runner on every OS and in CI (`.venv/bin/just check`). Contributors need the dev extra,
not a system package. The spec text and the justfile can drift: the target names are the contract.
