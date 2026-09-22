"""Command-line interface for local salvage review."""
import argparse
from pathlib import Path
from .core import parse_digest, render_review, review_issue


def main() -> int:
    parser = argparse.ArgumentParser(description="Review an intake digest locally")
    parser.add_argument("digest", type=Path)
    args = parser.parse_args()
    reports = [review_issue(issue) for issue in parse_digest(args.digest.read_text(encoding="utf-8"))]
    print(render_review(reports), end="")
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through the console entry point
    raise SystemExit(main())
