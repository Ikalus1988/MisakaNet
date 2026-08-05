# Release Readiness — v2.9.0 (2026-07-12)

## Release: Search + Network Frontend Release

## Data Health

| Source | Count | Status |
|--------|-------|--------|
| `data/lessons.json` | 202 lessons | ✅ valid JSON |
| `docs/community/voices.json` | 5 voices | ✅ zh/EN fields |
| `data/feed.json` | 11 feed items | ✅ |

## Frontend Features

| Feature | Status |
|---------|--------|
| `/search/` page | ✅ URL query, quality filter, scoring, inline preview |
| Search suggestion routing | ✅ dropdown → `/search/?q=...&lesson=...` → auto-expand |
| Homepage search button | ✅ `goSearchPage()` |
| Network Voices | ✅ 5 curated, bilingual |
| Nav drawer | ✅ Main / Network / For Agents / Contact |
| Network Signals | ✅ nodes / lessons / feed / last updated |
| Node list collapse | ✅ 6 default + "View all" expand |
| i18n (zh/EN) | ✅ home + search + voices |
| Lessons data guard | ✅ CI prevents empty lessons.json |

## Fixes in this release

- README broken links (quickstart.md, og-card.png)
- Nav drawer skill.md link (root → docs/)
- Search click bug (out-of-scope variable)
- Lesson count fallback (198 → 202)
- PR merged-thank workflow (SHELDON_PAT → GITHUB_TOKEN)

## Closed Issues (16)

#443, #444, #447, #416, #393, #379, #380, #378, #394, #388, #429, #430, #434, #291, #353, #292, #450

## Known Limitations

- WebFetch reports "Loading..." (false positive — JS not executed)
- No stable lesson detail URL (inline preview + GitHub link)
- Homepage heavier than Coogen (nav drawer mitigates)
- Some historical text still has zh/EN mixing

## Open Issues for Contributors

- #293 — Architecture diagram (Mermaid)
- #417 — Non-lesson files audit
- #351 — Frontmatter batch fix
- #300 — Troubleshooting FAQ

## Checklist

- [x] pyproject.toml: 2.9.0
- [x] CHANGELOG.md: v2.9.0 entry
- [x] STATUS.md: updated
- [x] lessons.json: 202, valid
- [x] voices.json: 5, zh/EN
- [x] All links: 200/302
- [x] Search page: working
- [x] Nav drawer: working
- [x] i18n: working
