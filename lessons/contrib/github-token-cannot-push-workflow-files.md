---
title: 'GITHUB_TOKEN cannot push changes to .github/workflows/** — your bot job will fail at push time'
domain: devops
tags:
  - github-actions
  - permissions
  - bot-commits
  - ci
  - idempotency
status: published
created: '2026-09-12'
updated: '2026-09-12'
source: token-workflows-permission-push-rejected-2026-09-12
evidence_level: E1

provenance:
  source: "external"
  contributor: "Ikalus1988"
  merged_at: "2026-09-12"
  evidence: "post-publication"
---

# GITHUB_TOKEN cannot push changes to .github/workflows/** — your bot job will fail at push time

## Problem

A daily "keep the docs in sync" job had been green for weeks. The first day its output actually
changed, the run failed at the very last step:

```text
! [remote rejected]   main -> main (refusing to allow a GitHub App to create or update workflow
  `.github/workflows/pr-thank-you.yml` without `workflows` permission)
error: failed to push some refs to 'https://github.com/owner/repo'
```

Nothing in the job's own logic was wrong: it regenerated its artifacts, committed them, and pushed.
GitHub rejected the push because **one file in the commit was a workflow file**.

## Root Cause

A syncer had a registry of "places that quote the number it maintains", and one entry pointed at a
count written *inside* `.github/workflows/pr-thank-you.yml` (a bot comment: "part of X's 298+
lessons"). GitHub restricts writes under `.github/workflows/**` to tokens holding the `workflows`
permission. `GITHUB_TOKEN` — the default token of a workflow run — never has it, by design: otherwise
any workflow edit could grant itself more privileges.

The failure is invisible until the day the value changes:

* the job was green every day the number stayed the same (nothing to commit → nothing to push);
* the first real change made the commit touch `pr-thank-you.yml`, so the push was rejected **and the
  entire regeneration was thrown away** (the commit never left the runner);
* the rejection names only *one* file — if you scan the log too quickly you blame that workflow
  rather than the syncer that keeps writing to it.

`.github/ISSUE_TEMPLATE/**`, `.github/PULL_REQUEST_TEMPLATE.md`, `README.md` and anything under
`docs/` are all fine. Only `.github/workflows/**` is gated.

## Solution

**Never let a bot commit be the thing that keeps a workflow file up to date.** Move the value out of
the workflow, or read it at runtime:

```yaml
# The count used to be hardcoded here, which meant the daily "refresh counts" job
# could never push its own commit. Read the canonical file at runtime instead.
permissions:
  contents: read     # added: the read below needs it (the job otherwise grants none)
  issues: write
steps:
  - uses: actions/github-script@v9
    with:
      script: |
        let lessons = "";
        try {
          const file = await github.rest.repos.getContent({
            owner: context.repo.owner,
            repo: context.repo.repo,
            path: "docs/_lessons_count.txt",
            ref: context.payload.repository.default_branch,
          });
          const count = Buffer.from(file.data.content, "base64").toString("utf8").trim();
          if (/^\d+$/.test(count)) lessons = " (now " + count + " lessons)";
        } catch (e) {
          lessons = "";   // decorative — never fail the comment over it
        }
```

If the value genuinely must be *written* into a workflow file by automation, that job needs a PAT or
GitHub App token with the `workflows` permission (and that is a security decision, not a default).

While fixing this, make the bot's push resilient, because `main` moves under long-lived jobs:

```bash
git add -A
git commit -m "chore: auto-update generated artifacts"
# A rejected push throws away the whole regeneration. Retry through a rebase once,
# but let a real conflict fail loudly — a `|| true` here hides a detached HEAD.
git push || { git pull --rebase origin main && git push; }
```

Add `concurrency: {group: <job>, cancel-in-progress: false}` so two runs cannot race each other, and
**run the job on demand** (`workflow_dispatch`) after changing it: a scheduled-only job gives you no
signal until the next cron tick.

## Verification

- Dispatch the job and read the **step-level** result, not just the workflow conclusion — the failure
  is in the last step ("Commit and push"), and the job may not have run for days.
- Inspect what the push actually contained: `git status --porcelain` before committing tells you which
  files the job touches. Any `.github/workflows/**` in that list is this bug.
- After the fix, confirm the value in the workflow still renders correctly (here: the PR comment shows
  the count) — the failure mode of the fix is a silently missing number, which try/catch swallows by
  design.

## Detection Heuristics

- A syncer/registry/bot that writes into `.github/workflows/**` is a time bomb: it stays green as long
  as the value does not change, then fails exactly when it finally works.
- `refusing to allow a GitHub App to create or update workflow` = permission, not syntax. Do not go
  edit the workflow it names; go find who is committing it.
- Repeated values in generated commit lists are the tell: if the same fact lives in a workflow file,
  you cannot keep it "single source of truth" from a bot. Prefer reading it at runtime.
- Any two-statement shell idiom like `cmd || true` around `git push`/`git rebase` hides exactly this
  class of state corruption; make failures loud.
