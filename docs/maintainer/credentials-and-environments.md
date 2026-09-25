# Credentials, and the environments that hold them

Which secret lives where, who can read it, and when it expires — written down so that it is not
remembered. Snapshot re-verified against the GitHub API on **2026-09-24** (§2 lists what is actually
installed, which is not the same as what this document recommends); if you change an environment, change
this table in the same PR.

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
| env `release` | `CF_BUILDS_TOKEN` (optional) | `cf-diagnostics` | branch policy `main` + required reviewer — **read-only and user-scoped**: `Workers Builds Configuration` (read), no deploy. Created 2026-09-24, see §4.4 |
| repo level | `AI_GATEWAY_TOKEN` | `benchmark-workers-ai` | none |
| repo level | `OPENAI_KEY` | `pr-agent-review` | none |
| repo level | `CLOUDFLARE_API_TOKEN` | **nothing** | none — deleted 2026-09-20, see §6 |

Environment secrets shadow repository secrets **by name**: a job in `automation` that reads
`secrets.CF_API_TOKEN` gets `automation`'s value even if a repository secret of that name exists. So
one credential must have exactly one name, or the environment is decoration.

**Measured 2026-09-24** (`GET /repos/…/environments/{release,automation}/secrets`, which the maintainer
token can read):

| environment | secrets actually installed | protection rules |
|---|---|---|
| `release` | `CF_API_TOKEN`, `CF_BUILDS_TOKEN`, `NPM_TOKEN` | branch policy `main` + required reviewer `Ikalus1988` |
| `automation` | `CF_API_TOKEN` | branch policy `main`, no reviewers |

Two things that table settles without a run:

* **`CF_OBSERVABILITY_TOKEN` does not exist**, even though §4.2 recommends creating it and
  `cf-diagnostics` prefers it. The workflow's `|| secrets.CF_API_TOKEN` fallback is what actually runs, so
  the deploy token is the one carrying Account Analytics, Workers KV Storage and Workers Scripts reads on
  the diagnostics path. The recommendation stands (narrower is better); the entry above was aspirational
  until now, which is what "optional" means and why the fallback exists.
* **`CF_BUILDS_TOKEN` exists** (created 2026-09-24, §4.4). Its permissions cannot be read back — GitHub
  never reveals a secret and a Cloudflare token's scopes are not enumerable from here — so the only proof
  is a run that gets past the tag lookup and prints `== log for build …`.

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
>
> **…and it breaks one thing GitHub cannot show you.** The same 2026-09-23 roll also invalidated the
> Worker Builds **build token** in the Cloudflare panel, which is why the site stopped deploying for a
> day — see §4.5, which is the half of this warning that cost the most.

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

### 4.4 Reading the *site build* logs — the one API that refuses an account-scoped token

