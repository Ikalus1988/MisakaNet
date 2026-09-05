"""Log harvester for the MisakaNet CLI (--harvest).

Extracted from search_knowledge.py (audit 2026-09-05, T1.1 stage 3): parses
an error log and prints a failure-memory-protocol lesson draft.
"""
import json
import re


def run_harvest(args: list[str]) -> None:
    """--harvest dispatch: parse --from-file and generate a lesson draft."""
    harvest_file = ""
    for i, arg in enumerate(args):
        if arg.startswith("--from-file="):
            harvest_file = arg.split("=", 1)[1]
        elif arg == "--from-file" and i + 1 < len(args):
            harvest_file = args[i + 1]

    if harvest_file:
        harvest_from_file(harvest_file)
    else:
        print("🌾 misaka harvest: Knowledge Harvester")
        print()
        print("  Usage:")
        print("    python3 search_knowledge.py --harvest --from-file <path>")
        print()
        print("  Planned interfaces:")
        print("    misaka harvest --bash-history    Scan $HISTFILE")
        print("    misaka harvest --pipe             Accept stdin")
        print()
        print("  See misaka-protocol.json → ecosystem.tools.harvester for spec.")


def harvest_from_file(filepath: str):
    """Log Harvester prototype — parse error log and generate lesson draft."""
    """Log Harvester prototype — parse error log and generate lesson draft."""
    import datetime as _dt
    from pathlib import Path
    path = Path(filepath)
    if not path.exists():
        print(f"❌ File not found: {filepath}")
        return
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.split("\n")

    # Extract lines that look like errors
    error_patterns = [
        r"(error|exception|traceback|failed|failure|fatal|crash|timeout|denied|not\s+found)",
        r"(killed|segfault|oom|out\s+of\s+memory|disk\s+full|permission\s+denied)",
        r"(exit\s+code\s+[1-9]|returned\s+non-zero|signal\s+\d+)",
        r"(traceback|most recent call last)",
    ]
    combined = re.compile("|".join(error_patterns), re.IGNORECASE)

    error_lines = []
    for i, line in enumerate(lines, 1):
        if combined.search(line):
            # Include a few lines of context
            start = max(0, i - 2)
            context = lines[start:i]
            error_lines.append((i, line.strip(), context))

    if not error_lines:
        print(f"⚠️  No error patterns found in {filepath}")
        print("   Try with a log file, error output, or stack trace.")
        return

    # Generate lesson draft
    query = path.stem.replace("-", " ").replace("_", " ")
    print("🌾 Harvest complete!")
    print()

    # Show first 10 errors
    print(f"📋 Found {len(error_lines)} error lines (showing first 10):")
    for lineno, line, _ in error_lines[:10]:
        print(f"  L{lineno}: {line[:120]}")
    print()

    # Generate failure-memory protocol-compliant lesson draft
    print("=" * 50)
    print("📝 Generated Lesson Draft")
    print("=" * 50)
    # Frontmatter emitted via json.dumps so quotes/backslashes in the title are
    # escaped (the old inline template produced invalid JSON for such titles).
    meta = {
        "title": f"Fix: {query[:80]}",
        "domain": "general",
        "tags": ["harvester", "auto-generated"],
        "status": "draft",
        "created": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "source": "harvester",
    }
    print(f"---\n{json.dumps(meta, ensure_ascii=False)}\n---\n")
    print("## Problem\n")
    print(f"Error encountered during `{query[:60]}`.\n")
    print("## Root Cause\n")

    # Show first error as context
    print("```text")
    for ctx_line in error_lines[0][2]:
        print(ctx_line[:200])
    print(error_lines[0][1][:200])
    print("```")
    print()
    print("## Solution")
    print()
    print("<!-- TODO: describe the fix -->")
    print()
    print("## Verification")
    print()
    print("<!-- TODO: add verification steps -->")
    print()
    print("## Notes")
    print()
    print(f"Auto-harvested from: {filepath}")
    print()
    print("=" * 50)
    print("💡 Save to lessons/ with:")
    print(f'   mv <this-output> lessons/contrib/{path.stem}.md')
    print("   Then run: python3 scripts/contribute.py lessons/contrib/<file>.md")


