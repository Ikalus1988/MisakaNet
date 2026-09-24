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
| repo level | `SHELDON_PAT` | `auto-sync-prs`, `pr-checks`, `pr-shape-guard`, `release-please`, `auto-merge-docs` | none (see §5) |
| env `release` | `CF_OBSERVABILITY_TOKEN` (optional) | `cf-diagnostics` | branch policy `main` + required reviewer — **read-only**: `Workers Observability: Read` + `Account Analytics: Read`, no `Workers Scripts: Edit` |
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

### 4.1 `NPM_TOKEN` — expires **2026-11-30**, and it cannot be renewed forever

npm no longer issues tokens that outlive the release train. Since the
[2025-11-05 security change](https://github.blog/changelog/2025-11-05-npm-security-update-classic-token-creation-disabled-and-granular-token-changes/),
classic tokens are gone (revoked 2025-11-19) and **every granular token with write permission is
capped at a 90-day lifetime** — the tokens this repository publishes with are exactly that kind. The
current one expires **2026-11-30** (reported by the owner from
`npmjs.com/settings/~/tokens`), which means a rotation whose only failure mode is a red release job
is already scheduled, by npm, about two months out.

To rotate it:

1. `npmjs.com/settings/~/tokens` → *Generate New Token* → **Granular Access Token**, with
   `read and write` on the three packages this repository publishes: `misakanet`,
   `@misaka-net/fatal-guard`, `@misaka-net/misakanet-setup`. Keep the lifetime at the 90-day maximum.
2. GitHub → Settings → Environments → `release` → update `NPM_TOKEN`.
3. **Prove it with a run**: the publish workflows call `npm whoami` *before* publishing and fail with
   `npm rejected NPM_TOKEN (npm whoami failed)` when the value is wrong
   (`misakanet-publish.yml:105`), so a dispatch with `dry_run` is enough — the token is checked and
   nothing is published.
4. Update the date here and in the tracking issue — **#2113**, labelled `keep` for the same
   reason #1886 is.

**The rotation should be the last one.** [Trusted publishing](https://docs.npmjs.com/trusted-publishers/)
removes the credential instead of renewing it: the package is configured with a *Trusted Publisher*
on npmjs.com (repository + workflow filename), the workflow asks for `permissions: id-token: write`,
and `npm publish` exchanges the OIDC token for a short-lived publish token — no `NPM_TOKEN` at all.
Requirements are npm CLI ≥ 11.5.1 and Node ≥ 22.14.0, both satisfied by the `setup-node` pins in the
three publish workflows. The npm side is a per-package setting (up to 10 per package), so it is an
owner action in the npm UI; the workflow side is a three-line change.

### 4.2 Reading worker logs, and why that is a *separate* token

`cf-diagnostics.yml` queries several Cloudflare APIs, and none is covered by the deploy token's
permissions:

| API | permission it needs |
|---|---|
| `GET /graphql` `httpRequestsAdaptiveGroups` (status codes by route) | Account → **Account Analytics** → Read |
| `POST /accounts/{id}/workers/observability/telemetry/query` (worker logs) | Account → **Workers Observability** → Read |
| `GET /zones?name=…` + `GET /zones/{id}/workers/routes` (who owns which route) | Zone → **Zone** → Read + Zone → **Workers Routes** → Read |
| `GET /accounts/{id}/storage/kv/namespaces` (which namespaces exist, and which nothing binds) | Account → **Workers KV Storage** → Read |

The `wrangler d1 info` / `d1 time-travel info` steps need the same scope the D1 steps already use
(Account → **D1** → Read), and the zone/KV steps **degrade with the error text** rather than failing
the run — a 403 body names the missing permission, which is itself the answer to "why is this empty".

Measured 2026-09-23: with only the deploy token's scopes, the first returned
`filter: datetime_geq: not an iso8601 time` (a bug in the query, since fixed) and the second returned
`HTTP 403 Authentication error`.

Two ways to grant it, and the order below is the one this repository's rule prefers (*one credential
per purpose, narrowest scope*):

1. **Create a separate read-only token** with exactly the two permissions above and store it in the
   `release` environment as `CF_OBSERVABILITY_TOKEN`. The workflow prefers it and falls back to
   `CF_API_TOKEN`, so nothing breaks until it exists.
2. **Add the two permissions to the existing deploy token** — for a *permission* edit no GitHub change
   is needed, because the token's value is unchanged. It is faster and it widens what a deployment
   credential can do.

> ⚠️ **If Cloudflare shows you a new token value, update the GitHub secret in the same sitting.** Editing
> permissions on an existing token keeps its value; creating or rolling one does not, and the old value
> is then invalid rather than merely under-privileged. Measured 2026-09-23: after a token update the
> worker deploy failed with
>
> ```
> ✘ [ERROR] A request to the Cloudflare API (/accounts) failed.
>   Invalid access token [code: 9109]
> ```
>
> **`9109` means the value is not a token at all** — not a missing permission (that reads
> `Authentication error` / code `10000`, which is what the telemetry endpoint returned before its
> permission existed). Every job that reads `release`'s `CF_API_TOKEN` breaks together when this happens:
> `deploy-worker`, `apply-d1-schema`, `d1-bootstrap`, `d1-counters-report`, `intake-pipeline-test`,
> `cf-diagnostics`. The `automation` environment holds its **own** `CF_API_TOKEN` (D1:Edit only), so
> `sync-d1` and `sync-question-answers` keep working — which is the two-credential design earning its
> keep: a rotation on one path did not stop the scheduled corpus sync.

A third option costs nothing at all and is enough for a one-off: the dashboard's
Workers & Pages → `misakanet-register-proxy` → Observability → Logs view, or
`npx wrangler tail misakanet-register-proxy` locally.

### 4.3 What was proven, and what can only be assumed

The token's *sufficiency* was verified end-to-end on 2026-09-20 rather than assumed — a narrower token
plausibly could have been too narrow, and `wrangler` sometimes needs account-level reads that the D1
permission group does not obviously grant. Both jobs were dispatched on `main` and neither waited for an
approval (`pending_deployments` empty), so `automation` really is reviewer-free:

| run | result | evidence from the log |
|---|---|---|
| [35461711546](https://github.com/Ikalus1988/MisakaNet/actions/runs/35461711546) `sync-d1` | success | self-heal DB check, schema `21 queries`, upsert `805 queries / 1581 rows read / 2809 rows written`, FTS rebuilt for 401 lessons, count `401 rows read` |
| [35461713086](https://github.com/Ikalus1988/MisakaNet/actions/runs/35461713086) `sync-question-answers` | success | `open question issues: 2, closed: 7`, no permission error |

The token value itself is still unverifiable from here, and always will be: GitHub never reveals a secret,
so a green run is the only proof that the right value is installed. That is why step 3 above exists.

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
