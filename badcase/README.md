# Badcase Archive

This directory contains low-quality intake issues that were rejected but preserved for training and improvement.

## Purpose

1. **Training data** — Use rejected cases to improve the scoring algorithm
2. **Pattern recognition** — Identify common low-quality patterns
3. **Contributor guidance** — Generate improvement suggestions
4. **Avoid repetition** — Prevent same mistakes in future submissions

## Directory Structure

```
badcase/
├── README.md                 # This file
├── index.json               # Index of all badcases
├── {issue-number}/          # One directory per issue
│   ├── intake.md           # Original intake content
│   ├── metadata.json       # Scoring details
│   └── reasons.md          # Rejection reasons
```

## Categories

Issues are categorized by rejection reason:

| Category | Description | Count |
|----------|-------------|-------|
| `incomplete` | Missing required sections | — |
| `vague` | Too short or unclear | — |
| `test` | Test/heartbeat submissions | — |
| `spam` | Promotional or off-topic | — |

## How It Works

### Auto-Archive (score < 40)

When an intake issue receives a score below 40, it is automatically archived here with:

- `intake.md` — The original content
- `metadata.json` — Detailed scoring breakdown
- `reasons.md` — Specific rejection reasons and suggestions

### Algorithm Improvement

Badcases are used to:

1. **Extract features** — What makes a low-quality submission
2. **Adjust weights** — Tune scoring dimensions
3. **Add rules** — Create new rejection patterns
4. **Generate tests** — Create test cases for validation

### Pattern Analysis

Run analysis on badcases:

```bash
python3 scripts/analyze_badcases.py
```

This generates:
- Common rejection reasons
- Feature importance rankings
- Suggested weight adjustments

## Improvement Suggestions

Each badcase includes specific suggestions:

```markdown
## Suggestions for Improvement

- Add an 'Error' section with error messages
- Include code blocks with examples
- Add verification steps in '## Verification'
- Remove user-specific paths
- Add more technical detail
```

## Permanent Retention

Badcases are permanently retained as:

- **Training data** for algorithm improvement
- **Reference examples** for contributor guidance
- **Historical record** of submission quality

## Maintenance

- **Monthly**: Review new badcases for patterns
- **Quarterly**: Update improvement suggestions
- **Annually**: Archive old badcases to cold storage
