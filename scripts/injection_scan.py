#!/usr/bin/env python3
"""Fail closed when public documentation contains common secret-shaped text."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_PATHS = (ROOT / "docs",)
PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]+PRIVATE KEY-----"),
    re.compile(r"(?:ghp|github_pat|sk|xox[baprs])-[-A-Za-z0-9_]{12,}"),
    re.compile(r"(?:api[_-]?key|access[_-]?token|secret)\s*[:=]\s*['\"]?[A-Za-z0-9+/=_-]{12,}", re.I),
    re.compile(r"(?:password|passwd|pwd)\s*[:=]\s*\S+", re.I),
)


def findings(paths: tuple[Path, ...] = PUBLIC_PATHS) -> list[str]:
    results: list[str] = []
    for base in paths:
        if not base.exists():
            continue
        for path in sorted(p for p in base.rglob("*") if p.is_file()):
            if path.name.startswith("handoff-"):
                continue
            text = path.read_text(encoding="utf-8")
            for line_number, line in enumerate(text.splitlines(), 1):
                if any(pattern.search(line) for pattern in PATTERNS):
                    try:
                        label = str(path.relative_to(ROOT))
                    except ValueError:
                        label = str(path)
                    results.append(f"{label}:{line_number}")
    return results


def main() -> int:
    hits = findings()
    if hits:
        print("Potential secret-shaped content found:")
        print("\n".join(hits))
        return 1
    print("No secret-shaped content found in public documentation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
