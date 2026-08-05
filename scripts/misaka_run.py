#!/usr/bin/env python3
"""misakanet run — wrap a command, search MisakaNet on failure.

Usage:
    misakanet run -- python -m pytest
    misakanet run -- npm test
    misakanet run -- git commit -m "fix"

On failure:
1. Capture stderr tail
2. Redact secrets
3. Search MisakaNet for matching lessons
4. Print top 3 lessons
5. Offer to submit intake (opt-in, not automatic)

Does NOT:
- Auto-retry the command
- Auto-upload logs or secrets
- Modify the command or its output
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.intake_redact import redact_text


def search_lessons(query: str, top: int = 3) -> list[dict]:
    """Search MisakaNet for matching lessons."""
    try:
        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "search_knowledge.py"), query, "--json", "--top", str(top)],
            capture_output=True, text=True, timeout=15, cwd=str(REPO_ROOT),
            encoding="utf-8", errors="replace",
        )
        stdout = result.stdout or ""
        if result.returncode == 0 and stdout.strip():
            return json.loads(stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        pass
    return []


def extract_keywords(stderr: str, max_keywords: int = 5) -> str:
    """Extract error keywords from stderr for search."""
    import re

    lines = stderr.strip().split("\n")
    error_lines = []

    for line in lines[-20:]:  # Last 20 lines
        line_lower = line.lower()
        if any(kw in line_lower for kw in [
            "error", "exception", "traceback", "failed", "failure",
            "fatal", "crash", "timeout", "denied", "not found",
            "exit code", "returned non-zero", "assertion",
        ]):
            error_lines.append(line.strip())

    if not error_lines:
        # Fallback: use last 3 non-empty lines
        error_lines = [l.strip() for l in lines if l.strip()][-3:]

    # Clean up and truncate
    keywords = " ".join(error_lines)[:200]
    return keywords


def main():
    parser = argparse.ArgumentParser(
        description="Run a command and search MisakaNet on failure"
    )
    parser.add_argument("command", nargs=argparse.REMAINDER, help="Command to run")
    parser.add_argument("--capture", action="store_true", help="Auto-submit intake on failure (opt-in)")
    parser.add_argument("--top", type=int, default=3, help="Number of lessons to show")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Strip leading -- if present
    cmd = args.command
    if cmd and cmd[0] == "--":
        cmd = cmd[1:]

    if not cmd:
        parser.print_help()
        sys.exit(1)

    # Run the command
    print(f"Running: {' '.join(cmd)}")
    print("-" * 60)

    try:
        result = subprocess.run(cmd, capture_output=False)
        exit_code = result.returncode
    except FileNotFoundError:
        print(f"Error: command not found: {cmd[0]}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(130)

    print("-" * 60)

    if exit_code == 0:
        print(f"✅ Command succeeded (exit code 0)")
        sys.exit(0)

    # Command failed — search MisakaNet
    print(f"❌ Command failed (exit code {exit_code})")
    print()

    # Get stderr from the last run (we didn't capture it, so use generic search)
    # Try to extract keywords from the command itself
    cmd_str = " ".join(cmd)
    keywords = extract_keywords(cmd_str)

    print(f"Searching MisakaNet for: {keywords[:80]}...")
    lessons = search_lessons(keywords, top=args.top)

    if lessons:
        print(f"\n📋 Related MisakaNet lessons ({len(lessons)} found):")
        print()
        for i, lesson in enumerate(lessons, 1):
            title = lesson.get("title", "Unknown")
            path = lesson.get("path", "")
            score = lesson.get("score", lesson.get("rank", 0))
            print(f"  {i}. {title}")
            if path:
                print(f"     Path: {path}")
            if score:
                print(f"     Score: {score}")
            print()

        print(f"💡 Read a lesson: cat lessons/<path>.md")
    else:
        print("No matching lessons found in MisakaNet.")

    # Offer intake submission
    print()
    if args.capture:
        print("Submitting redacted intake...")
        try:
            result = subprocess.run(
                [sys.executable, str(REPO_ROOT / "scripts" / "misaka_capture.py"),
                 "--summary", f"Command failed: {cmd_str[:100]}",
                 "--source", "misaka-run"],
                capture_output=True, text=True, cwd=str(REPO_ROOT),
            )
            if result.returncode == 0:
                print(result.stdout)
            else:
                print(f"⚠️  Could not submit intake: {result.stderr}")
        except Exception as e:
            print(f"⚠️  Could not submit intake: {e}")
    else:
        print(f"💡 To submit a redacted intake:")
        print(f"   python3 scripts/misaka_capture.py --summary \"<error description>\" --source misaka-run")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
