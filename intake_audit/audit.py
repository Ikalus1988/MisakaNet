from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable


_ISSUE_RE = re.compile(r"(?:#|issues?/)(\d+)(?:\b|/)", re.IGNORECASE)
_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", re.DOTALL)


@dataclass(frozen=True)
class Intake:
    number: int
    created_at: datetime

    @property
    def age_days(self) -> int:
        now = datetime.now(timezone.utc)
        return max(0, (now.date() - self.created_at.astimezone(timezone.utc).date()).days)


@dataclass(frozen=True)
class Match:
    intake: Intake
    course_path: str


def parse_datetime(value: str) -> datetime:
    value = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(value)
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


def _references(value: Any) -> set[int]:
    """Extract issue numbers from strings/lists/dicts without treating arbitrary numbers as issues."""
    if isinstance(value, str):
        return {int(number) for number in _ISSUE_RE.findall(value)}
    if isinstance(value, list):
        result: set[int] = set()
        for item in value:
            result.update(_references(item))
        return result
    if isinstance(value, dict):
        result: set[int] = set()
        for item in value.values():
            result.update(_references(item))
        return result
    return set()


def _frontmatter(text: str) -> str:
    match = _FRONTMATTER_RE.match(text)
    return match.group(1) if match else ""


def referenced_intakes(text: str) -> set[int]:
    """Return only issue references in frontmatter source/provenance fields.

    This intentionally does not scan body text: a casual mention of an intake is
    not evidence that the course satisfied it.
    """
    frontmatter = _frontmatter(text)
    if not frontmatter:
        return set()
    references: set[int] = set()
    in_provenance = False
    provenance_indent = 0
    for raw_line in frontmatter.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip())
        line = raw_line.strip()
        if re.match(r"^provenance\s*:", line):
            in_provenance, provenance_indent = True, indent
            references.update(_references(line.split(":", 1)[1]))
            continue
        if in_provenance and indent <= provenance_indent and not line.startswith("-"):
            in_provenance = False
        if re.match(r"^source\s*:", line) or (in_provenance and re.match(r"^issue\s*:", line)):
            references.update(_references(line.split(":", 1)[1]))
    return references


def find_matches(intakes: Iterable[Intake], courses_root: Path) -> list[Match]:
    open_intakes = {item.number: item for item in intakes}
    matches: list[Match] = []
    for path in sorted(courses_root.rglob("*.md")):
        references = referenced_intakes(path.read_text(encoding="utf-8"))
        for number in sorted(references & open_intakes.keys()):
            matches.append(Match(open_intakes[number], path.as_posix()))
    return matches


def render_markdown(matches: Iterable[Match]) -> str:
    rows = list(matches)
    if not rows:
        return "No open intakes are referenced by course frontmatter.\n"
    lines = [
        "## Open intakes already satisfied by a course",
        "",
        "| Intake | Course | Open for |",
        "| --- | --- | ---: |",
    ]
    lines.extend(f"| #{m.intake.number} | `{m.course_path}` | {m.intake.age_days} days |" for m in rows)
    return "\n".join(lines) + "\n"


def _load_intakes(path: Path) -> list[Intake]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [Intake(int(item["number"]), parse_datetime(item["createdAt"])) for item in data]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--open-intakes", type=Path, required=True, help="JSON array from GitHub issues API")
    parser.add_argument("--courses-root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    output = render_markdown(find_matches(_load_intakes(args.open_intakes), args.courses_root))
    if args.output:
        args.output.write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
