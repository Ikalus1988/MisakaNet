# Journey Report Review Checklist

Use this checklist when reviewing journey report PRs (#510).

## Quick Triage

- [ ] At least 2 journey steps completed?
- [ ] Specific evidence (screenshots, commands, reproduction steps)?
- [ ] No secrets, tokens, or private personal data?
- [ ] No unrelated code changes?
- [ ] No fake human feedback?

## Quality Tier

| Tier | Criteria | Decision |
|------|----------|----------|
| Basic | 2 steps + clear feedback | Consider merge |
| Good | 3–4 steps + reproduction evidence | Recommend merge |
| Excellent | Full chain + human feedback + bug/test/lesson candidate | Prioritize merge |

## Review Questions

1. **Is the feedback actionable?** Can we turn it into a follow-up issue?
2. **Are bugs reproducible?** Does the report include enough detail to reproduce?
3. **Is it honest?** Does it report failures and friction, not just success?

## Red Flags

- Generic feedback with no specifics ("everything is fine")
- Screenshots with visible secrets or tokens
- Unrelated code changes mixed in
- Copied/AI-generated human feedback
- Report that only praises without identifying friction

## After Merge

- [ ] Thank the contributor
- [ ] Create follow-up issues for actionable friction points
- [ ] Update docs if confusion was widespread