`Workers Builds: misakanet-web` is Cloudflare's Git integration building `docs/` into misakanet.org. It is
not one of the three checks the ruleset requires, so it can be red on every commit while `main` keeps
merging — which is what happened between 2026-09-23 and this writing (#2136). Its check-run carries no
summary, no annotation and no log, and this repository contains **no build configuration at all**
(`package.json` has no `build` script, `wrangler.jsonc` names no build command — the command lives only in
the Cloudflare panel).

So the build's cause exists in exactly one place, and reading it needs a credential the others do not cover:

| API | permission it needs |
|---|---|
| `GET /builds/workers/{external_script_id}/triggers` and `…/builds` (the build command, and which builds are red) | Account → **Workers Builds Configuration** → Read |
| `GET /builds/builds/{build_uuid}/logs` (the error the build died on) | same |
| `GET /workers/scripts` (the worker **tag** — every Builds endpoint wants `external_script_id`, never the name) | Account → **Workers Scripts** → Read |

Two things are easy to get wrong here, and both were:

1. **This API rejects account-scoped tokens.** The docs are explicit: account-scoped tokens return
   `Invalid token`. `CF_BUILDS_TOKEN` must therefore be created at
   <https://dash.cloudflare.com/profile/api-tokens> as a **user-scoped** token. This is the one credential
   in this repository that cannot be folded into the account-scoped deploy token even in principle.
2. **The permission has two names in Cloudflare's own documentation.** The guide calls it *Workers Builds
   Configuration*; the API reference pages for the two endpoints call it `Workers CI Read` / `Workers CI
   Write`. They are the same permission group — do not go looking for a third one. Read is enough to read a
   log; Write is only for triggering a build or editing a trigger.

The workflow treats the token as optional, exactly like `CF_OBSERVABILITY_TOKEN`: absent, it says what is
missing and the rest of the run still happens. Two deliberate softenings in `cf-diagnostics.yml`:

* the **tag** lookup falls back to `CLOUDFLARE_API_TOKEN`, because `/workers/scripts` is a *Workers Scripts*
  read and a perfectly good Builds token may not carry it — without that fallback, a token with only the
  Builds scope would still cost a dispatch;
* every failure is printed with the API's own error text and never fails the run, because a 403 body names
  the missing permission, and that is the answer to "why is this empty".

To prove the value is installed (GitHub never reveals a secret, so a run is the only evidence):
Actions → *CF diagnostics* → Run workflow, and look for `== worker tag …` followed by
`== log for build …`. The step's behaviour is pinned by `tests/test_cf_diagnostics_builds_step.py`,
which runs the workflow's own Python against a stub account — including the two ways the step can lie:
reading the newest build instead of the newest **failure**, and reading the first page of a
`truncated` log whose error is on the last one.

### 4.5 Rolling an API token also breaks the site build — and that is how it broke for a day

The first thing the step above found (#2136) is a credential that is **not** in this document, because
it is not in GitHub at all: the Workers Builds **build token**, selected in the Cloudflare panel
(Worker → Settings → Builds → API token, documented as `build_token_uuid`). Measured 2026-09-24, the
failing build's entire log was three lines:

```
Initializing build environment...
Success: Finished initializing build environment
Failed: The build token selected for this build has been deleted or rolled and cannot be used for
this build. Please update your build token in the Worker Builds settings and retry the build.
```

What makes this worth a section rather than a line: **the build token is derived from an API token, so
rolling the API token invalidates it too**, and nothing anywhere says so. On 2026-09-23 the deploy
token was rolled — the event §4.2 already documents as `9109 Invalid access token`. The GitHub secret
was updated (§4.2's warning), which is why `deploy-worker` works; the build token in the panel was
not, which is why every site build since **2026-09-23T17:40Z** died before building anything. The live
site stayed byte-identical to `7fcebbf2a` — the commit *before* the first failure — for a day.

So the rotation procedure in §4 and §4.2 gains a step, and it applies to **every** Cloudflare token
rotation, not just the deploy one:

1. roll the token and update the GitHub secret, as §4.2 says;
2. **update the build token** in Worker → `misakanet-web` → Settings → Builds → API token, and re-run
   the build from the dashboard;
3. confirm the site actually moved, by fetching something that changed in the last commit — a green
   `deploy-worker` run says nothing about the site, and the site's own check-run is not a required
   check, so it will not stop a merge.

`.github/workflows/workers-builds-watch.yml` now opens an issue when that check goes red on `main`
(label `site-build-red`), so the second half of a rotation fails loudly instead of silently. It does
**not** make the check required: a required check that is red blocks every merge, including the merge
that fixes it.

The trigger configuration worth knowing, read from the API on 2026-09-24 (it exists nowhere in this
repository): two triggers, `Deploy default branch` (`branches=['main']`, `npx wrangler deploy`) and
`Deploy non-production branches` (`branches=['*']`, `npx wrangler versions upload`), both with an
**empty build command** and no build-time environment variables. So the site has no build step at all
— the deploy is `npx wrangler deploy` against the root `wrangler.jsonc` (`assets.directory = docs`),
which is reproducible from this repository.

#### 4.5.1 What the build token needs, exactly

Asked and answered on 2026-09-24, from Cloudflare's own
[Workers Builds configuration docs](https://developers.cloudflare.com/workers/ci-cd/builds/configuration/)
rather than from memory, because a wrong scope here is another day of a dead site:

* it must be a **user token**. Account-owned tokens are *not* supported by Workers Builds ("currently,
  only user tokens are supported") — the same constraint §4.4 hit from the other direction, where the
  Builds *API* answers an account-scoped token with `Invalid token`;
* choosing **Create new token** in the panel's build settings makes Cloudflare create one with exactly
  these permissions:

| scope | permission | why the deploy needs it |
|---|---|---|
| Account | **Account Settings** — Read | resolving the account the Worker belongs to |
| Account | **Workers Scripts** — Edit | the upload itself |
| Account | **Workers KV Storage** — Edit | the asset store behind `assets.directory` |
| Account | **Workers R2 Storage** — Edit | same, for the newer assets backend |
| Zone | **Workers Routes** — Edit (all zones on the account) | keeping the Worker's route/domain attachment |
| User | **User Details** — Read | the token is a user token, so it identifies a user |
| User | **Memberships** — Read | which accounts that user can act on |

Cloudflare's `Edit Cloudflare Workers` template is the same list plus `Workers Tail` — either is
sufficient; **do not hand-trim** the list. A missing permission does not fail at build start, it fails
at the end of a deploy nobody is watching, which is the shape of failure this section exists to stop.

**Prefer "Create new token" over picking an existing token.** The panel lets you re-use a token you
already own, and that is exactly how the site died: the build token was one the owner also rotated for
GitHub Actions. A token created *for* Builds is dedicated, so rolling the deploy token no longer takes
the site with it — which is the whole failure mode described above, removed by construction rather than
by remembering.

**`CF_BUILDS_TOKEN` (§4.4) is a different credential and must stay one.** It is read-only
(`Workers Builds Configuration` + `Workers Scripts` reads) and lives in GitHub's `release` environment;
the build token is deploy-capable and lives only in the Cloudflare panel. Merging them would put a
deploy-capable credential in GitHub, where a workflow can print it.

After changing it: re-run the build from the dashboard. `Workers Builds: misakanet-web` on the new
commit should report success **with a `Version ID:` line** — its absence is how a build that died
before producing a version looks, which is what every failing check-run above had. The watcher
(§4.5) then comments once on the tracking issue, because its recorded state is `red`.

## 5. What is deliberately still repository-level

`SHELDON_PAT` is the token that lets the branch sync push to `main` as a user rather than as
`github-actions[bot]` (a bot-authenticated push does not trigger workflows — see
`docs/maintainer/branch-sync-and-ci.md`). It is used non-interactively by scheduled and event-driven
workflows, so it cannot move into an environment with reviewers. `AI_GATEWAY_TOKEN` and `OPENAI_KEY`
are model-provider keys used by workflows that also must run unattended. Moving any of them would break
the automation that needs them; the mitigation is that they cannot deploy anything.

## 6. When a credential has been published (2026-09-25, #1982)

A token in a **published document** is a different incident from a token in a secret store, and it needs
a different reflex. On 2026-09-25 a docs-only PR was one merge away from landing two live-looking node
tokens: both smoke reports quoted `"Authorization": "Bearer mcp_…"` verbatim.

**The first thing to understand is that editing the file does not fix it.** A fork PR's diff is public
the moment it is opened, so the value is already out. Removing the line (or closing the PR without
merging) is necessary and insufficient — the string must be treated as burned.

What can actually be done:

| | |
|---|---|
| Redact the document | replace with `Bearer <redacted>` or `$MISAKANET_TOKEN`, so main is not a copy of a live credential |
| Re-issue the node | re-register with the same `client_id` to get a fresh node and token; that is the only self-service lever, and it is the *right* one for the reporter |
| Kill it now | delete the stored keys — `mcp_token:<token>` and `node:MisakaNNNN` in D1/KV (`workers/register-proxy-sw.js:2517-2545`, 30-day TTL). **There is no revocation endpoint**, so this is a manual ops action rather than an API call |
| Assume the write path | until expiry, whoever holds the string can call the Bearer-only tools (`misakanet_write_lesson`, `misakanet_preflight`) as that node |
| **Invalidate the reason it merged** | if an auto-merge label or auto-merge was enabled on the PR, turn it off while the tokens are in the branch — otherwise the next passing check lands them |

**Why nothing caught it**, because the reasons are worth more than the incident: the auditor's
`Secret Scan` step read `workers/**` only *and* was gated on `scope == 'full'`, so a docs-only PR never
ran it; HOL Guard covers `lessons/`, `scripts/` and `workers/`, not `docs/`; and the audit's test suite
was aborting during collection on the Python version that job pinned (§4.5's sibling bug, fixed the same
day). Four overlapping scanners, none of them looking at the file. `scripts/check_published_secrets.py`
now scans `docs/**` and `lessons/**` prose **for every scope**, with a rule that separates a token from
the tool names and placeholders this repository is full of (`MIN_DISTINCT` — the measurement is in that
file's docstring).

## 7. Known gaps

* The repository-level `CLOUDFLARE_API_TOKEN` was a leftover from the migration: nothing read it, and
  the name was the *wrong* name (the test in §1 requires the Cloudflare credential to be referenced as
  `CF_API_TOKEN`). A dead deploy-capable secret is worse than no secret, because a future workflow can
  reference it and silently go around the environment. Deleted 2026-09-20.
* `.github/workflows/stale.yml` exempts a `keep` label that did not exist until 2026-09-20, so the
  exemption was decorative — the four other exempt labels do exist, but a dated reminder would never
  carry them. The label now exists.
