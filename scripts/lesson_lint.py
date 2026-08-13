#!/usr/bin/env python3
"""Lightweight lesson lint / health check.

Checks for:
- Broken links (relative links to non-existent files)
- Duplicate titles
- Missing frontmatter (YAML or JSON)
- Quality score anomalies
- Empty or too-short lessons

Usage:
    python scripts/lesson_lint.py --lessons-dir lessons
    python scripts/lesson_lint.py --lessons-dir lessons --json
    python scripts/lesson_lint.py --lessons-dir lessons --fail-on high
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


# Files to exclude from linting (non-lesson files)
EXCLUDE_FILES = {
    "TEMPLATE.md",
    "LESSON_QUALITY_SCORING.md",
    "index.md",
}

# Directories to exclude
EXCLUDE_DIRS = {
    "_archive",
    "drafts",
    "templates",
}

# Non-lesson directories (language translations, etc.)
NON_LESSON_DIRS = {
    "en", "hi", "id", "ru", "tr", "vi", "zh",
}
PROVENANCE_SOURCES = {"intake", "pr", "manual", "rescue"}


def is_lesson_file(file_path: Path, lessons_dir: Path) -> bool:
    """Check if this is an actual lesson file (not a template, index, etc.)."""
    # Check filename
    if file_path.name in EXCLUDE_FILES:
        return False

    # Check if in excluded directory
    try:
        relative = file_path.relative_to(lessons_dir)
        parts = relative.parts
        # Check top-level directories
        if parts and parts[0] in EXCLUDE_DIRS:
            return False
        if parts and parts[0] in NON_LESSON_DIRS:
            return False
        # Skip files directly in lessons/ (not in core/ or contrib/)
        if len(parts) == 1:
            return False
    except ValueError:
        pass

    return True


def parse_frontmatter(content: str) -> tuple[dict | None, int]:
    """Parse YAML or JSON frontmatter. Returns (parsed_dict, body_start_line)."""
    lines = content.split("\n")

    # Check for JSON frontmatter (starts with {)
    if content.lstrip().startswith("{"):
        try:
            # Find the closing brace
            brace_count = 0
            end_idx = 0
            for i, char in enumerate(content):
                if char == "{":
                    brace_count += 1
                elif char == "}":
                    brace_count -= 1
                    if brace_count == 0:
                        end_idx = i + 1
                        break
            if end_idx > 0:
                json_str = content[:end_idx]
                data = json.loads(json_str)
                body_start = content[:end_idx].count("\n") + 1
                return data, body_start
        except json.JSONDecodeError:
            pass

    # Check for YAML frontmatter (starts with ---)
    if content.startswith("---"):
        end_idx = content.find("---", 3)
        if end_idx > 0:
            yaml_str = content[3:end_idx].strip()
            try:
                parsed = json.loads(yaml_str)
                if isinstance(parsed, dict):
                    body_start = content[:end_idx].count("\n") + 1
                    return parsed, body_start
            except json.JSONDecodeError:
                pass
            # Simple YAML parsing (key: value pairs)
            data = {}
            for line in yaml_str.split("\n"):
                if ":" in line:
                    key, _, value = line.partition(":")
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    # Try to parse numbers
                    try:
                        value = int(value)
                    except ValueError:
                        try:
                            value = float(value)
                        except ValueError:
                            pass
                    data[key] = value
            body_start = content[:end_idx].count("\n") + 1
            return data, body_start

    return None, 0


def check_frontmatter(content: str, file_path: Path) -> list[dict[str, str]]:
    """Check for valid YAML/JSON frontmatter."""
    issues = []
    frontmatter, _ = parse_frontmatter(content)
    if frontmatter is None:
        issues.append({
            "rule": "missing_frontmatter",
            "severity": "high",
            "file": str(file_path),
            "message": "No frontmatter found (expected YAML --- or JSON {})"
        })
    return issues


def check_provenance(content: str, file_path: Path) -> list[dict[str, str]]:
    """Require an auditable provenance tuple on published lessons."""
    frontmatter, _ = parse_frontmatter(content)
    if not frontmatter or frontmatter.get("status") != "published":
        return []
    issues = []
    source = str(frontmatter.get("source", "")).strip().lower()
    if source not in PROVENANCE_SOURCES:
        issues.append({
            "rule": "invalid_provenance_source",
            "severity": "medium",
            "file": str(file_path),
            "message": "Published lesson needs source=intake|pr|manual|rescue",
        })
    for field in ("author", "edited_at", "merged_by"):
        if not str(frontmatter.get(field, "")).strip():
            issues.append({
                "rule": f"missing_{field}",
                "severity": "medium",
                "file": str(file_path),
                "message": f"Published lesson is missing provenance field '{field}'",
            })
    if source == "pr" and not str(frontmatter.get("pr", "")).strip():
        issues.append({
            "rule": "missing_pr",
            "severity": "medium",
            "file": str(file_path),
            "message": "source=pr requires a PR number or URL",
        })
    return issues


def check_title(content: str, file_path: Path) -> list[dict[str, str]]:
    """Check for H1 title."""
    issues = []
    lines = content.split("\n")
    # Skip frontmatter
    _, body_start = parse_frontmatter(content)
    search_lines = lines[body_start:body_start + 10] if body_start > 0 else lines[:10]
    has_h1 = any(line.startswith("# ") for line in search_lines)
    if not has_h1:
        issues.append({
            "rule": "missing_title",
            "severity": "medium",
            "file": str(file_path),
            "message": "No H1 title found in first 10 lines of body"
        })
    return issues


def check_length(content: str, file_path: Path) -> list[dict[str, str]]:
    """Check lesson length."""
    issues = []
    lines = content.split("\n")
    _, body_start = parse_frontmatter(content)
    body_lines = len(lines[body_start:])
    if body_lines < 10:
        issues.append({
            "rule": "too_short",
            "severity": "medium",
            "file": str(file_path),
            "message": f"Lesson body is only {body_lines} lines (minimum 10)"
        })
    return issues


def check_links(content: str, file_path: Path, lessons_dir: Path) -> list[dict[str, str]]:
    """Check for broken relative links."""
    issues = []
    # Find markdown links: [text](path)
    link_pattern = re.compile(r'\[([^\]]*)\]\(([^)]+)\)')
    for match in link_pattern.finditer(content):
        link_text, link_path = match.groups()
        # Skip external URLs and anchors
        if link_path.startswith(("http://", "https://", "#", "mailto:")):
            continue
        # Skip absolute paths
        if link_path.startswith("/"):
            continue
        # Skip references to lessons/ directory (common in README)
        if "lessons/" in link_path:
            continue
        # Resolve relative link
        target = (file_path.parent / link_path).resolve()
        if not target.exists():
            issues.append({
                "rule": "broken_link",
                "severity": "low",
                "file": str(file_path),
                "message": f"Broken link: [{link_text}]({link_path})"
            })
    return issues


def check_quality_score(content: str, file_path: Path) -> list[dict[str, str]]:
    """Check for quality score issues."""
    issues = []
    frontmatter, _ = parse_frontmatter(content)
    if frontmatter and "quality_score" in frontmatter:
        score = frontmatter["quality_score"]
        if isinstance(score, (int, float)) and score < 0.3:
            issues.append({
                "rule": "low_quality_score",
                "severity": "medium",
                "file": str(file_path),
                "message": f"Quality score is {score} (below 0.3 threshold)"
            })
    return issues


def check_duplicate_titles(lessons: dict[str, str]) -> list[dict[str, str]]:
    """Check for duplicate titles across lessons."""
    issues = []
    title_map: dict[str, list[str]] = {}
    for file_path_str, content in lessons.items():
        frontmatter, body_start = parse_frontmatter(content)
        # Try to get title from frontmatter first
        if frontmatter and "title" in frontmatter:
            title = str(frontmatter["title"])
        else:
            # Fall back to H1
            lines = content.split("\n")
            search_lines = lines[body_start:body_start + 10] if body_start > 0 else lines[:10]
            title = None
            for line in search_lines:
                if line.startswith("# "):
                    title = line[2:].strip()
                    break
        if title:
            if title not in title_map:
                title_map[title] = []
            title_map[title].append(file_path_str)
    for title, files in title_map.items():
        if len(files) > 1:
            issues.append({
                "rule": "duplicate_title",
                "severity": "medium",
                "file": ", ".join(files),
                "message": f"Duplicate title: '{title}'"
            })
    return issues


def lint_lesson(file_path: Path, lessons_dir: Path) -> list[dict[str, str]]:
    """Lint a single lesson file."""
    content = file_path.read_text(encoding="utf-8")
    issues = []
    issues.extend(check_frontmatter(content, file_path))
    issues.extend(check_provenance(content, file_path))
    issues.extend(check_title(content, file_path))
    issues.extend(check_length(content, file_path))
    issues.extend(check_links(content, file_path, lessons_dir))
    issues.extend(check_quality_score(content, file_path))
    return issues


def main() -> int:
    """Main entry point."""
    import argparse
    parser = argparse.ArgumentParser(description="Lesson lint / health check")
    parser.add_argument("--lessons-dir", default="lessons", help="Lessons directory")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--fail-on", choices=["high", "medium", "low"], default="high",
                        help="Fail on issues of this severity or higher (default: high)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show all issues")
    args = parser.parse_args()

    lessons_dir = Path(args.lessons_dir)
    if not lessons_dir.exists():
        print(f"Error: {lessons_dir} not found", file=sys.stderr)
        return 1

    # Collect all lesson files (with filtering)
    all_md_files = list(lessons_dir.rglob("*.md"))
    lesson_files = [f for f in all_md_files if is_lesson_file(f, lessons_dir)]

    if not lesson_files:
        print(f"No lesson files found in {lessons_dir}", file=sys.stderr)
        return 1

    # Load all lessons for duplicate check
    lessons: dict[str, str] = {}
    for f in lesson_files:
        try:
            lessons[str(f)] = f.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            print(f"Warning: Could not read {f} (encoding error)", file=sys.stderr)
        except Exception as e:
            print(f"Warning: Could not read {f}: {e}", file=sys.stderr)

    # Run all checks
    all_issues: list[dict[str, str]] = []

    # Single-file checks
    for file_path in lesson_files:
        try:
            all_issues.extend(lint_lesson(file_path, lessons_dir))
        except Exception as e:
            all_issues.append({
                "rule": "read_error",
                "severity": "high",
                "file": str(file_path),
                "message": f"Error reading file: {e}"
            })

    # Cross-file checks
    all_issues.extend(check_duplicate_titles(lessons))

    # Sort by severity
    severity_order = {"high": 0, "medium": 1, "low": 2}
    all_issues.sort(key=lambda x: severity_order.get(x.get("severity", "low"), 3))

    # Output
    if args.json:
        print(json.dumps(all_issues, indent=2))
    else:
        if not all_issues:
            print("[OK] No issues found!")
            return 0

        print(f"## Lesson Lint Report\n")
        print(f"**Checked:** {len(lesson_files)} lesson files (from {len(all_md_files)} total .md files)\n")

        # Count by severity
        high = sum(1 for i in all_issues if i.get("severity") == "high")
        medium = sum(1 for i in all_issues if i.get("severity") == "medium")
        low = sum(1 for i in all_issues if i.get("severity") == "low")
        print(f"**Issues:** {high} high, {medium} medium, {low} low\n")

        if not args.verbose:
            # Only show high issues by default
            display_issues = [i for i in all_issues if i.get("severity") == "high"]
            if display_issues:
                print(f"### High severity (showing {len(display_issues)}):\n")
            else:
                print("### No high severity issues\n")
        else:
            display_issues = all_issues

        for issue in display_issues:
            severity = issue.get("severity", "unknown")
            icon = {"high": "[HIGH]", "medium": "[MED]", "low": "[LOW]"}.get(severity, "[???]")
            print(f"{icon} **{issue.get('rule', 'unknown')}**")
            print(f"   File: {issue.get('file', 'unknown')}")
            print(f"   {issue.get('message', 'No message')}")
            print()

    # Determine exit code
    severity_levels = {"high": 0, "medium": 1, "low": 2}
    fail_level = severity_levels.get(args.fail_on, 0)
    has_failures = any(
        severity_levels.get(i.get("severity", "low"), 3) <= fail_level
        for i in all_issues
    )
    return 1 if has_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
