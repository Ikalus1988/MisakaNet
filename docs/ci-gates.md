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

Read that way on 2026-09-29, the gates that block a merge are the rows below —

| Check (context as GitHub reports it) | Workflow | What it validates |
|---|---|---|
| **DCO / Signed-off-by** | `dco-check.yml` | Every commit carries `Signed-off-by:` |
| **test (ubuntu-latest, 3.11)** | `ci-cross-platform.yml` | The pytest suite on the `ubuntu-latest` + 3.11 leg of that workflow's matrix — every other Linux/macOS leg is *not* required, so none of them can hold a merge |
| **test (windows-latest, 3.11)** | `ci-cross-platform.yml` | Required since 2026-11-01. The same suite on the platform most of this project's users run, at the Python floor the package now requires (3.0.0 is `>=3.11`). One leg, not three: the 3.12/3.13 Windows legs still report and still do not block |
| **gate** | `lesson-gate.yml` | The lesson gate (structure, quality, injection). It deliberately has **no `paths:` filter**, because a required check that sometimes does not run blocks every PR that does not trigger it (#1920) |
| **audit** | `pr-checks.yml` | The audit verdict: DCO audit, secret scan (`scripts/check_worker_secrets.py`), dependency audit, the worker `node --test` suite, and a `pytest --cov-fail-under=20` run. This is the job that turns a test failure into a blocked merge |

Two notes on **what those commands actually measure** (both fixed 2026-10-02 after an audit found the
gates naming scope they did not have):

* **Coverage measures `misakanet/` only — accepted technical debt.** The command is
  `--cov=misakanet`; `scripts/` is **not** in the measured set. It used to be passed as
  `--cov=scripts` *and* omitted via `[tool.coverage.run] omit = ["scripts/*"]`, so it contributed
  0 lines to a TOTAL that therefore only ever described `misakanet/` (9,109 LOC — about 17 % of the
  54,527 LOC of non-test Python). Measuring `scripts/` properly is a separate investment decision;
  until then the debt is recorded here and in `pyproject.toml`, and the threshold is deliberately
  left alone.
* **The worker suite is `node --test 'workers/**/*.test.mjs'`, quoted.** The file count is deliberately absent (it drifted 66 → 75 between 2026-10-02 and 2026-10-07 and nothing warns when it does again — see `tests/test_ci_runs_what_it_claims.py`, which pins the *nested file exists* instead); count it yourself with `ls workers/*.test.mjs workers/*/*.test.mjs | wc -l`.
  `workers/*.test.mjs` did not reach `workers/email-register/email-utils.test.mjs` (the nested
  email worker's test, shipped by `make deploy-email`), so that file ran in no workflow at all. The
  quotes matter: unquoted, the shell expands the glob to the nested files only.

Three notes that have each cost someone an afternoon:

* **"Required" is about the *context name*.** Two legs of the `test (…)` matrix are required —
  `ubuntu-latest, 3.11` and, since 2026-11-01, `windows-latest, 3.11`. The rest are advisory, so a red
  `macos-latest` leg **does not block a merge**: it merges green-looking and shows up afterwards as "that
  PR broke something". Read the leg you changed.
  The Windows leg became required after it was shown to be *capable* of going red for a real reason: on
  2026-10-31 it caught a CRLF digest mismatch in the installer and a PATH-shim bug that Linux could not
  see, and both were fixed rather than silenced. The cost is real — every PR now waits for it — and the
  rule for the next red one is the one this repository already uses: fix the cause, or remove the
  requirement deliberately, never re-add `continue-on-error`.
* **`audit` runs pytest too** (with a coverage floor), so the suite *is* gated even though the
  `Run Test Suite` step inside `pr-checks.yml` is `continue-on-error`.
* **The node suite is behind the required `audit` verdict — it was not, until 2026-10-02.**
  `node --test 'workers/**/*.test.mjs'` (634 tests — 633 pass, 1 skipped — measured
  2026-10-02) is the only automated verification of `workers/register-proxy-sw.js`, i.e. of the MCP
  endpoint, search and the public API. It runs in the **required** `audit` job (`pr-checks.yml`) and in
  `mcp-stress.yml`, which is not required. The `audit` step carried `continue-on-error: true` and no
  `exit 1` read its outcome, so a red suite produced an `::error` annotation and a **green** required
  check; both halves are fixed and pinned by `tests/test_ci_runs_what_it_claims.py`. Worth knowing before
  you rely on it: the suite now blocks a merge, so if it ever goes flaky it blocks PRs until it is fixed —
  fix the test rather than re-adding `continue-on-error`. (`mcp-stress.yml`'s trigger paths were also a
  hand-written file list until 2026-09-29, so most of its test files did not run on the PRs that changed
  them.)

## Proving a gate can still go red

A gate that cannot fail is worse than no gate: it reports ✅ on broken input and retires the
suspicion that would have found the bug. `scripts/gate_mutation_audit.py` (#2045, #3837) therefore
proves each covered gate can still **reject** — it builds a valid artifact in a temporary directory,
asserts the gate accepts it, then breaks exactly the thing the gate checks and asserts the gate exits
non-zero.

**The hard-gate table above is the single source of that list.** `hard_gates()` parses it on every
run, each entry in the audit's `GATES` registry names the context it proves in `Gate.check`, and a
full run fails when a context in the table has no mutation. Nothing else restates the list: a row
added above turns the audit (and `tests/test_gate_mutation_audit.py`) red until a mutation for it
lands in the same pull request. The weekly ratchet `scripts/check_documented_gates.py` is the second
reader of the same table, and a test compares all three — the document, this audit's parser and the
ratchet's — so a reader that drifts to the wrong table is caught instead of agreeing with itself.

| Required context | Proven by | The mutation is |
|---|---|---|
| **DCO / Signed-off-by** | `dco` | **real** — the `Scan DCO` step of `.github/actions/dco-audit` runs against a real git history |
| **test (ubuntu-latest, 3.11)** | `pytest-leg` | **real** — the leg's own `Run Tests` + `Verify test outcome` steps run against a scenario suite whose tests fail, fail to collect, or collect nothing |
| **gate** | `lesson-gate` | **real** — `scripts/lesson_gate.py` runs against a mutated lesson |
| **audit** | `audit-secret-scan` | **real** — the job's `Secret Scan` step runs both scanners over a scenario tree with a planted token |
| | `audit-worker-suite` | **real** — the job's `node --test 'workers/**/*.test.mjs'` step runs over a scenario worker test that fails |
| | `audit-coverage-floor` | **criterion-level** — the floor is read from `pr-checks.yml` and enforced by `pytest-cov` when it is installed; without the plugin the comparison is modelled, and the audit says so when it reports |

`provenance-gate` is in the audit but **not** in the table above: it is not a required context, and
the `gate` context does not read whether a cited source exists. It is kept because it is the only
gate that checks that, and because a gate that cannot block a merge is exactly the kind that
regresses unnoticed — proving it can still fail is the audit's whole job.

Two limits worth knowing before trusting a green audit:

* **The workflow-driven mutations execute the step bodies, not GitHub Actions.** The YAML is parsed
  at run time, so deleting the `5) … exit 1` arm, the `Signed-off-by:` grep or the coverage floor
  turns the mutation green — that is the intended detection. What it cannot see is the Actions
  machinery *around* a step (its `if:`, its job's `continue-on-error`, ruleset membership); those are
  pinned by `tests/test_ci_runs_what_it_claims.py`, `tests/test_workflow_pins.py` and the ratchet.
* **The `audit` verdict block itself is not executed** — its `exit 1` chain is interleaved with the
  report generation. The audit proves the criteria that feed it (the secret scan, the worker suite,
  the coverage floor); that a red criterion reaches the job's verdict is pinned by
  `tests/test_ci_runs_what_it_claims.py`.

It runs on **every pull request**, weekly, and by manual dispatch
(`.github/workflows/gate-mutation-audit.yml`). The pull request trigger is deliberate (#3837): the
change that removes a gate's teeth *is* a pull request, and a weekly audit finds it after it merged.
The job is a single runner with read-only permissions and no secrets, and superseded runs are
cancelled; it is not in the ruleset, so it advises rather than blocks.

## A mechanism that runs by itself must be able to fail

A workflow that runs on a `schedule`, on `workflow_run`, on `issues` or on `issue_comment` runs
**without anybody watching it**. Nobody is waiting for that run, nobody sees its logs, and nobody
gets a notification when it stops working. So for those workflows the only honest failure signal is
the run itself: if the thing the mechanism exists to produce can fail quietly, the mechanism can
end **green having produced nothing** — and nothing in the repository will ever say so.

That is not hypothetical. `ci-lesson-search.yml` — "our CI failed, so surface the lessons that
match" — fired on a genuinely failing matrix and produced nothing: the log read was refused by the
token's missing `actions` scope, the refusal was swallowed by an empty `catch`, the downstream steps
were skipped, the pull request got no note, and the workflow reported success. It is the shape this
repository already knows twice: a crash that became a *constant payload* so the run stayed green
with nothing posted (#1825), and a step whose `$ERROR_SIG` was undefined so the search had nothing
to search and stayed green (#1984 — **a green run is not evidence unless something in it can
differ**).

The rule is therefore: **nothing on the path to the delivery may swallow a failure quietly.**

* the **producer** — the command that posts the comment or opens the issue — must be load-bearing:
  if it fails, the step fails and the workflow ends red;
* the producer's **feeders** — the steps whose outputs gate it — must be load-bearing too, and so
  must their feeders. A feeder that swallows its failure leaves the producer *skipped*, and a
  skipped producer is a mechanism that produced nothing and reported success.

It lives in `tests/test_self_running_mechanisms.py` and rides on the existing **`audit`** context
(the suite runs there), so no ruleset change was needed. The check is **derived from the workflows
themselves**, not from a registry of them: a new self-running workflow is covered the day it is
written, which is what a registry of sixty-odd workflows cannot do.

It is not decoration — the check is run against the *pre-fix* `ci-lesson-search.yml` and goes red
on it, and it found the one violation the repository still had:
`provenance-gate.yml`'s comment step carried `continue-on-error: true` and an empty `catch (e) {}`
since PR #1768, so a comment that could not be posted left a green run and a pull request with no
verdict on it.

What it cannot see, stated rather than left to be discovered: a production that happens *inside a
script* (`python3 scripts/register_issue.py`), a production performed by a *third-party action*
(`actions/stale`), a production that goes to *another system* (`lesson-notify.yml`'s Feishu
webhook), and a *semantic* silence — the producer runs, the run is green, and what it produced is
empty because the decision it was reading was always "no". `context.repo.full_name` was exactly
that: the path read the logs, reached a decision, and still posted nothing. No rule over workflow
text can see it; it needs a probe that exercises the path
(`tests/test_ci_failure_lesson_path.py`).

## One rule, one copy — and a gate that says so

`escapeHTML` and `readJsonResponse` used to be copied into seven pages. The copies were not equal:
four escaped with `String(value)` (so a null rendered as the words "null"), one with
`String(value || '')` (so a count of zero rendered as nothing at all), and two with
`String(val ?? '')`. Then #3694 moved the registration form to `/register/` and deleted the copy that
lived beside it — the copy the form used as a form — while the homepage's panels kept calling it.
The homepage loaded, the panels threw a `ReferenceError` the first time they had data to render,
each panel's own `catch` turned that into "the activity snapshot is unavailable", and the reader was
told the site was out of date while `/api/activity` was answering 200. Three panels went blank at
once, and every gate was green: there is no eslint, no bundler and no type checker in this tree.

So the copies are gone. One copy lives in **`docs/js/site.js`**, every page loads it with
`<script src="/js/site.js"></script>`, and the pages that used to carry a copy now carry none. The
module is a **classic script**, not an ES module: a module's scope is not visible to the pages'
classic inline scripts, and a module script is deferred, so it would run *after* them.

Two rules are enforced, both by `scripts/check_page_scripts.py`:

* **missing** — a page calls a name it does not define, and no script it loads defines it. This is
  the #3694 shape, and it is what the script was written for.
* **duplicate** — a page declares, at its top level, a name the shared module already publishes. A
  second copy is how the copies drifted apart in the first place. A name declared *inside* a
  function is that function's own business and is not a finding: a gate that flags ordinary code
  teaches maintainers to ignore it.

The script runs inside `tests/test_check_page_scripts.py`, which rides on the existing **`audit`**
context, so no ruleset change was needed. It is not decoration: `scripts/check_page_scripts.py
--reverse-test` injects both shapes and asserts each is caught — and asserts that the pages which
are *right* stay quiet (a page that defines its own helper in a tree with no shared module; a page
that loads the module; a page that shadows the name inside a function). The canonical semantics are
pinned separately, in `tests/frontend.test.js`, because a module nobody pins drifts again: the
tests there fail if the escape goes back to `String(value)` or `String(value || '')`, and if the
module is turned into an ES module.

What it cannot see: a page that loads the module and then misuses it, and a copy that was renamed
rather than duplicated — the rule knows the names the module publishes, not the names a page invents.

## Soft Gates (advisory, won't block)

These report but cannot stop a merge. Some are advisory by design; two are advisory by accident, which is
worth knowing before treating a green page as coverage.

| Check | Workflow | Why it is advisory |
|---|---|---|
| **drift (the published package must not lag the repository)** | `misakanet-setup-ci.yml` | Advisory **by decision**, and the job says so: it compares the installer on npm against this repository and turns red when the published one is behind. It is **not** a required check, because a required check with a `paths:` filter blocks every PR that does not trigger it (#1920) — so a drift gate would have to be required *without* a filter, which is its own cost. It runs on the package's own pull requests, on pushes to `main`, and daily at 04:17 UTC; the drift it measures accumulates, so a daily sweep is what keeps the state from being reachable again. It is the answer to `--verify`, which cannot see this: `--verify` compares npm with npm, so it reports "up to date" for an installer that is a month old (#3691). |
| **the other `test (…)` legs** | `ci-cross-platform.yml` | Only `ubuntu-latest, 3.11` is in the ruleset — the windows/macos legs exist to catch platform drift and merge red (measured twice on 2026-09-28 alone) |
| **MCP Endpoint Stress Tests** | `mcp-stress.yml` | The worker suite, not in the required set — see the note above |
| **CodeQL (python / javascript-typescript)** | GitHub default | Security queries; findings do not block |
| **Agent Quality Score / Validate Lesson Schema** | `pr-checks.yml` | `continue-on-error: true` |
| **Lesson Quality Score (the 0.5 threshold)** | `lesson-quality.yml` (`quality-check`) | Advisory **by decision**, and the job says so. The `lint-check` job in the same workflow *does* block — it could not before 2026-10-07, when `grep -n 'exit 1'` over the file returned nothing and the lint's own `--fail-on high` was discarded by both `\|\| true` and a job-level `continue-on-error` (#2940). The score half is left advisory because the threshold fails 5% of the corpus (3 of 60 sampled 2026-10-07, `scripts/quality_scorer.py --json`, lowest 0.46) and it scores the whole changed *file*, not the diff — so blocking it would reject unrelated edits to a pre-existing low-scoring lesson. Its result is reported in a PR comment. |
| **pr-agent / pr-genius** | external | Review helpers |
| **Workers Builds: misakanet-web** | Cloudflare bot | The site build; external, and noisy on bot PRs |

**Why the other legs stay advisory, and what keeps them from being ignored.** They are advisory *by
decision*, and the reason is that their verdict is not **deterministic**: the matrix has no
`setup-node` step, so a leg runs whatever node the runner image ships — and node's test reporter
changed its summary prefix in v23.0.0 (`# pass N` → `ℹ pass N`), which on 2026-10-26 made the
audit criterion unreadable on the macOS legs and turned a healthy gate into "could not be
evaluated" (exit 3). A leg whose answer depends on the runner image is not a merge blocker: making
it one would turn infrastructure drift into a blocked merge, and the audit cannot prove such a leg
can fail either — it executes step bodies on its own ubuntu runner, where a macOS leg does not
exist.

What the other legs *are* allowed to be is loud. `Cross-Platform Tests` is the trigger of
`ci-lesson-search.yml`, so a red leg surfaces the matching lessons on the pull request — and that
workflow now **fails loudly when it cannot read the logs it exists to read**. It used to swallow
the refusal (the token had no `actions` scope) and stay green, so a failing matrix produced no note
and nothing looked wrong; measured 2026-10-26, every run of that path behaved that way.
`tests/test_ci_failure_lesson_path.py` pins the difference between "there was nothing to report"
and "we were not allowed to look".

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
