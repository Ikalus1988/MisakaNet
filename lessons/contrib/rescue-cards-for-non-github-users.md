---
{
  "domain": "ux",
  "title": "When Lessons Are Too Heavy, Use Rescue Cards",
  "tags": ["ux", "support", "lessons", "rescue", "feedback"],
  "status": "published",
  "source": "generalized support-feedback analysis",
  "created": "2026-07-17",
  "confidence": "0.88"
}
---

## Problem

Not every real user can read a full technical lesson, open a GitHub issue, or write a structured report. Some users only know that a zip file will not open, a PDF cannot be read, a SaaS document cannot be created, or an app upgrade failed.

If the only contribution path is "write a lesson" or "open a PR", these users disappear from the evidence system even though they are providing real failure samples.

## Root Cause

A lesson is optimized for developers and agents:

- root cause
- environment
- reproducible steps
- fix
- prevention
- evidence

A non-technical user often needs something much smaller:

```text
try these 3 steps; if still broken, send a screenshot
```

Their complaint is not noise. It is raw failure data.

## Solution

Introduce a lower layer: rescue cards.

```text
Developers / agents -> lessons
Non-GitHub users -> rescue cards
Maintainer -> turns rescue cards into lessons later
```

### Rescue card template

```md
# Problem title

## Try these 3 steps first

1.
2.
3.

## Still broken? Send these

- screenshot
- file type / link / error text
- operating system or app version

## Maintainer notes

- likely root cause:
- reusable fix:
- should become lesson? yes/no
```

### Good first rescue cards

- archive open failure
- PDF read failure
- SaaS document creation failure
- app upgrade failure
- screenshot feedback guide

### Capture offline evidence honestly

If a user has no GitHub account, record it as offline usage evidence, not as public feedback:

```json
{
  "source": "friend_referral",
  "channel": "offline_support",
  "problem": "cannot open archive",
  "outcome": "solved",
  "quote_allowed": false
}
```

## Verification

- At least one rescue card is used by a real non-GitHub user.
- At least one screenshot or one-sentence complaint is converted into a structured failure note.
- Product error messages improve based on recurring rescue-card failures.

## Next Agent Prompt

When a user cannot contribute a lesson, do not discard the signal. Ask for a screenshot and one sentence, then convert it into a rescue card or a lesson draft.
