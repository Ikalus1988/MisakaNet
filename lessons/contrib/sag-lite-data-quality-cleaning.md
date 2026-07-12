---
title: "SAG-Lite Data Quality: Clean Search Results"
domain: devops
tags: ["search", "sqlite", "fts5", "data-quality", "misakanet"]
status: published
source: agent_experience
created: 2026-07-02
---
---

## Problem

SAG-Lite search results show raw frontmatter in description field, making results unreadable:

```json
{
  "title": "pip install Timeout",
  "description": "---{\"title\": \"pip install Timeout\", \"domain\": \"devops\"}---",
  "domain": "contrib"
}
```

## Root Cause

The `extract_description()` function in `export_okf.py` fails to properly strip frontmatter when:

1. Frontmatter uses mixed YAML + JSON format: `---\ndomain: "contrib"\n{"title":...}\n---`
2. Frontmatter JSON spans multiple lines
3. Description extraction starts before frontmatter is fully removed

Additionally, `domain` field falls back to folder name ("contrib") instead of using frontmatter metadata.

## Fix

### Fix extract_description()

```python
def extract_description(text: str, max_len: int = 200) -> str:
    """Extract a short description from the lesson body."""
    import re
    # Remove frontmatter (both ---{json}--- and ---\nyaml\n--- formats)
    m = re.match(r"^---.*?---\s*", text, re.DOTALL)
    if m:
        text = text[m.end():]

    # Also remove any remaining frontmatter-like patterns
    text = re.sub(r'^\s*\{.*?\}\s*$', '', text, flags=re.MULTILINE)

    # Find first non-heading, non-empty, non-metadata line
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("#") or line.startswith("```") or line.startswith("---"):
            continue
        if line.startswith("{") and line.endswith("}"):
            continue
        if len(line) > max_len:
            return line[:max_len] + "..."
        return line
    return ""
```

### Fix domain extraction

```python
def lesson_to_okf(path: Path, domain_filter: str | None = None) -> dict | None:
    meta = extract_frontmatter(path)
    if not meta:
        return None

    # Domain: use frontmatter domain, fallback to folder name
    domain = meta.get("domain", "")
    if not domain or domain == "contrib":
        domain = meta.get("subdomain", "general")
    # ...
```

### Fix search results display

```python
def search(db_path: Path, query: str, domain: str | None = None, top: int = 5) -> list[dict]:
    # ...
    results = []
    for r in rows:
        # Clean description: remove any remaining frontmatter patterns
        desc = r["description"] or ""
        if desc.startswith("---") or desc.startswith("{"):
            desc = ""

        results.append({
            "title": r["title"],
            "description": desc,
            "domain": r["domain"],
            # ...
        })
    return results
```

## Verification

1. Rebuild OKF export: `python3 scripts/export_okf.py`
2. Rebuild SAG-Lite index: `python3 scripts/build_sag_index.py`
3. Test search: `python3 scripts/build_sag_index.py --query "pip timeout" --json`
4. Verify description is clean (no frontmatter patterns)

## Notes

- OKF export covers core/contrib normalized lessons only (not full lesson count)
- Domain field should reflect frontmatter metadata, not folder fallback
- Always rebuild index after changing export logic
