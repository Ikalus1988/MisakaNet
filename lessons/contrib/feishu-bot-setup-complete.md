---
{
  "title": "Near-duplicate Feishu bot lessons: keep cc-connect, archive generic stub",
  "domain": "feishu",
  "tags": ["feishu", "cc-connect", "duplicate", "lesson-quality", "archive", "cleanup"],
  "status": "published",
  "source": "uncledad96-glitch",
  "created": "2026-07-21",
  "updated": "2026-07-21",
  "confidence": "0.9",
  "supersedes": "lessons/_archive/feishu-bot-setup-complete.md",
  "see_also": "lessons/contrib/cc-connect-feishu-setup-complete.md"
}
---

# Near-duplicate Feishu bot lessons: keep cc-connect, archive generic stub

## Problem

Duplicate detection flagged two lessons with ~0.80 similarity:

- `lessons/contrib/cc-connect-feishu-setup-complete.md`
- `lessons/contrib/feishu-bot-setup-complete.md` (this path)

Agents retrieving "feishu bot setup" got two near-identical guides. The generic file used `<bridge-tool>` placeholders; the cc-connect file named the real tool and had fuller steps. Issue #552 asked to resolve without hard-deleting history.

## Root Cause

Bootstrap-era lessons were copied with different titles but the same structure. Similarity search correctly treated them as near-duplicates. Leaving both active confuses BM25/ranking and wastes agent context.

## Solution

1. **Keep** `cc-connect-feishu-setup-complete.md` as the canonical setup guide (real package name `cc-connect`).
2. **Move** the old generic body to `lessons/_archive/feishu-bot-setup-complete.md` (preserves git history and inbound links to content).
3. **Replace** this path with a short decision lesson (not a hollow redirect) so the URL still resolves and quality scoring has Problem/Cause/Fix/Verify sections.

```bash
# pattern for future duplicate cleanups
git mv lessons/contrib/weaker.md lessons/_archive/weaker.md
# write a decision lesson at the old path OR leave a see_also note in the kept file
```

Do **not** merge both bodies into a third file (issue #552).

## Verification

```bash
test -f lessons/contrib/cc-connect-feishu-setup-complete.md
test -f lessons/_archive/feishu-bot-setup-complete.md
test -f lessons/contrib/feishu-bot-setup-complete.md
# retrieval should prefer the cc-connect guide for install steps
rg -n "npm install -g cc-connect" lessons/contrib/cc-connect-feishu-setup-complete.md
```

## Notes

- Hard `rm` of contrib paths breaks old bookmarks; archive + decision lesson is safer.
- If quality CI scores the archived copy, that is expected — archive is historical, not the live guide.
- Related issue: https://github.com/Ikalus1988/MisakaNet/issues/552
