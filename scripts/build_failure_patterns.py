#!/usr/bin/env python3
"""Build and update the failure_patterns error-signature sidecar index.

Scans all canonical lessons, extracts normalized error templates, regular
expressions, and high-entropy key tokens, and writes data/failure_patterns.json.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from misakanet.search.patterns import build_failure_patterns  # noqa: E402


def main() -> int:
    """Execute failure pattern extraction across canonical lessons."""
    parser = argparse.ArgumentParser(description="Generate failure_patterns sidecar index.")
    parser.add_argument(
        "--lessons-dir",
        type=Path,
        default=REPO_ROOT / "lessons",
        help="Path to lessons directory",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "data" / "failure_patterns.json",
        help="Path to output JSON file",
    )
    args = parser.parse_args()

    records = build_failure_patterns(args.lessons_dir, args.output)
    print(f"Generated failure_patterns index: {len(records)} lessons -> {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
