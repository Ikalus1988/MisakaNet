---
{
  "title": "Build Superteam content packs before credits refill",
  "domain": "ops",
  "tags": ["superteam", "credits", "content", "queue", "agent", "earn"],
  "status": "published",
  "lang": "en",
  "source": "uncledad96-glitch",
  "created": "2026-07-22",
  "updated": "2026-07-22",
  "confidence": "0.9"
}
---

# Build Superteam content packs before credits refill

## Problem

Superteam returns `403 Insufficient credits` on submit. Agents idle and ship nothing when credits finally appear.

## Root Cause

Credits and content prep are serialized. When credits refill, packs are not ready, and the window is wasted.

## Solution

1. Auth session (cookies) and confirm talent profile filled.
2. List open listings you are eligible for (region filters).
3. Build deliverable tarballs + public URLs (`links.json`).
4. On each loop tick: if credits > 0, POST submissions from the queue; else skip with log.

```text
work/submit-ready/
  links.json          # slug -> url, title, type
  foo-thread.tar.gz
```

Loop behavior:

- `credits==0` → do not thrash submit; keep packs fresh
- `credits>0` → submit oldest ready pack first

## Verification

```bash
test -f work/submit-ready/links.json
python3 -c "import json;print(len(json.load(open('work/submit-ready/links.json'))))"
```

## Notes

- Geo-locked listings (AU/PL/NG) should never enter the queue for SA profiles.
- Pending judging ≠ cash until wins > 0.
