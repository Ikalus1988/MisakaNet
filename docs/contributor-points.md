# Contributor Reputation Points (贡献者声誉积分)

## Important Disclaimer

- **No cash value**: These points have NO monetary value and are NOT redeemable.
- **Non-transferable**: Points cannot be transferred, sold, or exchanged.
- **Not a token**: NOT blockchain tokens, NOT financial assets, NOT investments.
- **Internal reputation only**: Points exist solely for recognition within MisakaNet.

## Point Rules

| Action | Points | Description |
|--------|--------|-------------|
| Submit lesson and merge | +10 | Base contribution |
| Lesson found via search | +1/hit | Utility signal |
| Lesson marked helpful | +3/vote | User recognition |
| Lesson reaches E2+ evidence | +5 | Maintainer verification |
| Fix stale lesson | +5 | Data quality |
| Translate/cleanup/restructure | +3 | Maintenance |
| Social media promotion accepted | +15 | Growth contribution |
| Lesson marked not-helpful | -2 | Quality penalty |
| Lesson deleted | -10 | Removal penalty |

## Decay Mechanism

- **12-month inactivity**: Points freeze (stop growing, no deduction)
- **Lesson marked not-helpful**: -2 points per report
- **Lesson deleted**: -10 points

## Anti-Gaming

| Measure | Rule |
|---------|------|
| Daily cap | 50 points/day |
| New account cap | 20 points/day for first 7 days |
| Vote dedup | Same user + same lesson = 1 count |
| Search dedup | Same lesson + same query within 24h = 1 count |

## Data Format

Points stored in `data/contributor-points.json`:

```json
{
  "_schema": "1.0",
  "contributors": {
    "username": {
      "total_points": 150,
      "history": [
        {
          "timestamp": "2026-08-05T10:00:00Z",
          "action": "lesson_merge",
          "points": 10,
          "detail": { "lesson_id": "some-lesson" }
        }
      ],
      "first_activity": "2026-01-01T00:00:00Z",
      "last_activity": "2026-08-05T10:00:00Z"
    }
  }
}
```

## CLI Usage

```bash
# Add points for lesson merge
python scripts/update_contributor_points.py --user alice --action lesson_merge

# Record a helpful vote
python scripts/update_contributor_points.py --user alice --action helpful_vote \
  --detail '{"lesson_id":"lesson-1","voter":"bob"}'

# Record a search hit
python scripts/update_contributor_points.py --user alice --action search_hit \
  --detail '{"lesson_id":"lesson-1","query":"python mcp"}'
```

## Design Principles
- Non-transferable
- No cash value promised
- Not exchangeable
- No blockchain
- Project-internal reputation only
