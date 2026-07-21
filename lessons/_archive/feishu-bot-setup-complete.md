---
{
  "title": "ARCHIVED: generic Feishu bot setup (superseded by cc-connect guide)",
  "domain": "feishu",
  "tags": ["archived", "feishu", "cc-connect", "duplicate", "bot", "setup"],
  "status": "archived",
  "source": "bootstrap",
  "created": "2026-05-19",
  "updated": "2026-07-21",
  "confidence": "0.7",
  "superseded_by": "lessons/contrib/cc-connect-feishu-setup-complete.md"
}
---

# ARCHIVED: generic Feishu bot setup (superseded by cc-connect guide)

## Problem

This file used to hold a generic Feishu/bridge setup with `<bridge-tool>` placeholders. It near-duplicated the concrete **cc-connect** guide (~0.80 similarity), so agents retrieving "feishu bot" got two conflicting paths.

## Root Cause

Bootstrap copied a template twice: one kept generic placeholders, one specialized to `cc-connect`. Duplicate detection flagged the pair (issue #552).

## Solution

**Do not use this file for new work.**

Canonical guide:

- `lessons/contrib/cc-connect-feishu-setup-complete.md`

Decision lesson at the old contrib path:

- `lessons/contrib/feishu-bot-setup-complete.md`

```bash
# install real tool
npm install -g cc-connect
cc-connect --version
```

Historical body is preserved below the fold only for git archaeology; operators should follow the canonical file.

## Verification

```bash
test -f lessons/contrib/cc-connect-feishu-setup-complete.md
test -f lessons/contrib/feishu-bot-setup-complete.md
test -f lessons/_archive/feishu-bot-setup-complete.md
python3 scripts/quality_scorer.py lessons/contrib/cc-connect-feishu-setup-complete.md
```

## Notes

- Status is `archived` on purpose.
- Hard-delete avoided so inbound links and git blame survive.
- See https://github.com/Ikalus1988/MisakaNet/issues/552
