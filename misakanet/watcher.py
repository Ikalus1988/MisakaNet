"""Memory dump watcher — auto-extract failure lessons from agent logs.

Monitors directories for new/modified files and extracts structured
lesson drafts from failure signals in agent conversation logs, Claude
memory dumps, and debugging transcripts.

Issue #1166
"""
import datetime as _dt
import json
import re
import sys
from pathlib import Path

# ── Failure detection patterns ──
FAILURE_PATTERNS = [
    r"(error|exception|traceback|failed|failure|fatal|crash)",
    r"(timeout|timed?\s*out|deadline\s+exceeded)",
    r"(denied|forbidden|unauthorized|403|401|500|502|503)",
    r"(killed|segfault|oom|out\s+of\s+memory|disk\s+full)",
    r"(exit\s+code\s+[1-9]|returned\s+non-zero|signal\s+\d+)",
    r"(not\s+found|missing|undefined\s*is\s*not|cannot\s+read)",
    r"(bug|defect|regression|broken|corrupt)",
]
_FAILURE_RE = re.compile("|".join(FAILURE_PATTERNS), re.IGNORECASE)

# ── Noise patterns (skip these files) ──
NOISE_PATTERNS = [
    r"^#\s*(memory|lesson|template|index)",
    r"^(title|domain|tags|status):",
    r"^\s*$",
]
_NOISE_RE = re.compile("|".join(NOISE_PATTERNS), re.IGNORECASE)


def content_filter(text: str, min_length: int = 200) -> dict:
    """Check if content is worth processing.

    Returns {pass: bool, reason: str, length: int, failure_signals: int}.
    """
    length = len(text.strip())

    if length < min_length:
        return {"pass": False, "reason": f"too short ({length} < {min_length})", "length": length}

    # Count failure signals
    failure_signals = len(_FAILURE_RE.findall(text))
    if failure_signals == 0:
        return {"pass": False, "reason": "no failure signals detected", "length": length, "failure_signals": 0}

    # Check noise ratio
    lines = text.split("\n")
    non_empty = [l for l in lines if l.strip()]
    if not non_empty:
        return {"pass": False, "reason": "empty content", "length": length}

    noise_count = sum(1 for l in non_empty if _NOISE_RE.match(l))
    noise_ratio = noise_count / len(non_empty) if non_empty else 1.0
    if noise_ratio > 0.8:
        return {"pass": False, "reason": f"too noisy ({noise_ratio:.0%} noise)", "length": length}

    return {"pass": True, "reason": "ok", "length": length, "failure_signals": failure_signals}


def detect_failures(text: str) -> list[dict]:
    """Extract failure lines with context from text.

    Returns list of {line_no, line, context, pattern}.
    """
    lines = text.split("\n")
    failures = []

    for i, line in enumerate(lines):
        match = _FAILURE_RE.search(line)
        if match:
            start = max(0, i - 1)
            end = min(len(lines), i + 3)
            context = lines[start:end]
            failures.append({
                "line_no": i + 1,
                "line": line.strip()[:200],
                "context": [l.strip()[:200] for l in context],
                "pattern": match.group().lower(),
            })

    return failures


def extract_lesson_draft(filepath: str, text: str, failures: list[dict]) -> str:
    """Generate a lesson draft from failure analysis.

    Returns markdown string with frontmatter.
    """
    path = Path(filepath)
    query = path.stem.replace("-", " ").replace("_", " ")

    meta = {
        "title": f"Fix: {query[:80]}",
        "domain": "general",
        "tags": ["watcher", "auto-extracted"],
        "status": "draft",
        "created": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "source": "memory-dump-watcher",
    }

    # Find the most relevant failure
    primary = failures[0] if failures else None

    sections = [
        f"---\n{json.dumps(meta, ensure_ascii=False)}\n---\n",
        "## Problem\n",
        f"Failure detected in `{path.name}`.\n",
    ]

    if primary:
        sections.append("### Error Context\n")
        sections.append("```text")
        for ctx_line in primary["context"]:
            sections.append(ctx_line)
        sections.append("```\n")

    sections.extend([
        "## Root Cause\n",
        "<!-- TODO: analyze the root cause from the context above -->\n",
        "## Solution\n",
        "<!-- TODO: describe the fix -->\n",
        "## Verification\n",
        "<!-- TODO: add verification steps -->\n",
        "## Notes\n",
        f"Auto-extracted from: {filepath}",
        f"Failure signals found: {len(failures)}",
        f"Extraction time: {_dt.datetime.now(_dt.timezone.utc).isoformat()}",
    ])

    return "\n".join(sections)


