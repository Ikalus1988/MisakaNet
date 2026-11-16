# pr-agent retired — 2026-11-16

Two workflows, one config file and one script removed:

| removed | what it did |
|---|---|
| `.github/workflows/pr-agent-review.yml` | `Codium-ai/pr-agent` v0.49.0 on every same-repo PR (not `docs-only`), plus the `/review` `/describe` `/improve` `/ask` slash commands. Posted review comments and created the `Review effort n/5` labels |
| `.github/workflows/pr-agent-verdicts.yml` | daily classifier for *that* workflow's red runs — "was this a model timeout or a real review?" |
| `.pr-agent.toml` | its configuration |
| `scripts/pr_agent_verdict.py`, `tests/test_pr_agent_verdict.py` | the classifier behind the second row |

## Why

**It had already stopped reviewing, and its red looked like noise.** On 2026-11-16 every run ended in
`litellm.AuthenticationError: login fail: Please carry the API secret key` — `OPENAI_KEY` had expired.
The failure was not new in kind: the day before it was `APITimeoutError` against `openai/minimax-M3`.
Both arrive as the check conclusion `failure`, which is why `pr-agent-verdicts.yml` existed at all —
one workflow whose entire job was to explain another workflow's red. That is a maintenance cost paid
permanently to keep a review nobody could trust.

**A red that cannot be fixed by a pull request teaches people to ignore red.** Eleven PRs this week
carried a failing check that meant "the vendor's key is stale". The required set on `main` is DCO,
`test (ubuntu-latest, 3.11)`, `gate`, `audit` — pr-agent was never one of them, so its red blocked
nothing and warned no one.

**What was lost is smaller than it looks.** `pr-agent` posted advisory review prose; the repository's
own gates do the work: `audit` (required, and it runs the suite plus the node worker tests),
`pr-shape-guard` (dumps and generated-file PRs), `gate-mutation-audit` (proves a hard gate can still go
red), `pr-genius-check` (still present, non-blocking, no model credential), and 5,500 tests. What is
genuinely gone is a second opinion in English prose on a diff — useful when it works, and it had not
worked for days before anyone noticed.

## What moved with it

- `tests/test_workflow_author_association.py` kept its rule and lost its subject. The rule — *a
  workflow that can act on someone else's comment and holds write scope or a model key must check
  `author_association`* — still measures `fix-dco.yml`, `adopt-pr.yml` and `newbie-welcome.yml`; the
  three tests that read `pr-agent-review.yml`'s own `if:` are gone with the file.
- `tests/test_workflow_timeouts.py` lost its `pr-agent` measurement row (6.4 minutes, two samples).
- `docs/CI.md` lost both rows (质量门禁 28 → 26); `docs/ci-gates.md`, `state-of-the-repo.md` and
  `agents/repo-operations.md` now say `pr-genius` where they said `pr-agent / pr-genius`.
- `docs/maintainer/credentials-and-environments.md` §2 now records `OPENAI_KEY` as read by **nothing**.

## Still owed by the owner

1. **Delete the `OPENAI_KEY` repository secret.** GitHub → Settings → Secrets → Actions. Leaving it is
   the failure mode this file exists to avoid: a credential that looks like it backs a live check.
2. **The `Review effort n/5` labels** were created by the action, not by this repository. They are
   stale on old PRs and inert; delete them at leisure, or leave them — nothing reads them.

## What would bring it back

A reviewer whose failure mode is distinguishable from its success without a second workflow explaining
it, and whose key is owned by something that notices when it expires. The measurement that made this
retirement a decision rather than a guess is in `scripts/growth_funnel_snapshot.py`'s spirit: a red
check that has never once blocked anything is not a gate, it is decoration that costs a key.
