# CI Gates: Hard vs Advisory

> This document defines which CI checks are **hard gates** (must pass to merge) vs **advisory/external** (informational, won't block merge).

## Hard Gates (must pass)

The required set is defined by the branch ruleset **`main: the deterministic gates`** (id `23826057`,
`target: branch`, `enforcement: active`, `bypass_actors: []`). Read it back with:

```bash
curl -sS -H "Authorization: Bearer $TOKEN" \
  https://api.github.com/repos/Ikalus1988/MisakaNet/rulesets/23826057 \
  | python3 -c "import json,sys; [print(c['context']) for r in json.load(sys.stdin)['rules'] \
      if r['type']=='required_status_checks' for c in r['parameters']['required_status_checks']]"
```

Measured that way on 2026-09-29, **four** checks block a merge:

| Check (context as GitHub reports it) | Workflow | What it validates |
|---|---|---|
| **DCO / Signed-off-by** | `dco-check.yml` | Every commit carries `Signed-off-by:` |
| **test (ubuntu-latest, 3.11)** | `ci-cross-platform.yml` | The pytest suite on one leg of a 9-leg matrix — the other eight legs are *not* required |
| **gate** | `lesson-gate.yml` | The lesson gate (structure, quality, injection). It deliberately has **no `paths:` filter**, because a required check that sometimes does not run blocks every PR that does not trigger it (#1920) |
| **audit** | `pr-checks.yml` | The audit verdict: DCO audit, secret scan (`scripts/check_worker_secrets.py`), dependency audit, and a `pytest --cov-fail-under=20` run. This is the job that turns a test failure into a blocked merge |

Two notes on **what those commands actually measure** (both fixed 2026-10-02 after an audit found the
gates naming scope they did not have):

* **Coverage measures `misakanet/` only — accepted technical debt.** The command is
  `--cov=misakanet`; `scripts/` is **not** in the measured set. It used to be passed as
  `--cov=scripts` *and* omitted via `[tool.coverage.run] omit = ["scripts/*"]`, so it contributed
  0 lines to a TOTAL that therefore only ever described `misakanet/` (9,109 LOC — about 17 % of the
  54,527 LOC of non-test Python). Measuring `scripts/` properly is a separate investment decision;
  until then the debt is recorded here and in `pyproject.toml`, and the threshold is deliberately
  left alone.
* **The worker suite is `node --test 'workers/**/*.test.mjs'` — 66 files, not 65.** The unquoted
  `workers/*.test.mjs` did not reach `workers/email-register/email-utils.test.mjs` (the nested
  email worker's test, shipped by `make deploy-email`), so that file ran in no workflow at all. The
  quotes matter: unquoted, the shell expands the glob to the nested files only.

Three notes that have each cost someone an afternoon:

* **"Required" is about the *context name*.** Only `test (ubuntu-latest, 3.11)` is required out of the nine
  `test (…)` legs, so a red `windows-latest` or `macos-latest` leg **does not block a merge** — it merges
  green-looking and shows up afterwards as "that PR broke something". Read the leg you changed.
* **`audit` runs pytest too** (with a coverage floor), so the suite *is* gated even though the
  `Run Test Suite` step inside `pr-checks.yml` is `continue-on-error`.
* **The node suite is not required at all.** `node --test 'workers/**/*.test.mjs'` (~570 tests across all
  66 `.test.mjs` files, the only automated
  verification of `workers/register-proxy-sw.js` — i.e. of the MCP endpoint, search and the public API) runs in
  `mcp-stress.yml`, which is not in the required set. Its trigger paths were also a hand-written file list
  until 2026-09-29, so most of its test files did not even run on the PRs that changed them. Until it is
  required, a red worker test merges; treat its check-run as part of review.

## Soft Gates (advisory, won't block)

These report but cannot stop a merge. Some are advisory by design; two are advisory by accident, which is
worth knowing before treating a green page as coverage.

| Check | Workflow | Why it is advisory |
|---|---|---|
| **the other eight `test (…)` legs** | `ci-cross-platform.yml` | Only `ubuntu-latest, 3.11` is in the ruleset — the windows/macos legs exist to catch platform drift and merge red (measured twice on 2026-09-28 alone) |
| **MCP Endpoint Stress Tests** | `mcp-stress.yml` | The worker suite, not in the required set — see the note above |
| **CodeQL (python / javascript-typescript)** | GitHub default | Security queries; findings do not block |
| **Agent Quality Score / Validate Lesson Schema** | `pr-checks.yml` | `continue-on-error: true` |
| **pr-agent / pr-genius** | external | Review helpers |
| **Workers Builds: misakanet-web** | Cloudflare bot | The site build; external, and noisy on bot PRs |

## External (not gated)

These are informational only and never block merge.

| Check | Source | Notes |
|-------|--------|-------|
| **Cloudflare Workers** | `cloudflare-workers-and-pages[bot]` | Bot-generated, ignores project needs |
| **Opire bot** | `opirebot[bot]` | Bounty tracking, not code review |
| **CodeRabbit / Devin** | External bots | Review suggestions, not blockers |

## Auto-Merge Gate

The `Auto-Merge Gate` step in `pr-checks.yml` checks `success()` — meaning ALL steps in the audit job must pass. If an advisory step fails (like `continue-on-error: true` steps), the gate still passes because those steps report `success` even on failure.

However, if an **external check** (like Workers Builds) is configured as a required status check in branch protection rules, the Auto-Merge Gate will fail because GitHub sees the external check as failed.

### How to fix

If a good PR is blocked by Auto-Merge Gate due to external checks:

1. **Manual merge**: Maintainer can merge directly (bypass branch protection)
2. **Update branch protection**: Remove external checks from required status checks
3. **Fix the external check**: Address the underlying issue (e.g., remove Cloudflare Workers integration if not needed)

## Adding new checks

When adding a new CI check, decide its gate level:

- **Hard gate**: Use `continue-on-error: false` (default) — blocks merge on failure
- **Soft gate**: Use `continue-on-error: true` — provides feedback but doesn't block
- **External**: Don't add to branch protection required checks
