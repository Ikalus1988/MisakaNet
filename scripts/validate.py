#!/usr/bin/env python3
"""Validation script for MisakaNet content artifacts.

Checks artifacts for staleness based on date fields and enforces
freshness gates depending on the mode selected.
"""

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional


@dataclass
class ArtifactResult:
    """Result of validating a single artifact."""
    path: str
    date_field: str
    age_days: int
    stale: bool
    acknowledged: bool = False
    warnings: List[str] = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


def parse_frontmatter(content: str) -> tuple[Optional[dict], str]:
    """Extract frontmatter from content string.

    Returns (frontmatter_dict, body_string).
    """
    content = content.strip()
    if not content.startswith("---"):
        return None, content

    end_idx = content.find("---", 3)
    if end_idx == -1:
        return None, content

    fm_block = content[3:end_idx].strip()
    body = content[end_idx + 3:].lstrip("\n")

    fm: dict = {}
    current_key = None
    for line in fm_block.splitlines():
        if ":" in line and not line.startswith(" ") and not line.startswith("\t"):
            key, _, val = line.partition(":")
            current_key = key.strip()
            val = val.strip()
            if val:
                fm[current_key] = val
        elif current_key is not None:
            # continuation line
            fm[current_key] = f"{fm.get(current_key, '')} {line.strip()}"

    return fm, body


def extract_date_field(fm: dict) -> Optional[str]:
    """Return the primary date field value from frontmatter, or None."""
    for key in ("date", "last_verified", "modified", "updated", "published"):
        if key in fm:
            return fm[key]
    return None


def parse_date(date_str: str) -> Optional[datetime]:
    """Best-effort parsing of common date formats."""
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ",
                "%Y/%m/%d", "%d %b %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    return None


def validate_artifact(
    path: Path,
    stale_threshold_days: int,
    strict: bool,
    enforce_evidence: bool,
) -> ArtifactResult:
    """Validate a single artifact file."""
    text = path.read_text(encoding="utf-8", errors="replace")
    fm, _body = parse_frontmatter(text)

    result = ArtifactResult(
        path=str(path),
        date_field="",
        age_days=0,
        stale=False,
        acknowledged=False,
    )

    if fm is None:
        return result

    date_val = extract_date_field(fm)
    if date_val is None:
        return result

    result.date_field = date_val
    parsed = parse_date(date_val)
    if parsed is None:
        result.warnings.append(f"unparseable date: {date_val!r}")
        return result

    age = (datetime.utcnow() - parsed).days
    result.age_days = age

    if age >= stale_threshold_days:
        result.stale = True
        needs_reverify = fm.get("needs_reverify", "").strip().lower() in (
            "true", "yes", "1", "y"
        )
        result.acknowledged = needs_reverify

        if enforce_evidence and not needs_reverify:
            result.warnings.append(
                f"{path}: stale artifact missing 'needs_reverify' marker "
                f"(age={age}d)"
            )
        elif not needs_reverify:
            result.warnings.append(
                f"{path}: stale artifact (age={age}d); add needs_reverify: true "
                f"to acknowledge"
            )
        else:
            result.warnings.append(
                f"{path}: stale artifact acknowledged (age={age}d)"
            )

    return result


def collect_artifacts(root: Path, extensions: tuple[str, ...]) -> List[Path]:
    """Recursively collect candidate artifact files."""
    out: List[Path] = []
    for dirpath, _, filenames in os.walk(root):
        for fn in sorted(filenames):
            if any(fn.endswith(ext) for ext in extensions):
                out.append(Path(dirpath) / fn)
    return sorted(out)


def summarize(results: List[ArtifactResult]) -> str:
    fresh = sum(1 for r in results if not r.stale)
    stale = sum(1 for r in results if r.stale and not r.acknowledged)
    ack = sum(1 for r in results if r.stale and r.acknowledged)
    return f"fresh={fresh} stale={stale} (acknowledged={ack})"


def main() -> int:
    parser = argparse.ArgumentParser(description="MisakaNet artifact validator")
    parser.add_argument("--root", default=".", help="Root directory to scan")
    parser.add_argument(
        "--stale-days", type=int, default=90,
        help="Age in days after which an artifact is considered stale",
    )
    parser.add_argument(
        "--strict", action="store_true",
        help="Fail the pipeline on any stale artifact",
    )
    parser.add_argument(
        "--enforce-evidence", action="store_true",
        help="Also fail when a stale artifact lacks the acknowledgement marker",
    )
    parser.add_argument(
        "--extensions", default=".md,.yaml,.yml,.json,.toml",
        help="Comma-separated list of extensions to scan",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    extensions = tuple(args.extensions.split(","))
    artifacts = collect_artifacts(root, extensions)

    results: List[ArtifactResult] = []
    for art in artifacts:
        results.append(validate_artifact(art, args.stale_days, args.strict, args.enforce_evidence))

    # Print warnings
    exit_code = 0
    for r in results:
        for w in r.warnings:
            print(f"WARNING: {w}", file=sys.stderr)
            if args.strict and r.stale and not r.acknowledged:
                exit_code = 1

    summary = summarize(results)
    print(summary)

    if args.strict and exit_code == 1:
        sys.exit(exit_code)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
