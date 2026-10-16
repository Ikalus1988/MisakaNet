# Evidence Level Badges

MisakaNet uses an E0-E4 evidence level system to indicate the trust level of each lesson.

## Badge Colors

| Level | Badge | Color | Meaning |
|-------|-------|-------|---------|
| E0 | ![E0](assets/badges/evidence-e0.svg) | Gray | Unverified — lesson not yet validated |
| E1 | ![E1](assets/badges/evidence-e1.svg) | Red | Self-reported — submitted by author without verification |
| E2 | ![E2](assets/badges/evidence-e2.svg) | Orange | Verified fix — fix has been tested and confirmed |
| E3 | ![E3](assets/badges/evidence-e3.svg) | Blue | Peer-reviewed — reviewed and approved by another contributor |
| E4 | ![E4](assets/badges/evidence-e4.svg) | Green | Reused — another contributor or agent reused it, observed rather than reported; a vote never confers it |

## Usage in Lessons

Add the evidence level to your lesson's frontmatter:

```yaml
---
evidence_level: E2
---
```

## Badge Rendering

Badges are automatically rendered in the lesson search results and detail pages.

## Accessibility

- All badges include `<title>` elements for screen readers
- `role="img"` and `aria-labelledby` attributes are included
- Color is not the only indicator — text labels are always present

## Design Rationale

- **Gray (E0):** Neutral, indicates unknown/unverified state
- **Red (E1):** Warning color, indicates unverified self-report
- **Orange (E2):** Caution color, indicates verified but not reviewed
- **Blue (E3):** Trust color, indicates peer review
- **Green (E4):** Success color, indicates observed reuse by another contributor or agent — never a helpful vote

> **2026-10-16 — what the top rung means.** `E4` rests on **observed** reuse: a helpful vote is
> capped below it at every count (`workers/register-proxy-sw.js`, `misakanet_me_events`), because a
> vote is one person's opinion, recorded as a hint. The canonical scale is `misakanet/evidence.py`
> and [`docs/trust-semantics.md`](trust-semantics.md); the `E0`–`E3` wording in the table above and
> in the `assets/badges/evidence-e*.svg` titles predates that scale and is tracked separately.

> **2026-10-17 — which observation.** The `me_events` half of the sentence above is now pinned to a
> named producer: `E4` is conferred by `lesson_retrieved_by_distinct_clients` — two or more distinct
> `search_signals.client_hint` values actually retrieved the lesson. A lesson's own
> `verified by:` / `contributors:` line used to reach `E4` as "cross-node confirmation"; it is a
> declaration parsed out of the lesson body, so it is demoted to an `E3` hint
> (`lesson_confirmed_by`) and no longer touches the rung. Anonymous callers write no `client_hint`
> and therefore do not count: the signal under-counts rather than over-counts. Measured that day,
> **0 of 483 lessons** had two distinct observed clients — the honest answer is "nothing is at `E4`",
> not a number to soften.
