#!/usr/bin/env python3
"""Fetch the Smithery Kin score for MisakaNet and write a shields.io-compatible badge JSON file.

Usage:
    python3 scripts/update-smithery-badge.py [--output data/badges/smithery.json]

The JSON output follows the shields.io endpoint schema:
    {"schemaVersion": 1, "label": "Smithery", "message": "82/100", "color": "orange"}
"""

import argparse
import json
import re
import sys
import urllib.request

SMITHERY_SERVER_URL = "https://smithery.ai/servers/misakanet/misakanet"
DEFAULT_OUTPUT = "data/badges/smithery.json"


def fetch_score(url: str) -> str | None:
    """Fetch the Smithery server page and extract the Kin score.

    The score is rendered as: <span>N<!-- -->/100</span> in the HTML.
    Returns the score string like "82/100" or None if not found.
    """
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"Error fetching {url}: {e}", file=sys.stderr)
        return None

    # Pattern: <span>N<!-- -->/100</span>
    m = re.search(r"<span>(\d+)<!-- -->/100</span>", html)
    if m:
        return f"{m.group(1)}/100"

    print(f"Score pattern not found in HTML", file=sys.stderr)
    return None


def write_badge(message: str, output_path: str) -> bool:
    """Write a shields.io-compatible badge JSON file."""
    badge = {
        "schemaVersion": 1,
        "label": "Smithery",
        "message": message,
        "color": "orange",
    }
    try:
        with open(output_path, "w") as f:
            json.dump(badge, f, indent=2)
        print(f"Written: {output_path}")
        return True
    except OSError as e:
        print(f"Error writing {output_path}: {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(description="Update Smithery Kin score badge")
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help=f"Output JSON file path (default: {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args()

    score = fetch_score(SMITHERY_SERVER_URL)
    if score is None:
        print("Failed to fetch Smithery score", file=sys.stderr)
        sys.exit(1)

    print(f"Smithery Kin score: {score}")
    if not write_badge(score, args.output):
        sys.exit(1)


if __name__ == "__main__":
    main()