def process_file(filepath: str, min_length: int = 200) -> dict:
    """Process a single file through the extraction pipeline.

    Returns {status, reason, draft?, failures?, filter_result?}.
    """
    path = Path(filepath)
    if not path.exists():
        return {"status": "error", "reason": f"file not found: {filepath}"}

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return {"status": "error", "reason": f"read error: {e}"}

    # Content filter
    filter_result = content_filter(text, min_length)
    if not filter_result["pass"]:
        return {"status": "skipped", "reason": filter_result["reason"], "filter_result": filter_result}

    # Detect failures
    failures = detect_failures(text)
    if not failures:
        return {"status": "skipped", "reason": "no failures detected", "filter_result": filter_result}

    # Extract draft
    draft = extract_lesson_draft(filepath, text, failures)

    return {
        "status": "extracted",
        "reason": f"{len(failures)} failure(s) found",
        "draft": draft,
        "failures": failures[:5],  # Limit to first5 for output
        "filter_result": filter_result,
    }


def watch_directory(dirpath: str, pattern: str = "*.md", min_length: int = 200) -> list[dict]:
    """Process all matching files in a directory.

    Returns list of {file, status, reason, draft?}.
    """
    path = Path(dirpath)
    if not path.exists():
        return [{"file": dirpath, "status": "error", "reason": "directory not found"}]

    results = []
    for filepath in sorted(path.glob(pattern)):
        if filepath.is_file():
            result = process_file(str(filepath), min_length)
            result["file"] = str(filepath)
            results.append(result)

    return results


def run_extract(args: list[str]) -> None:
    """CLI entry point for extraction commands."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="misakanet extract",
        description="Extract failure lessons from agent logs and memory dumps",
    )
    parser.add_argument("--file", "-f", help="Process a single file")
    parser.add_argument("--dir", "-d", help="Process all files in directory")
    parser.add_argument("--pattern", "-p", default="*.md", help="File pattern for --dir (default: *.md)")
    parser.add_argument("--stdin", action="store_true", help="Read from stdin")
    parser.add_argument("--min-length", type=int, default=200, help="Minimum content length (default: 200)")
    parser.add_argument("--output", "-o", help="Output directory for drafts")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    parsed = parser.parse_args(args)

    results = []

    if parsed.stdin:
        text = sys.stdin.read()
        if not text:
            print("No input received on stdin", file=sys.stderr)
            sys.exit(1)
        # Process stdin as virtual file
        filter_result = content_filter(text, parsed.min_length)
        if filter_result["pass"]:
            failures = detect_failures(text)
            if failures:
                draft = extract_lesson_draft("<stdin>", text, failures)
                results.append({
                    "file": "<stdin>",
                    "status": "extracted",
                    "reason": f"{len(failures)} failure(s) found",
                    "draft": draft,
                    "failures": failures[:5],
                })
            else:
                results.append({"file": "<stdin>", "status": "skipped", "reason": "no failures detected"})
        else:
            results.append({"file": "<stdin>", "status": "skipped", "reason": filter_result["reason"]})

    elif parsed.file:
        result = process_file(parsed.file, parsed.min_length)
        result["file"] = parsed.file
        results.append(result)

    elif parsed.dir:
        results = watch_directory(parsed.dir, parsed.pattern, parsed.min_length)

    else:
        parser.print_help()
        sys.exit(0)

    # Output
    if parsed.json:
        output = json.dumps(results, indent=2, ensure_ascii=False, default=str)
        print(output)
    else:
        for r in results:
            status = r["status"]
            file = r.get("file", "?")
            reason = r.get("reason", "")

            if status == "extracted":
                print(f"✅ {file}: {reason}")
                if r.get("draft") and parsed.output:
                    outdir = Path(parsed.output)
                    outdir.mkdir(parents=True, exist_ok=True)
                    outfile = outdir / f"{Path(file).stem}-draft.md"
                    outfile.write_text(r["draft"], encoding="utf-8")
                    print(f"   → saved to {outfile}")
                elif r.get("draft"):
                    print("\n" + r["draft"])
            elif status == "skipped":
                print(f"⏭️  {file}: {reason}")
            else:
                print(f"❌ {file}: {reason}")

    # Exit code: 0 if any extracted, 1 if all skipped/errors
    if any(r["status"] == "extracted" for r in results):
        sys.exit(0)
    else:
        sys.exit(1)