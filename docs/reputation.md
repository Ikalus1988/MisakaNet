# Contributor Reputation System

## Overview

MisakaNet uses a **reuse-weighted** reputation system that rewards contributors whose lessons actually help others solve problems — not just who submits the most PRs.

## Formula

```
score = usage_reports × 2.0
      + lessons_contributed × 1.0
      + lessons_reused × 0.2
      + lessons_verified × 0.5
```

| Signal | Weight | Why |
|--------|--------|-----|
| Usage reports | ×2.0 | Strongest signal: someone used this lesson to solve a real problem |
| Lessons contributed | ×1.0 | Baseline: contributing knowledge has value |
| Lessons reused | ×0.2 | Light signal: multiple people found it useful |
| Verified lessons | ×0.5 | Quality signal: lesson has verification steps |

## Two different boards — read this before judging a name on either

The project publishes **two** rankings, and neither of them answers "is this a person?":

| board | what it ranks | where it comes from |
|---|---|---|
| **Reputation points** (this document's formula) | contributors in the `data/contributor-points.json` ledger, weighted by *reuse* — a lesson somebody actually used | `/api/insights/reputation-leaderboard`, rendered on `docs/insights/reputation-leaderboard.html` |
| **Contributor snapshot** (`data/leaderboard.json`) | **commit authors on `main`**, scored by commit recency (30-day half-life) × median PR size | `scripts/leaderboard_watch.py` |

The second one is not the formula above, and it is worth knowing why its rows are what they are:

* contributors are taken from *commit authors* — `author.user.login` when GitHub can resolve one, and
  otherwise **the raw git author name**. So a board row can be an account, an identity that has no
  GitHub account at all (`misakanet-sync-bot` is configured in a workflow's `git config user.name`), or
  a string nobody owns;
* GitHub's `type` field separates **Apps** from users and nothing else. Measured on this repository
  (2026-09-25): `github-actions[bot]` and `dependabot[bot]` are `type=Bot`, while `actions-user`
  (GitHub's own automation identity) and `claude` (a coding agent) are `type=User`. A `User` row is
  therefore **not** evidence of a human;
* the only filter was a hardcoded list, which had missed `github-actions[bot]` — the most active
  automation identity in the repository — so it sat at **rank #2** on the public board until
  2026-09-25. The filter is now a rule (`[bot]` suffix, plus this repository's own identities, checked
  against the workflows by `tests/test_leaderboard_exclusions.py`).

There is one genuine self-declaration in the system, and it is about *nodes* rather than accounts: a
registered MCP node reports an `agent_type` (`claude-code`, `codex`, …). It is **not verified** — agents
type it themselves — so it can describe an agent population but cannot certify that any particular
contributor is (or is not) a human. When attribution has to be checkable, the project uses GitHub
instead: the PR's author identity plus the DCO sign-off.

## Anti-Gaming Safeguards

### Sigmoid Cap

A single massive PR cannot dominate the leaderboard. The per-contributor score is multiplied by a sigmoid function of their lesson count:

```
cap = 1 / (1 + e^(-0.5 × (lessons - 10)))
```

| Lessons | Cap | Effect |
|---------|-----|--------|
| 1 | 0.01 | New contributor starts low |
| 10 | 0.50 | Midpoint — earned trust |
| 50 | 1.00 | Full weight — established contributor |

This prevents gaming by submitting many low-quality lessons in one PR.

### Time Decay

Recent contributions are weighted more. Older lessons decay with a half-life of 90 days:

```
weight = 0.5^(days_since_creation / 90)
```

| Age | Weight |
|-----|--------|
| Today | 1.00 |
| 90 days | 0.50 |
| 180 days | 0.25 |
| 1 year | 0.06 |

This ensures the leaderboard reflects **current** contribution activity.

## Usage

```bash
# Full reputation table
python3 scripts/reputation.py

# Single contributor details
python3 scripts/reputation.py --contributor zsxh1990

# JSON output
python3 scripts/reputation.py --json

# Save to data/reputation.json
python3 scripts/reputation.py --save
```

## Integration with Leaderboard

The reputation score feeds into the per-contributor leaderboard. Higher reputation gives a small search quality boost (not dominant — content quality still matters more).

## Data Sources

| Source | Location | Description |
|--------|----------|-------------|
| Lessons | `lessons/core/`, `lessons/contrib/` | Lesson files with frontmatter |
| Usage reports | `data/usage_reports.json` | Reported usage events |
| Git history | `git log` | Contributor attribution |

## Tests

```bash
python3 tests/test_reputation.py
```

Covers: sigmoid cap behavior, time decay correctness, new contributor surge prevention, single-large-PR anti-gaming.
