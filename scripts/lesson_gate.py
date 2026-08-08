#!/usr/bin/env python3
"""Lesson Quality Gate — structural validation for new lesson contributions (issue #889).

Validates lesson Markdown files against the quality gate checklist:
  - Required frontmatter fields: title, domain, tags, status, evidence_level
  - Minimum content length: 100 chars (excluding frontmatter)
  - No duplicate titles (against all existing lessons)
  - Domain must be in the allowed list (docs/domains/ + lessons/core|contrib|en)
  - Tags validated for format (1-10 unique strings, min 2 chars)
  - status ∈ {published, draft, archived}; evidence_level ∈ {E0..E4}

Usage:
    python3 scripts/lesson_gate.py lessons/contrib/foo.md          # validate one
    python3 scripts/lesson_gate.py lessons/a.md lessons/b.md       # validate many
    python3 scripts/lesson_gate.py --all                           # validate all lessons
    python3 scripts/lesson_gate.py --json <file>                   # JSON report

Exit code: 0 = all pass, 1 = any file failed.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LESSONS_DIR = REPO / "lessons"
DOCS_DOMAINS = REPO / "docs" / "domains"

VALID_STATUS = {"published", "draft", "archived"}
VALID_EVIDENCE = {"E0", "E1", "E2", "E3", "E4"}
MIN_CONTENT_CHARS = 100
MIN_TITLE_CHARS = 4
MAX_TITLE_CHARS = 120
MIN_TAG_CHARS = 2
MAX_TAGS = 10

# Lesson directories that count as real contributions (not templates/archive).
ACTIVE_LESSON_SUBDIRS = {"core", "contrib", "en"}

FM_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)


# ── Parsing ─────────────────────────────────────────────────────────
def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Return (frontmatter_dict, content_without_frontmatter)."""
    m = FM_RE.match(text)
    if not m:
        return {}, text
    try:
        fm = json.loads(m.group(1).strip())
    except json.JSONDecodeError:
        return {}, text[m.end():]
    if not isinstance(fm, dict):
        return {}, text[m.end():]
    return fm, text[m.end():]


# ── Field validators ────────────────────────────────────────────────
def validate_required(fm: dict) -> list[str]:
    errors = []
    for field in ("title", "domain", "tags", "status", "evidence_level"):
        if field not in fm or fm[field] in (None, ""):
            errors.append(f"missing required field: {field}")
    return errors


def validate_title(title) -> list[str]:
    if not isinstance(title, str):
        return ["title must be a string"]
    errors = []
    if len(title) < MIN_TITLE_CHARS:
        errors.append(f"title too short ({len(title)} < {MIN_TITLE_CHARS} chars)")
    if len(title) > MAX_TITLE_CHARS:
        errors.append(f"title too long ({len(title)} > {MAX_TITLE_CHARS} chars)")
    return errors


def validate_tags(tags) -> list[str]:
    if not isinstance(tags, list):
        return ["tags must be a list"]
    if len(tags) < 1:
        return ["tags must have at least 1 tag"]
    if len(tags) > MAX_TAGS:
        return [f"tags exceed {MAX_TAGS} tags"]
    if len(set(tags)) != len(tags):
        return ["tags must be unique"]
    short = [t for t in tags if not (isinstance(t, str) and len(t) >= MIN_TAG_CHARS)]
    if short:
        return [f"tags must be strings of >= {MIN_TAG_CHARS} chars: {short[:3]}"]
    return []


def validate_status(status) -> list[str]:
    if status not in VALID_STATUS:
        return [f"status must be one of {sorted(VALID_STATUS)}, got {status!r}"]
    return []


def validate_evidence(evidence_level) -> list[str]:
    if evidence_level not in VALID_EVIDENCE:
        return [f"evidence_level must be one of {sorted(VALID_EVIDENCE)}, got {evidence_level!r}"]
    return []


def validate_content_len(content: str) -> bool:
    return len(content.strip()) >= MIN_CONTENT_CHARS


# ── Repo-level checks ───────────────────────────────────────────────
def allowed_domains(repo: Path = REPO) -> set[str]:
    """Allowed domains = docs/domains/* + domains used in active lesson dirs."""
    domains = set()
    if DOCS_DOMAINS.is_dir():
        for f in DOCS_DOMAINS.glob("*.md"):
            domains.add(f.stem.lower())
    for sub in ACTIVE_LESSON_SUBDIRS:
        d = repo / "lessons" / sub
        if not d.is_dir():
            continue
        for f in d.rglob("*.md"):
            try:
                fm, _ = parse_frontmatter(f.read_text(encoding="utf-8", errors="ignore"))
            except Exception:
                continue
            dom = fm.get("domain")
            if isinstance(dom, str) and dom:
                domains.add(dom.lower())
    return domains


def _iter_active_lessons(repo: Path = REPO):
    for sub in ACTIVE_LESSON_SUBDIRS:
        d = repo / "lessons" / sub
        if d.is_dir():
            yield from d.rglob("*.md")


def find_duplicate_title(title: str, repo: Path = REPO, exclude_file: Path | None = None) -> bool:
    if not title:
        return False
    norm = title.strip().lower()
    for f in _iter_active_lessons(repo):
        if exclude_file is not None and f.resolve() == Path(exclude_file).resolve():
            continue
        try:
            fm, _ = parse_frontmatter(f.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            continue
        if isinstance(fm.get("title"), str) and fm["title"].strip().lower() == norm:
            return True
    return False


# ── File validation ─────────────────────────────────────────────────
def validate_file(path: Path, repo: Path = REPO) -> list[str]:
    errors = []
    try:
        text = Path(path).read_text(encoding="utf-8", errors="ignore")
    except OSError as e:
        return [f"cannot read {path}: {e}"]

    fm, content = parse_frontmatter(text)
    errors += validate_required(fm)
    if fm:
        errors += validate_title(fm.get("title"))
        errors += validate_tags(fm.get("tags")) if "tags" in fm else []
        errors += validate_status(fm.get("status")) if "status" in fm else []
        errors += validate_evidence(fm.get("evidence_level")) if "evidence_level" in fm else []

    if not validate_content_len(content):
        errors.append(f"content too short (< {MIN_CONTENT_CHARS} chars excluding frontmatter)")

    if fm and fm.get("title"):
        domain = fm.get("domain")
        if isinstance(domain, str) and domain:
            if domain.lower() not in allowed_domains(repo):
                errors.append(f"domain {domain!r} not in allowed list (docs/domains/ or existing lessons)")
        if find_duplicate_title(fm["title"], repo, exclude_file=path):
            errors.append(f"duplicate title: {fm['title']!r}")

    return errors


# ── CLI ─────────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv or "--help" in argv or "-h" in argv:
        print(__doc__)
        return 0

    json_mode = "--json" in argv
    argv = [a for a in argv if a != "--json"]

    if "--all" in argv:
        files = sorted(_iter_active_lessons())
    else:
        files = [Path(a) for a in argv]

    failures = 0
    report = {}
    for f in files:
        errors = validate_file(f)
        report[str(f)] = errors
        if errors:
            failures += 1

    if json_mode:
        print(json.dumps({"files": report, "failures": failures}, indent=2))
    else:
        for f, errors in report.items():
            if errors:
                print(f"FAIL {f}")
                for e in errors:
                    print(f"  - {e}")
        if failures:
            print(f"\n{len(files)} file(s) checked, {failures} failed.")
        else:
            print(f"OK: {len(files)} file(s) passed the lesson quality gate.")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
