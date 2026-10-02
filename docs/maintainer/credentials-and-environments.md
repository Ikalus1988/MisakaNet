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
| env `npm-release` | **trusted publishing (OIDC)** — preferred; `NPM_TOKEN` transitional | `misakanet-publish` | branch policy `main` + `v*`, **no reviewer** (unattended, 2026-09-30 — intake #2486 D1). OIDC needs no stored secret at all; see §4.1 |
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
| `release` | `CF_API_TOKEN`, `CF_BUILDS_TOKEN` | branch policy `main` + required reviewer `Ikalus1988` (gates `deploy-worker.yml`) |
| `npm-release` | `NPM_TOKEN` | branch policy `main` + `v*`, no reviewer — an unattended publish must not un-gate worker deploys |
| `automation` | `CF_API_TOKEN` | branch policy `main`, no reviewers |

Two things that table settles without a run:

* **`CF_OBSERVABILITY_TOKEN` does not exist**, even though §4.3 recommends creating it and
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

**One ref that has to be allowed explicitly, not remembered (2026-09-30).** `misakanet-publish.yml`
also runs on a **published release** (`on: release: types: [published]`), and that run's ref is
`refs/tags/vX.Y.Z` — not `main`. A `release` environment restricted to the branch `main` refuses that
job at deploy time, before any step runs, so the symptom is a release with no publish and no log to
read. The environment therefore needs the tag pattern `v*` allowed as well (Settings → Environments →
`release` → deployment branch and tag rules). Two further settings the automatic npm publish depends
on, both repository settings rather than code: for an *unattended* publish `release` must not require
a reviewer (with one configured the run waits for approval, which is a deliberate choice — the human
gate moved from memory to a visible click), and the **`npm-release`** environment (no reviewer, branch policies `main` + `v*`) carries the npm credential so the publish can be unattended without un-gating worker deploys — and since 2026-09-30 that credential is preferably not a secret at all: see §4.1 on trusted publishing.

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

### 4.1 npm authentication — trusted publishing (OIDC) first, `NPM_TOKEN` transitional

**The direction (2026-09-30, intake #2486 D1): publish with npm *trusted publishing* and stop storing a
credential.** The workflow asks for `id-token: write`; GitHub mints an OIDC token; npm CLI (>= 11.5.1 on
Node >= 22.14 — the publish job therefore runs Node 24) exchanges it for a **short-lived** publish
credential and, per [npm's docs](https://docs.npmjs.com/trusted-publishers), "automatically detects OIDC
environments and uses them for authentication **before** falling back to traditional tokens". Provenance
attestations are generated automatically, without `--provenance`.

Why this and not "drop the reviewer from `release`": publishing a package and deploying production code are
different privileges. `release` gates `deploy-worker.yml`, so making it unattended would un-gate the worker
as a side effect; `npm-release` is a second, narrower boundary that holds only the publish credential — and
with OIDC it holds nothing at all.

**One-time configuration on npmjs.com** (cannot be done from this repository):

1. `npmjs.com` → the package (`misakanet`) → *Settings* → **Trusted publisher** → GitHub Actions.
2. Fill in: organisation/user `Ikalus1988`, repository `MisakaNet`, **workflow file name**
   `misakanet-publish.yml`, **environment** `npm-release` (naming the environment binds the trust to this
   job, not to any workflow in the repo), and the **allowed actions** — allow `npm publish` for direct
   publishing; `npm stage publish` is always allowed. Choosing *stage-only* instead is the strongest
   posture: every release would then need a maintainer's 2FA approval on npm before it becomes public.
3. Repeat for the other two packages this repository publishes (`@misaka-net/misakanet-setup`,
   `@misaka-net/fatal-guard`) as their workflows migrate.

**Then retire the secret:**

4. Run one release (or `gh workflow run misakanet-publish.yml -f version=X`) and check the log line
   `OIDC available: npm will authenticate with trusted publishing (no long-lived token).`
5. Only after a successful OIDC publish: delete `NPM_TOKEN` from `npm-release` and remove the
   `NODE_AUTH_TOKEN` passthrough from the workflow. Until then the token is a deliberate fallback, so a
   migration mistake cannot turn into a release that silently does not happen.

**While the token still exists** it expires **2026-11-30** and cannot be renewed forever: npm caps every
granular write token at a 90-day lifetime
([2025-11-05 change](https://github.blog/changelog/2025-11-05-npm-security-update-classic-token-creation-disabled-and-granular-token-changes/)).
To rotate it: *Generate New Token* → Granular Access Token, `read and write` on `misakanet`,
`@misaka-net/fatal-guard`, `@misaka-net/misakanet-setup` → update the secret in the `npm-release`
environment → prove it with a `dry_run` dispatch (the identity step calls `npm whoami` *before* publishing
and fails with a named error when the value is wrong). Expiry date tracked as issue **#2113**, labelled
`keep`. The token's real "rotation" is step 5 above: deleting it.

**Retirement decision (2026-10-01, owner): the secret stays until *every* package has published once
through OIDC — and that condition is checkable, so nobody has to remember it.** `misakanet` has
(2.39.0); the other two are already at their published version, so **their next release is the proof** and
there is nothing to do until then. Provenance/attestations are produced *only* by the trusted-publish
path, which makes them the evidence rather than a guess:

```sh
for p in misakanet @misaka-net/misakanet-setup @misaka-net/fatal-guard; do
  enc=$(python3 -c "import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1],safe=''))" "$p")
  curl -sS "https://registry.npmjs.org/$enc" | python3 -c "
import json,sys
d = json.load(sys.stdin); v = d['dist-tags']['latest']
print(d['name'], v, 'attestations:', bool(d['versions'][v].get('dist', {}).get('attestations')))"
done
```

Delete `NPM_TOKEN` (and the `NODE_AUTH_TOKEN` passthrough) only when all three print `attestations: True`.
Deleting earlier trades a working fallback for a release that can fail with a bare 401, and step 5 above is
the only thing that makes deletion safe.

### 4.2 The onboarding snapshot's GitHub traffic leg is deliberately credential-free (2026-10-01)

`scripts/snapshot_onboarding.py` has three legs: npm downloads, the site's own activity counts, and
GitHub's 14-day clones/views. The third needs the **Administration: read** repository permission, which
`GITHUB_TOKEN` cannot be granted — and the first attempt at a fix suggested a PAT instead. **Decision: it
does not get one, and `"traffic": null` is the intended state**, for two reasons that both point the same
way:

* **Blast radius vs. value.** The only token in this repository that can already read that endpoint is
  `SHELDON_PAT`, which exists to **push to `main` as a user** (§5, `branch-sync-and-ci.md`). Handing a
  push-capable credential to an unattended weekly job — to fetch three integers — is a bad trade; the
  numbers are context for a metric we already concluded is measured at the wrong end of the funnel.
* **Better data already exists.** Every request the worker answers is classified as **`agent` /
  `crawler` / `pageview`** (`/api/activity`, published in the badge's `activity.calls`), which answers
  "how much of this is machines" per request, at the bottom of the funnel, with no new permission.

If someone later wants the clone counts automated, the only acceptable shape is a **fine-grained PAT with
`Administration: read` and nothing else**, in its own environment — never `SHELDON_PAT`, never a classic
token. Until then the snapshot keeps saying so: it warns, it does not claim a `traffic` window it did not
measure, and the workflow passes only `GITHUB_TOKEN`.

### 4.3 `CF_OBSERVABILITY_TOKEN`: the scopes, and that creating it is an ops action (2026-10-02)

§2 has said since 2026-09-24 that this token is "optional", and it has never existed — so
`cf-diagnostics.yml` has been running its read-only Cloudflare Analytics queries with
`secrets.CF_API_TOKEN`, the **deploy-capable** credential. A read-only diagnostic that holds a deploy
token is the gap this section closes, and issue #2521 (the "Network activity" trend) widens the same
read path rather than adding a second one.

**What to create — an account-scoped Cloudflare API token.** The set is wider than two
permissions, because `cf-diagnostics.yml` is wider than the Analytics query. Measured against the
workflow's own request list rather than its name:

| Permission | Endpoint that needs it |
|---|---|
| Account · **Workers Observability** · Read | `wrangler tail` / the worker-log half of `cf-diagnostics` |
| Account · **Account Analytics** · Read | the `httpRequestsAdaptiveGroups` GraphQL query (status codes by route) |
| Account · **Workers KV Storage** · Read | `GET /accounts/{acct}/storage/kv/namespaces` |
| Account · **Workers Scripts** · Read | `GET /accounts/{acct}/workers/scripts` and `…/scripts/{name}/settings` |
| Zone · **Workers Routes** · Read | `GET /zones/{zone}/workers/routes` |

**Still nothing write-capable**: no `Workers Scripts: Edit`, no `Workers KV Storage: Edit`, no
`D1: Write`, no `Zone: Edit`. And `Workers Builds` is not here at all — that API has its own
user-scoped credential (§4.4) and rejects account-scoped tokens outright.

Two earlier drafts of this table said "exactly two permissions … nothing else". That was wrong in
a way that would have 403'd four endpoints the moment the `|| secrets.CF_API_TOKEN` fallback is
removed, so the list above is taken from the workflow source (`cf-diagnostics.yml` `get(...)`
calls), not from what the chart happens to need.

**Where it goes:** GitHub → Settings → Environments → `release` → Environment secrets →
`CF_OBSERVABILITY_TOKEN`. `cf-diagnostics.yml` already prefers it (`secrets.CF_OBSERVABILITY_TOKEN ||
secrets.CF_API_TOKEN`), so installing it is the whole change — no workflow edit, no redeploy.

**No value is written down here or anywhere in this repository.** Creating the token is an operator's
action in the Cloudflare dashboard; this document records which scopes it needs and nothing more. A
token pasted into a document is the incident §6 exists for.

**How to prove it works, since no run can name the token it used:** GitHub never reveals a secret's
value and Cloudflare token scopes are not enumerable from here, so a green `cf-diagnostics` run proves
only that *some* credential answered. The proof that the **narrow** one is what answered is a run with
the fallback temporarily out of the chain — set the workflow's `CLOUDFLARE_API_TOKEN` line to
`${{ secrets.CF_OBSERVABILITY_TOKEN }}` alone on a dispatch branch, run *CF diagnostics*, and look for
`== by status ==` with real counts in the first step. A 403 there names the missing permission, which
is the finding rather than a failure of the run.


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
