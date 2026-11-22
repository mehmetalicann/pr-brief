# Refresh on demand: `/pr-brief refresh`

Optional. A maintainer writes `/pr-brief refresh` as a comment on a pull request and pr-brief writes
a new brief, edited into the existing comment. Use it after changing the model or the settings, or
when a provider hiccup left an old result.

It is off until you add the `issue_comment` trigger to your workflow. Nothing else changes.

## Workflow

Replace `.github/workflows/pr-brief.yml` with this (it still runs on every pull request update):

```yaml
name: PR Brief
on:
  pull_request:
    types: [opened, synchronize, reopened, ready_for_review]
  issue_comment:
    types: [created]
permissions:
  contents: read
  pull-requests: write
jobs:
  brief:
    if: >-
      github.event_name == 'pull_request' ||
      (github.event.issue.pull_request &&
      github.event.comment.body == '/pr-brief refresh' &&
      contains(fromJSON('["OWNER","MEMBER","COLLABORATOR"]'),
      github.event.comment.author_association))
    concurrency:
      group: pr-brief-${{ github.event.pull_request.number || github.event.issue.number }}
      cancel-in-progress: true
    runs-on: ubuntu-latest
    steps:
      - uses: mehmetalicann/pr-brief@v1
        with:
          provider: gemini
          model: gemini-3.5-flash-lite
          api-key: ${{ secrets.LLM_API_KEY }}
```

## Rules (the action enforces them again, the workflow filter is the first line)

- Only the exact comment `/pr-brief refresh` counts (surrounding whitespace is ignored). Replies,
  quotes and code spans do not.
- Only repository **owners, members and collaborators** may run it. Anyone else could spend your
  API budget with a comment. GitHub does not tell the action which permission level a
  collaborator has (an invited collaborator may be read-only), so only invite people you trust
  with the budget. Comments written by bots, including pr-brief's own, never run it.
- Only new comments count (not edits or deletions), and only on pull requests.
- A refresh skips the result cache, so the model is called again. It still follows `include-drafts`
  and `skip-bots`, and edits the same comment; there is never a second one.
- **Fork pull requests are skipped**, as with `pull_request_target`: a comment event hands secrets
  and a write token to a run that reads text the fork controls. `allow-fork-target: true` opts in;
  read the [security model](security-model.md) first.
- The settings come from the base branch, never from the pull request, as for every other run.

## Why the `concurrency` block is on the job

Every comment on every issue and pull request starts this workflow; the job filter skips almost all
of them. A skipped *workflow*-level group still takes the group and can cancel a real run (this
happened once, see [troubleshooting](troubleshooting.md)). On the *job* a skipped job never takes
the group, so an unrelated comment cannot cancel a brief that is being written.

## Troubleshooting

| What you see | Cause and fix |
|--------------|---------------|
| Nothing happens after the comment | The comment must be exactly `/pr-brief refresh`, written by an owner, member or collaborator, on a pull request. The workflow must be on the default branch (comment events use that version). |
| Job summary says the comment is not the command or the commenter is not allowed | The run was skipped on purpose; see the rules above. |
| Skipped for a fork pull request | See the fork rule above. |
