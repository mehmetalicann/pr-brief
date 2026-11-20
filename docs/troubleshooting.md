# Troubleshooting

By default pr-brief never fails your pipeline: when something goes wrong the job stays green and
the reason, with a "How to fix" line, is written to the job log and the job summary. Set
`fail-on-error: true` if you would rather fail the job. To see what a run would post without posting
anything, set `dry-run: true`.

Messages below are quoted as the action prints them (the provider name varies).

## No comment appears

| What you see | Cause and fix |
|--------------|---------------|
| Job summary says the run was skipped for a **fork** pull request | Under `pull_request`, GitHub gives fork PRs no secrets and a read-only token, so the action cannot call the model or post. This is intended. Maintainers can re-run the PR from a branch in the main repository. Using `pull_request_target` for forks is possible only with the explicit `allow-fork-target: true` input and is dangerous; read the [security model](security-model.md) first. |
| Skipped, draft PR | Drafts are ignored. Set `include-drafts: true`, or mark the PR ready for review (the `ready_for_review` event triggers a run). |
| The run is **cancelled**, with the annotation "Canceling since a higher priority waiting request for pr-brief-N exists" | Two workflows use the same `concurrency` group (even a workflow whose jobs are skipped takes its group). Give each workflow its own group name, for example `pr-brief-${{ github.event.pull_request.number }}` for this action and something else for the rest. |
| The workflow does not run at all | Check the `on:` block: it needs `pull_request` with the types `opened`, `synchronize`, `reopened`, `ready_for_review`. Check the Actions tab: a run that never started points to the `on:` block or to Actions being disabled for the repository. |
| "GitHub refused the request: the token lacks permission (HTTP 403)" | Add `permissions: { contents: read, pull-requests: write }` to the workflow or job. Check that the repository setting "Workflow permissions" does not block it. Fork PRs always get a read-only token. |
| "api-key is required for provider ..." | The **secret** is missing or empty. Create it under Settings, Secrets and variables, Actions, and make sure the name in `${{ secrets.NAME }}` matches. Secrets are also empty on fork PRs and for Dependabot PRs (these need their own Dependabot secret). |
| Nothing to review | After filtering no reviewable file was left (only lockfiles, images, generated files, ...). The comment says so. Check `ignore` if this surprises you. |

## The provider reports an error

| Message | Fix |
|---------|-----|
| "authentication failed (HTTP 401/403)" | The key is wrong, expired, or not allowed to use this model or region. Create a new one and update the secret. |
| "model or endpoint not found (HTTP 404)" | The model name is wrong, retired, or not enabled for your key. Names change; list the models your key can use in the provider's console or API. For `openai-compatible` and `ollama` also check `base-url`. |
| "rate limit or quota exceeded (HTTP 429)" | Quota or per-minute limit reached (free tiers are small). pr-brief retries twice with short waits, then gives up. Lower `max-input-tokens`, use a cheaper model, or check billing. Re-running the workflow later also works. |
| "... is unavailable (HTTP 500/502/503/504)" | The provider is overloaded or down, often only for a while. Re-run later or pick another model. |
| "the request timed out" | Raise `timeout-seconds`, or use a faster model. Local models on small machines are often slow. |
| "the request was rejected (HTTP 400)" | Usually a bad model name or `max-output-tokens` the model does not accept. Newer OpenAI models can reject `max_tokens`; see the known limits in [providers](providers.md). |
| "the response is not valid JSON" | `base-url` does not point at the API (for example a web page or a login redirect). Redirects are never followed. |
| "Model output is not valid JSON ..." (or a message about the output structure) | The model did not return the expected structure, even after one repair attempt. Try a more capable model. |

## Self-hosted runners with Ollama

Free and private, but the runner must be set up:

1. Install Ollama on the runner machine and pull a model: `ollama pull llama3.2`.
2. Keep it running (a service, not a manual terminal).
3. Use `provider: ollama`, `model: llama3.2` and, if Ollama is not on the default port, a
   `base-url` such as `http://localhost:11434`. Plain `http` is accepted for `localhost` only.
4. Run the job on `runs-on: [self-hosted, ...]`. GitHub-hosted runners cannot reach your Ollama.
5. Raise `timeout-seconds` (for example `180`) for the first request, which loads the model.

Do not run untrusted fork PRs on a self-hosted runner that holds anything of value.

## The diff or pull request is too big

- Files over the budget are chunked; if even that does not fit, some are listed as "Not analyzed"
  in the comment's Run details. Raise `max-input-tokens` if your model allows it.
- Pull requests with more than 200 files are cut off after 200.
- GitHub itself refuses to return the diff of extremely large pull requests; the error then asks you
  to split the PR.

## Other

- **The comment is not updated.** Only comments by `github-actions[bot]` that start with the hidden
  marker are edited, and the whole text is replaced on every update, so manual edits are lost. If
  the comment is deleted, the next run posts a new one.
- **Same result after a change.** The result is cached for identical input. Set `cache: false` to
  force a fresh call.
- **Secrets in the diff.** They are masked before sending; the count is in Run details. Redaction is
  best effort, see [security model](security-model.md).
- **Garbled characters in a local Windows console.** Set `PYTHONUTF8=1`.

Still stuck? Open an issue with the job log (remove anything private). Never paste API keys. For
security problems use [`SECURITY.md`](../SECURITY.md).
