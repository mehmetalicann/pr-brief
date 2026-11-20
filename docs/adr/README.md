# Architecture decision records

Short records of decisions that are costly to reverse. Format: Status, Context, Decision,
Consequences. Add a new file (next number) instead of editing an accepted one; mark the old one
"Superseded by ...".

| # | Decision |
|---|----------|
| [1](0001-just-as-task-runner.md) | `just` instead of `make` |
| [2](0002-plain-http-no-vendor-sdks.md) | Plain HTTP with `httpx`, no vendor SDKs |
| [3](0003-trigger-and-fork-policy.md) | `pull_request` by default, forks skipped, config from the base commit |
| [4](0004-composite-action-with-locked-dependencies.md) | Composite action with hash-locked dependencies |
| [5](0005-one-comment-upserted-by-marker-and-author.md) | One comment, found by marker and author |
| [6](0006-tag-driven-gated-releases.md) | Tag-driven, gated releases with a moving major tag |
| [7](0007-refresh-command-by-comment.md) | `/pr-brief refresh` comment command, opt-in, maintainers only |
