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
