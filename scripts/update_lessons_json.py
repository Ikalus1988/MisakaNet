#!/usr/bin/env python3
"""Regenerate data/lessons.json from indexed lesson directories.

The public index intentionally keeps a stable, lightweight shape used by the
website and GitHub workflows. It indexes curated/core lessons and contrib
lessons, while excluding archives, drafts, templates, locale docs, and the
top-level lessons/index.md.
"""
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LESSONS_DIR = REPO / "lessons"
OUTPUT = REPO / "data" / "lessons.json"
INDEXED_DIRS = ("core", "contrib")


def parse_frontmatter(text: str) -> dict:
    """Parse only the standard JSON frontmatter form.

    Historical contrib files contain YAML-ish wrappers, bare JSON metadata, and
    inline `---{"title": ...}---` blocks. The current public index treats those
    as legacy content instead of trusted metadata, so keep parsing strict here.
    """
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end == -1:
        return {}
    raw = text[4:end].strip()
    if not raw.startswith("{"):
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def get_summary(content: str, max_chars: int = 160) -> str:
    """Extract first meaningful sentence after frontmatter."""
    lines = content.split('\n')
    start = 0
    if lines and lines[0].strip() == '---':
        for i in range(1, len(lines)):
            if lines[i].strip() == '---':
                start = i + 1
                break
    for line in lines[start:]:
        line = line.strip()
        if not line:
            continue
        if line == "---":
            continue
        if line.startswith("---{") and line.endswith("}---"):
            continue
        if line == "{":
            continue
        if line.startswith("{") and line.endswith("}"):
            continue
        if line.startswith('#') or line.startswith('- **'):
            continue
        if line.startswith("domain:") or line.startswith("title:") or line.startswith("verification:"):
            continue
        if line:
            return line[:max_chars] + ('…' if len(line) > max_chars else '')
    return ''


def main():
    entries = []
    for lesson_dir in INDEXED_DIRS:
        files = sorted((LESSONS_DIR / lesson_dir).glob("*.md"))
        for f in files:
            if f.name.startswith("."):
                continue
            content = f.read_text(encoding="utf-8", errors="replace")
            meta = parse_frontmatter(content)
            title = meta.get("title", f.stem)
            domain = meta.get("domain", lesson_dir)
            if isinstance(domain, list):
                domain = domain[0] if domain else lesson_dir
            tags = meta.get("tags", [])
            if not isinstance(tags, list):
                tags = [tags] if tags else []
            status = meta.get("status", "active")
            summary = meta.get("summary", "") or get_summary(content)
            rel_path = f.relative_to(LESSONS_DIR).as_posix()
            # Check for Verification section (badge-only verified semantics)
            verified = bool(re.search(r"##\s*(Verify|Verification)", content, re.IGNORECASE))
            entries.append({
                "id": f.stem,
                "title": title,
                "domain": domain,
                "tags": tags,
                "summary": summary,
                "url": f"lessons/{rel_path}",
                "created": meta.get("created", ""),
                "updated": meta.get("updated", ""),
                "validity_period_days": 365,
                "environment_version": "",
                "confidence": 0.5,
                "status": status,
                "verified": verified,
            })

    OUTPUT.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"OK lessons.json updated: {len(entries)} entries")


if __name__ == "__main__":
    main()
