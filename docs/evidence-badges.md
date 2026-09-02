# Evidence Level Badges

MisakaNet uses an E0-E4 evidence level system to indicate the trust level of each lesson.

## Badge Colors

| Level | Badge | Color | Meaning |
|-------|-------|-------|---------|
| E0 | ![E0](assets/badges/evidence-e0.svg) | Gray | Unverified — lesson not yet validated |
| E1 | ![E1](assets/badges/evidence-e1.svg) | Red | Self-reported — submitted by author without verification |
| E2 | ![E2](assets/badges/evidence-e2.svg) | Orange | Verified fix — fix has been tested and confirmed |
| E3 | ![E3](assets/badges/evidence-e3.svg) | Blue | Peer-reviewed — reviewed and approved by another contributor |
| E4 | ![E4](assets/badges/evidence-e4.svg) | Green | Maintainer-verified — verified by a project maintainer |

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
- **Green (E4):** Success color, indicates maintainer verification
