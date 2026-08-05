#!/usr/bin/env python3
"""misakanet capture — submit a redacted failure report from the command line.

Usage:
    misaka capture --summary "DCO failed after squash merge"
    misaka capture --summary "pip timeout" --context error.log
    misaka capture --summary "CI failed" --context pytest.log --source ci

Reads context from stdin or file, redacts secrets, writes to contribution queue.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.contribution_queue import submit_contribution


def main():
    parser = argparse.ArgumentParser(
        description="Capture a redacted failure report"
    )
    parser.add_argument("--summary", "-s", required=True, help="Short failure summary")
    parser.add_argument("--context", "-c", help="File path or - for stdin (redacted before storage)")
    parser.add_argument("--source", default="cli", help="Source: cli, ci, cursor, claude-code")
    parser.add_argument("--user", default="anonymous", help="User identifier")

    args = parser.parse_args()

    # Read context
    context_text = ""
    if args.context:
        if args.context == "-":
            context_text = sys.stdin.read()
        else:
            path = Path(args.context)
            if not path.exists():
                print(f"Error: {path} not found", file=sys.stderr)
                sys.exit(1)
            context_text = path.read_text(encoding="utf-8", errors="replace")

    # Build message
    message = args.summary
    if context_text:
        # Truncate context to 2000 chars and append
        truncated = context_text[:2000]
        message = f"{args.summary}\n\nContext:\n{truncated}"

    # Submit to contribution queue (redaction happens inside)
    result = submit_contribution(
        contrib_type="intake",
        user=args.user,
        message=message,
        source=args.source,
    )

    if "error" in result:
        print(f"Error: {result['error']}", file=sys.stderr)
        if "existing_id" in result:
            print(f"Existing: {result['existing_id']}", file=sys.stderr)
        sys.exit(1)

    # Output JSON result
    import json
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
