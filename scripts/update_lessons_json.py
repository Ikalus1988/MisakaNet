#!/usr/bin/env python3
"""扫描 lessons/ 目录，自动生成 lessons.json（含 frontmatter 元数据）。"""
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LESSONS_DIR = REPO / "lessons"
OUTPUT = REPO / "lessons.json"


def parse_frontmatter(text: str) -> dict:
    """Parse JSON or YAML frontmatter from a .md file."""
    meta = {}
    m = re.match(r'^---\s*\n?(\{.*?\})\n?---', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    m = re.match(r'^---\s*\n(.*?)\n---', text, re.DOTALL)
    if m:
        for line in m.group(1).split('\n'):
            if ':' not in line:
                continue
            key, _, val = line.partition(':')
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if val.startswith('[') and val.endswith(']'):
                try:
                    meta[key] = json.loads(val.replace("'", '"'))
                except json.JSONDecodeError:
                    meta[key] = [v.strip().strip('"').strip("'") for v in val[1:-1].split(',')]
            else:
                meta[key] = val
    return meta


def get_summary(content: str, max_chars: int = 120) -> str:
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
        if line and not line.startswith('#') and not line.startswith('- **'):
            return line[:max_chars] + ('...' if len(line) > max_chars else '')
    return ''


def main():
    entries = []
    for f in sorted(LESSONS_DIR.glob("**/*.md")):
        if f.name == "index.md" or f.name.startswith('.'):
            continue
        content = f.read_text(encoding="utf-8", errors="replace")
        meta = parse_frontmatter(content)
        title = meta.get("title", f.stem)
        domain = meta.get("domain", "uncategorized")
        if isinstance(domain, list):
            domain = domain[0] if domain else "uncategorized"
        tags = meta.get("tags", [])
        if not isinstance(tags, list):
            tags = [tags] if tags else []
        summary = meta.get("summary", "") or get_summary(content)
        updated = meta.get("updated", meta.get("created", ""))
        rel_path = f.relative_to(LESSONS_DIR)
        entries.append({
            "id": f.stem,
            "title": title,
            "domain": domain,
            "tags": tags,
            "summary": summary,
            "url": f"lessons/{rel_path}",
            "updated": updated,
        })

    OUTPUT.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"✅ lessons.json 已更新: {len(entries)} 条")


if __name__ == "__main__":
    main()
