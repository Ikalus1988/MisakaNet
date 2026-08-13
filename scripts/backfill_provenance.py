#!/usr/bin/env python3
"""Backfill lesson provenance from the Git history of each Markdown file.

The default mode is a report. Use ``--write`` to update frontmatter. Existing
provenance values are preserved unless ``--force`` is supplied, which makes
the script safe to run repeatedly while still allowing a deliberate rebuild.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SOURCES = {"intake", "pr", "manual", "rescue"}
NON_LESSON_DIRS = {"en", "hi", "id", "ru", "tr", "vi", "zh"}
EXCLUDED_DIRS = {"_archive", "draft", "drafts", "templates"}
EXCLUDED_FILES = {"index.md", "README.md", "TEMPLATE.md", "LESSON_QUALITY_SCORING.md"}


def display_path(path: Path) -> str:
    """Return a stable repository-relative path when possible."""
    try:
        return str(path.resolve().relative_to(REPO.resolve()))
    except ValueError:
        return str(path)


def is_candidate(path: Path, lessons_dir: Path) -> bool:
    """Match the repository's lesson-lint scope when scanning the root tree."""
    if path.name in EXCLUDED_FILES:
        return False
    if lessons_dir.name != "lessons":
        return True
    relative = path.relative_to(lessons_dir)
    if len(relative.parts) < 2:
        return False
    return relative.parts[0] not in NON_LESSON_DIRS | EXCLUDED_DIRS


def parse_yaml_value(value: str):
    """Parse the small YAML subset used by lesson frontmatter."""
    value = value.strip()
    try:
        # Lesson frontmatter commonly uses JSON-compatible arrays and quoted
        # scalars, so JSON parsing preserves tags instead of flattening them.
        return json.loads(value)
    except json.JSONDecodeError:
        return value.strip('"\'')


def parse_frontmatter(text: str) -> tuple[dict | None, int, int]:
    """Return metadata and character offsets for JSON/YAML frontmatter."""
    if text.lstrip().startswith("{"):
        depth = 0
        end = None
        for index, char in enumerate(text):
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    end = index + 1
                    break
        if end:
            try:
                return json.loads(text[:end]), 0, end
            except json.JSONDecodeError:
                pass
    if text.startswith("---"):
        end = text.find("---", 3)
        if end > 0:
            raw = text[3:end]
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    return parsed, 0, end + 3
            except json.JSONDecodeError:
                pass
            data = {}
            for line in raw.splitlines():
                if ":" in line:
                    key, value = (part.strip() for part in line.split(":", 1))
                    data[key] = parse_yaml_value(value)
            return data, 0, end + 3
    return None, 0, 0


def _git(path: Path, *args: str) -> str:
    try:
        relative = path.resolve().relative_to(REPO.resolve())
        return subprocess.check_output(
            ["git", "-C", str(REPO), *args, "--", str(relative)],
            text=True, stderr=subprocess.DEVNULL, timeout=10,
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return ""
    except ValueError:
        return ""


def infer_source(meta: dict, path: Path, commit_subject: str) -> str:
    existing = str(meta.get("source", "")).lower()
    if existing in SOURCES:
        return existing
    haystack = f"{existing} {path} {commit_subject}".lower()
    if "rescue" in haystack or "tombstone" in haystack or "fatal-guard" in haystack:
        return "rescue"
    if re.search(r"\bpr\b|pull request|merge pull request|#\d+", haystack):
        return "pr"
    if "intake" in haystack or "feedback" in haystack or "capture" in haystack:
        return "intake"
    return "manual"


def provenance_for(path: Path, meta: dict) -> dict:
    subject = _git(path, "log", "-1", "--format=%s")
    author = _git(path, "log", "-1", "--format=%an") or "unknown"
    edited_at = _git(path, "log", "-1", "--format=%cI") or datetime.now(timezone.utc).isoformat()
    source = infer_source(meta, path, subject)
    matches = re.findall(r"(?:pull request|PR|#)\s*#?(\d+)", subject, flags=re.IGNORECASE)
    result = {
        "author": meta.get("author") or author,
        "source": source,
        "edited_at": meta.get("edited_at") or edited_at,
        "merged_by": meta.get("merged_by") or author,
    }
    if matches or meta.get("pr"):
        result["pr"] = meta.get("pr") or int(matches[-1])
    return result


def update_file(path: Path, write: bool = False, force: bool = False) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    meta, start, end = parse_frontmatter(text)
    if not isinstance(meta, dict):
        return {"path": display_path(path), "status": "skipped", "reason": "no frontmatter"}
    additions = provenance_for(path, meta)
    changed = {}
    for key, value in additions.items():
        current = str(meta.get(key, "")).strip()
        needs_normalization = key == "source" and current.lower() not in SOURCES
        if force or needs_normalization or not current:
            if meta.get(key) != value:
                meta[key] = value
                changed[key] = value
    if write and changed:
        new_frontmatter = json.dumps(meta, ensure_ascii=False, indent=2)
        if text.startswith("---"):
            # Preserve fenced frontmatter so YAML lessons remain valid after
            # the migration. ``end`` already points just after the closing
            # delimiter.
            replacement = f"---\n{new_frontmatter}\n---" + text[end:]
        else:
            replacement = new_frontmatter + text[end:]
        path.write_text(replacement, encoding="utf-8")
    return {"path": display_path(path), "status": "changed" if changed else "ok", "fields": changed}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lessons-dir", type=Path, default=REPO / "lessons")
    parser.add_argument("--write", action="store_true", help="Update files; default is report-only")
    parser.add_argument("--force", action="store_true", help="Replace existing provenance values")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    lessons_dir = args.lessons_dir.resolve()
    rows = [update_file(path, write=args.write, force=args.force)
            for path in sorted(lessons_dir.rglob("*.md"))
            if is_candidate(path, lessons_dir)]
    changed = sum(row["status"] == "changed" for row in rows)
    payload = {"write": args.write, "files": len(rows), "changed": changed, "results": rows}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"provenance backfill: {changed} of {len(rows)} files would change" + (" (written)" if args.write else " (dry-run)"))
        for row in rows:
            if row["status"] == "changed":
                print(f"  {row['path']}: {', '.join(row['fields'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
