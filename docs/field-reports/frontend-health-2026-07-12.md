# Frontend Health Check — 2026-07-12

## Context

After a series of homepage changes (Network Voices, nav drawer, search button, i18n), a WebFetch-based audit reported "Loading..." states across the page. This report documents why those were false positives and confirms the actual frontend health.

## Key Lesson

**WebFetch does not execute JavaScript.** It captures the initial HTML shell, which always shows loading placeholders before JS fetches data. "Loading lessons..." or "Loading voices..." from WebFetch does not mean the page is broken.

## Correct Health Check Method

| Method | What it validates |
|--------|------------------|
| `curl` JSON endpoints | Data source returns valid JSON with expected count |
| `grep` deployed HTML | JS functions, element IDs, onclick handlers exist in source |
| Browser interaction | Click, type, toggle language — JS-rendered content appears |

## Verified State (2026-07-12)

| Endpoint / Feature | Status | Value |
|--------------------|--------|-------|
| `/data/lessons.json` | ✅ | 202 lessons, valid JSON |
| `/community/voices.json` | ✅ | 5 voices, `_zh` fields present |
| `/data/feed.json` | ✅ | 11 feed items |
| `/search/` page | ✅ | HTTP 200, `lesson` param handled |
| Nav drawer | ✅ | `toggleDrawer` / `closeDrawer` in HTML |
| Search button | ✅ | `goSearchPage` in HTML |
| Search suggestion routing | ✅ | `getLessonSearchUrl` → `/search/?q=...&lesson=...` |
| i18n (zh/EN) | ✅ | `switchLang` calls `renderVoices()` |
| Lesson count fallback | ✅ | Hardcoded fallback = 202 |
| Network Signals | ✅ | `total-nodes` / `knowledge-count` / `feed-count` / `last-updated` |

## Changes Made This Session

| Commit | Description |
|--------|-------------|
| `46977ec` | Network Voices MVP |
| `d84bb7d` | Lesson count fallback 202 |
| `a00d572` | Nav drawer |
| `cce23e7` | Search button |
| `b357845` | zh/EN toggle for search + voices |

## Recommendation

Do not continue modifying UI based on WebFetch reports. Wait for real browser feedback before making further changes.
