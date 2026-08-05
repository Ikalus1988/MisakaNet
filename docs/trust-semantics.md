# Lesson Trust Semantics

MisakaNet uses three trust levels for lessons. These terms are used consistently across README, site, and generated data.

## Definitions

| Term | Meaning | Quality gate |
|------|---------|-------------|
| **indexed** | In the search index. May be draft, published, or contrib. | quality_scorer ≥ 0 |
| **published** | Approved and visible. Passes quality gate. | quality_scorer ≥ 75 |
| **verified** | Fact-checked against original source material. Rare. | manual review + source link |

## Usage

- **README / public site**: Use "indexed" when counting total lessons.
  - ✅ "249 indexed failure-recovery lessons"
  - ❌ "249 verified failure lessons" (unless all 249 have been fact-checked)

- **Lesson frontmatter**: `status` field uses `draft`, `published`, or `deprecated`.
  - `published` means it passed the quality gate, not that it was manually verified.

- **Contrib lessons**: Start as `draft`, become `published` after quality_scorer ≥ 75.

- **Core lessons**: Are `published` by default (maintainer-curated).

## Why this matters

Claiming "verified" when lessons are only "indexed" erodes trust when a lesson turns out to be wrong. Use "indexed" for scale claims, "verified" only for fact-checked content.
