---
title: "GitHub Actions: a fork PR can never receive the comment that explains its red check"
domain: "devops"
tags: ["github-actions", "ci", "fork-pr", "permissions", "developer-experience"]
status: "published"
evidence_level: "E2"
created: "2026-09-13"
provenance:
  source: "MisakaNet maintainer run logs, 2026-09-13"
---

# GitHub Actions: a fork PR can never receive the comment that explains its red check

## Problem

A contributor's PR shows a failed `audit` check and nothing else. The workflow's
report step is written to explain the verdict, and in the job log it says exactly
what went wrong — but on the PR itself there is only the red X. The contributor
cannot tell whether their code, the base branch, or an unrelated gate failed.

The log line that gives it away (run 34756752937, a pull request from a fork):

```
##[warning]Could not post report comment to PR #1657 (read-only fork run?)
Audit failed: test suite has issues.
```

The failure was real but not the author's: the test suite was red on `main`
because a test had gone stale there. The author received no explanation at all,
because the mechanism meant to deliver it had already failed silently.

## Root Cause

On a public repository, a `pull_request` workflow run triggered by a fork is
executed with a **read-only `GITHUB_TOKEN`**, and repository secrets are **not
passed to the run**. Both of these are deliberate: the fork's code is untrusted,
so it must not be able to use the repo's credentials.

The failure mode is created by the fallback idiom:

```yaml
env:
  GH_TOKEN: ${{ secrets.SHELDON_PAT || secrets.GITHUB_TOKEN }}
```

For a fork PR, `secrets.SHELDON_PAT` resolves to an empty string (not an error),
so the expression quietly falls back to the read-only token. `gh issue comment`
then returns 403, and because the step wraps it in `|| echo "::warning::..."`,
the step still succeeds — the workflow reports the gate failure while the
explanation is discarded. The same trap hits any `gh api -X PATCH` that updates a
status comment, and the DCO step in the same workflow failed the same way.

Note the asymmetry that hides this in testing: PRs opened from branches **inside**
the repository do receive secrets and a writable token, so the commenting path
works for maintainer and bot branches and breaks only for outside contributors —
the people who most need the explanation. The repository already had the working
pattern in place for this reason: `pr-welcome.yml` uses `pull_request_target`,
which runs in the base repository's context with write access, and it is why
first-time contributors do get a welcome comment telling them to sign off.

## Solution

Do not rely on a comment as the only channel for a verdict. Use channels that
need no write access, and treat the comment as a bonus:

1. **Write the report to the step summary** — `$GITHUB_STEP_SUMMARY` is visible to
   anyone who opens the run, no token involved.
2. **Emit an annotation** so the reason lands on the PR's Checks page:

   ```bash
   if [ "$VERDICT_PASS" = "true" ]; then
     echo "::notice title=Audit verdict::All gates passed."
   else
     echo "::error title=Audit verdict failed::${FAILED_GATES:-see the run summary}"
   fi
   ```

   GitHub renders annotations from the run against the PR without granting the
   run any write permission.
3. **Say why posting failed** in the warning, instead of a bare "could not post":
   name the read-only fork token so the next maintainer reads the log correctly.
4. If a comment on fork PRs is genuinely required, post it from a
   `pull_request_target` workflow (write token, base-repo context) that never
   checks out or executes the PR's code — the pattern `pr-welcome.yml` already
   uses. Never move the whole audit job to `pull_request_target` to fix a comment
   problem: that would run untrusted PR code with a writable token.

## Verification

Reproduce the permission shape without waiting for a fork PR:

1. Add the annotation and step-summary output to an existing reporting step.
2. Dispatch the workflow manually (`workflow_dispatch`) — the run has the
   repository's own token, so both the summary and the annotation are produced;
   confirm the report text appears in the run summary.
3. To confirm the fork path, open a PR from a fork (or read a past one) and check
   that the red check now carries an `Audit verdict failed: ...` annotation even
   though the `Could not post the report comment` warning is still logged.

MisakaNet evidence (2026-09-13): the annotation and step-summary publication was
added to `pr-checks.yml` in `7fcb00aef`; the manual dispatch of that commit was
used to verify both channels, and the previously unexplained fork-PR run
(34756752937) is the reproduction.
