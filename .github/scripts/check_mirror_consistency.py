#!/usr/bin/env python3
"""Check that the generated lessons mirror contains the same lesson IDs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

MAX_PREVIEW = 20
DEFAULT_SOURCE = Path("data/lessons.json")
DEFAULT_MIRROR = Path("docs/data/lessons.json")


def load_ids(path: Path) -> tuple[int, set[str]]:
    """Return the entry count and IDs from a lessons JSON file."""
    try:
        with path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"unable to read {path}: {exc}") from exc

    if not isinstance(payload, list):
        raise ValueError(f"{path} must contain a JSON array")

    lesson_ids: set[str] = set()
    for index, entry in enumerate(payload):
        if not isinstance(entry, dict):
            raise ValueError(f"{path} entry {index} must be a JSON object")
        lesson_id = entry.get("id")
        if not isinstance(lesson_id, str) or not lesson_id.strip():
            raise ValueError(f"{path} entry {index} has no non-empty string id")
        lesson_ids.add(lesson_id)

    return len(payload), lesson_ids


def print_id_difference(label: str, ids: set[str]) -> None:
    """Print a deterministic, capped ID difference report."""
    ordered_ids = sorted(ids)
    preview = ", ".join(ordered_ids[:MAX_PREVIEW]) or "(none)"
    print(f"{label}: {len(ordered_ids)} total; first {MAX_PREVIEW}: {preview}")


def main(argv: list[str] | None = None) -> int:
    """Compare source and mirror files and return a shell-friendly status code."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", nargs="?", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("mirror", nargs="?", type=Path, default=DEFAULT_MIRROR)
    args = parser.parse_args(argv)

    try:
        source_count, source_ids = load_ids(args.source)
        mirror_count, mirror_ids = load_ids(args.mirror)
    except ValueError as exc:
        print(f"Mirror consistency check ERROR: {exc}")
        return 2

    common_ids = source_ids & mirror_ids
    missing_ids = source_ids - mirror_ids
    extra_ids = mirror_ids - source_ids

    print("Mirror consistency check")
    print(f"Source entries: {source_count}")
    print(f"Mirror entries: {mirror_count}")
    print(f"Common IDs: {len(common_ids)}")
    print_id_difference("Missing IDs in mirror", missing_ids)
    print_id_difference("Extra IDs in mirror", extra_ids)

    if source_count != mirror_count or missing_ids or extra_ids:
        print("Result: FAILED")
        return 1

    print("Result: PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
