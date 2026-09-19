# Credentials, and the environments that hold them

Which secret lives where, who can read it, and when it expires — written down so that it is not
remembered. Snapshot verified against the GitHub API on **2026-09-20**; if you change an environment,
change this table in the same PR.

## 1. The rule

**No deployable credential is a repository-level secret.** A repository secret is readable by *any*
workflow run on *any* branch, so anyone who can push a branch can print it. An environment secret is
readable only by jobs that declare that environment, and only subject to the environment's protection
rules (branch policy, required reviewers).

This is enforced, not just documented: `tests/test_secret_scoping.py` fails when a job reads a guarded
credential without declaring a known environment.

## 2. Where things are

| Where | Secret | Read by | Protection |
|---|---|---|---|
| env `release` | `CF_API_TOKEN` (deploy-capable) | `apply-d1-schema`, `d1-bootstrap`, `d1-counters-report`, `deploy-worker`, `intake-pipeline-test` | branch policy `main` + required reviewer |
| env `release` | `NPM_TOKEN` | `misakanet-publish`, `misakanet-setup-publish`, `fatal-guard-publish` | branch policy `main` + required reviewer |
| env `automation` | `CF_API_TOKEN` = `misakanet-automation-d1`, **D1:Edit only** | `sync-d1`, `sync-question-answers` | branch policy `main`, **no reviewers** |
| repo level | `SHELDON_PAT` | `auto-sync-prs`, `pr-checks`, `pr-shape-guard`, `release-please` | none (see §5) |
| repo level | `AI_GATEWAY_TOKEN` | `benchmark-workers-ai` | none |
| repo level | `OPENAI_KEY` | `pr-agent-review` | none |
| repo level | `CLOUDFLARE_API_TOKEN` | **nothing** | none — deleted 2026-09-20, see §6 |

Environment secrets shadow repository secrets **by name**: a job in `automation` that reads
`secrets.CF_API_TOKEN` gets `automation`'s value even if a repository secret of that name exists. So
one credential must have exactly one name, or the environment is decoration.

## 3. Why two environments, not one

`release` is for things a person starts and a person approves: publishing a version, deploying the
worker. A required reviewer there costs nothing — the run was going to wait for a human anyway.

A cron is the opposite case. An approval gate on a scheduled job does not make it safer; it makes it
stop. So `automation` exists with **no reviewers**, and the safety comes from somewhere else: the
credential inside it can only do one small thing. The token there is scoped to **D1:Edit on the
misakanet account** — it cannot deploy a worker, cannot read KV, cannot touch DNS. If it leaks, the
blast radius is "someone can read and write lesson rows", not "someone can replace the code served at
misakanet.org".

Both environments are branch-restricted to `main`. That is not a substitute for review — a merged
change on `main` can still reach these secrets. It only means a *feature branch* cannot.

## 4. Rotation

`misakanet-automation-d1` was created 2026-09-19 with a **TTL ending 2027-03-01**. To rotate:

1. Cloudflare dashboard → My Profile → API Tokens → create a custom token: Account / **D1** / **Edit**,
   account resource = misakanet. Nothing else.
2. GitHub → Settings → Environments → `automation` → update `CF_API_TOKEN`.
3. **Prove it with a run**, because GitHub never reveals a secret's value — a green run is the only
   evidence that the right value is installed: `gh workflow run sync-d1.yml` (or Actions →
   *Sync Lessons to D1* → Run workflow) and check that the upsert step succeeded.
4. Update the expiry date in this file and in the note at the top of `sync-d1.yml` /
   `sync-question-answers.yml`.

The expiry is also tracked as issue **#1886**, labelled `keep` so the stale bot leaves it alone, because
a date in a document is easy to miss.

## 5. What is deliberately still repository-level

`SHELDON_PAT` is the token that lets the branch sync push to `main` as a user rather than as
`github-actions[bot]` (a bot-authenticated push does not trigger workflows — see
`docs/maintainer/branch-sync-and-ci.md`). It is used non-interactively by scheduled and event-driven
workflows, so it cannot move into an environment with reviewers. `AI_GATEWAY_TOKEN` and `OPENAI_KEY`
are model-provider keys used by workflows that also must run unattended. Moving any of them would break
the automation that needs them; the mitigation is that they cannot deploy anything.

## 6. Known gaps

* The repository-level `CLOUDFLARE_API_TOKEN` was a leftover from the migration: nothing read it, and
  the name was the *wrong* name (the test in §1 requires the Cloudflare credential to be referenced as
  `CF_API_TOKEN`). A dead deploy-capable secret is worse than no secret, because a future workflow can
  reference it and silently go around the environment. Deleted 2026-09-20.
* `.github/workflows/stale.yml` exempts a `keep` label that did not exist until 2026-09-20, so the
  exemption was decorative — the four other exempt labels do exist, but a dated reminder would never
  carry them. The label now exists.
