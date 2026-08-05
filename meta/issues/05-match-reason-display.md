# Show match reason in search results

**Source:** `用户增长-使用者体验改进清单.md` item #10

## Problem

Users see search results without understanding why each result was chosen. This creates a "black box" feeling — especially when results seem irrelevant.

## Suggested implementation

Add a short match reason annotation to each result in the search output:

```
  [core][python]  lesson/  (matched: title) — Python venv troubleshooting
  [contrib]       lesson/  (matched: domain) — Django database connection
  [contrib]       lesson/  (matched: broad)  — General API error patterns
```

Possible match reasons:
- `matched: title` — query matched the lesson title
- `matched: domain` — query matched the lesson domain tag
- `matched: content` — query matched lesson body (BM25)
- `matched: broad` — result from broad mode expansion

## Acceptance criteria

- [ ] Each search result shows why it was matched
- [ ] Reason categories are clear and documented
- [ ] Output remains compact (single line per result)
- [ ] `--titles` mode also includes match reason
