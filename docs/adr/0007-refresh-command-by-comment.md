# 7. `/pr-brief refresh` comment command, opt-in and maintainers only

## Status
Accepted (2026-11-20)

## Context
A maintainer sometimes wants a new brief without pushing a commit (a better model, new settings, a
provider error). A comment is the natural place, but `issue_comment` is a different security
situation from `pull_request`: it runs from the default branch with secrets and a write token for
every comment on every issue and pull request, whoever wrote it, and for fork pull requests too.
It also competes for `concurrency` groups: a skipped workflow once cancelled a real run.

## Decision
- The feature is opt-in: it exists only when the maintainer adds `issue_comment: [created]` to the
  workflow (`docs/refresh.md`). No new input, no change to the settings schema.
- The command is the exact comment `/pr-brief refresh` (whitespace trimmed), on a pull request,
  newly created, by a person (not a bot) whose association is `OWNER`, `MEMBER` or `COLLABORATOR`.
  The workflow `if:` and the action both check it, so a copied workflow without the filter is
  still safe.
- Fork pull requests are skipped unless `allow-fork-target: true`; the fork status comes from the
  API because the comment payload does not carry it.
- A refresh bypasses the result cache and edits the existing comment (still one comment).
- The `concurrency` group is set on the job, never on the workflow, so skipped comment runs cannot
  cancel a real one.

## Consequences
Contributors without write access cannot trigger paid model calls. The workflow file must be on the
default branch before the command works. The action rejects ignored comments before any API request,
so spam comments cost nothing but a short job.
