# Field Reports

Real-world stories from MisakaNet users and contributors.

## How to Write a Field Report

1. Pick a real incident you solved (or helped solve)
2. Write it as a short narrative (300-800 words)
3. Include: what happened, how MisakaNet helped (or didn't), what you learned
4. Submit as `docs/field-reports/YYYY-MM-DD-slug.md`

## Before you paste terminal output

Field reports are **published**, and machine transcripts are where leaks actually happen. Paste the
numbers, the commands you ran and the messages you need — not your shell. Specifically:

* **no** token-shaped strings, even revoked ones: a reader cannot tell a session id from a credential,
  and neither can a scanner (`#279`, 2026-09-19, was a false positive on session UUIDs and cache
  hashes — the noise is real even when the finding is not);
* **no** `export -p` / `env` dumps, and no shell snapshots (`source ~/.hermes/cache/terminal/...`);
* **no** home paths, internal hostnames or private repo names — redact them to `/home/<user>/`,
  `internal.example`, `some/repo`;
* keep the agent transcript only where the *transcript is the evidence* (as in the A/B measurement
  reports), and trim it to the steps that carry the finding.

## Template

```markdown
# [Short Title]

> **Date**: YYYY-MM-DD
> **Author**: Your Name
> **Domain**: devops|python|network|...

## What Happened
[1-2 paragraphs: the incident]

## How MisakaNet Helped
[Did you find a lesson? Did you write one? What was the search experience?]

## What I Learned
[Takeaways for other users]

## Lessons Created
[Link to any lessons that came from this incident]
```

## Reports

Browse [this directory](.) — reports are named `YYYY-MM-DD-slug.md`. Recent examples:
`2026-09-18-issue-1819-agent-ab-measurement.md` (a real-agent A/B measurement) and
`2026-09-16-setup-verification-2lll5.md` (a setup verification).

This section said "No reports yet" until 2026-09-19, while the directory already held a dozen: a list
nobody maintains is worse than a pointer, so it points at the directory now.
