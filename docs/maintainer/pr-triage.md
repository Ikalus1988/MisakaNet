# PR Triage Guide

## Closed-DCO Absorption Batch (2026-08-02)

Closed-DCO absorption batch completed: shell helper, CI hygiene, benchmark catalog, query expansion, intake digest, English translations, runtime smoke.

All implemented via clean-room PRs with DCO sign-off. Original closed PRs were not copied.

## Stale PR Bulk Close (2026-08-02)

19 DCO-failed PRs closed (#685-692, #695-696, #700-701, #708-713, #679). Reviewed as demand signals only.

We will not copy code or text from these PRs. Any follow-up will be clean-room implementation from current issues and current repository state.

Signals retained:
- runtime smoke evidence → #757, #761
- benchmark task catalog → #742 (closed, absorbed)
- metadata consistency audit → deferred to v2.15
- onboarding first-run flow → #646 (active)
- multilingual lesson demand → i18n bounty issues active

## PR Genius (Advisory Only)

PR Genius is a CI check that provides automated risk assessment for PRs. It is **advisory only** — not a merge gate.

> PR Genius is advisory only. DCO and audit/shape/security remain merge blockers; PR Genius output is used for triage priority and review depth.

### How to use

| PR Genius result | Action |
|---|---|
| low risk | Quick diff review, normal process |
| medium risk | Read checklist, then human judgment |
| high risk | Deep review required (workflow/script/security) |

### What PR Genius catches

- Scope mixing (unrelated files in one PR)
- Workflow permission changes
- Benchmark/metadata overclaiming
- Random/simulated results in scripts
- Missing issue references

### What PR Genius does NOT catch

- Content quality of lessons
- Mojibake/encoding issues
- Whether DCO is signed (separate check)
- Whether tests actually pass (separate check)

### Merge blockers (hard requirements)

| Check | Required |
|---|---|
| DCO | Yes |
| audit/shape/security | Yes |
| PR Genius | No (advisory) |

### Observation log

Track PR Genius accuracy over 5-10 PRs before adjusting:

| PR | Genius risk | Human conclusion | Useful? | Notes |
|---|---|---|---|---|
| #724 | pass | pending | TBD | |
| #723 | pass | pending | TBD | |
| #721 | N/A | pending | TBD | No Genius run |
| #720 | N/A | pending | TBD | No Genius run |

Run more PRs through before deciding to:
- Add to branch protection (if accurate)
- Remove (if noisy)
- Keep as-is (if useful but not blocking)
