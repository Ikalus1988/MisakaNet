#!/usr/bin/env python3
"""Export MisakaNet lessons to OKF (Open Knowledge Format) compatible JSONL.

Usage:
    python3 scripts/export_okf.py                    # export all lessons
    python3 scripts/export_okf.py --output data/okf/ # custom output dir
    python3 scripts/export_okf.py --domain devops    # filter by domain

Output: data/okf/lessons.jsonl (one JSON object per line)
Each line: {"type":"lesson","title":"...","description":"...","tags":[...],"timestamp":"...","domain":"...","source":"..."}
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))  # audit T2.5: import misakanet.lesson_index
LESSONS_DIR = REPO_ROOT / "lessons"
DEFAULT_OUTPUT = REPO_ROOT / "data" / "okf"


def extract_frontmatter(path: Path) -> dict | None:
    """Extract JSON or YAML frontmatter from a lesson file."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    # Try JSON frontmatter first
    import re
    m = re.match(r"^---\s*\n(\{.*?\})\n---", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    # Try YAML-like frontmatter
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return None

    meta = {}
    for line in m.group(1).split("\n"):
        line = line.strip()
        if ":" not in line or line.startswith("{"):
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if val.startswith("[") and val.endswith("]"):
            try:
                meta[key] = json.loads(val.replace("'", '"'))
            except json.JSONDecodeError:
                meta[key] = [v.strip().strip('"').strip("'") for v in val[1:-1].split(",")]
        else:
            meta[key] = val
    return meta


def extract_description(text: str, max_len: int = 200) -> str:
    """Extract a short description from the lesson body."""
    import re
    # Remove frontmatter (both ---{json}--- and ---\nyaml\n--- formats)
    m = re.match(r"^---.*?---\s*", text, re.DOTALL)
    if m:
        text = text[m.end():]

    # Also remove any remaining frontmatter-like patterns
    text = re.sub(r'^\s*\{.*?\}\s*$', '', text, flags=re.MULTILINE)

    # Find first non-heading, non-empty, non-metadata line
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("#"):
            continue
        if line.startswith("```"):
            continue
        if line.startswith("---"):
            continue
        if line.startswith("{") and line.endswith("}"):
            continue
        # Truncate
        if len(line) > max_len:
            return line[:max_len] + "..."
        return line
    return ""


def lesson_to_okf(path: Path, domain_filter: str | None = None) -> dict | None:
    """Convert a lesson file to OKF format."""
    meta = extract_frontmatter(path)
    if not meta:
        return None

    # Domain: the frontmatter is the only source.
    #
    # The previous version inferred one from the second path component — "fallback to folder name" — and did
    # it by splitting a string on a **backslash**:
    #
    #     parts = str(path.relative_to(REPO_ROOT)).split("\\")
    #
    # On Windows that yields ("lessons", "en", "x.md"); on POSIX `str(Path(...))` contains no backslash at
    # all, so the split returns one element and the whole fallback never ran. The same corpus therefore
    # exported two different files, and only on one platform: `lessons/en/mkdir-p-race-safe.md` came out with
    # `"domain": "en"` on Windows and `""` on POSIX. The windows legs found it the day the export became a
    # graded artifact (2026-09-25) — `tests/test_okf_export_freshness.py` compares bytes, so it surfaced as
    # "STALE — the tracked export has 411 records, the corpus exports 411 (+0)".
    #
    # A directory is not a domain (`contrib`/`en`/`pt-br` are layout, and `docs/agents/repo-operations.md`
    # records the directory-as-domain confusion separately), so the explicit rule is the frontmatter, and
    # POSIX — the platform that produces the tracked file and builds the index in CI — keeps the output it
    # has always had.
    domain = meta.get("domain", "")

    if domain_filter and domain != domain_filter:
        return None

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    # Extract description from body if not in frontmatter
    description = meta.get("description", "")
    if not description:
        description = extract_description(text)

    # Normalize tags
    tags = meta.get("tags", [])
    if isinstance(tags, str):
        # Handle comma-separated string
        if tags.startswith("["):
            try:
                tags = json.loads(tags)
            except json.JSONDecodeError:
                tags = [t.strip() for t in tags.strip("[]").split(",")]
        else:
            tags = [t.strip() for t in tags.split(",") if t.strip()]

    # Build OKF record
    okf = {
        "type": "lesson",
        "title": meta.get("title", path.stem),
        "description": description,
        "tags": tags,
        "timestamp": meta.get("created", meta.get("updated", "")),
        "domain": domain,
        "source": meta.get("source", ""),
        "status": meta.get("status", "published"),
        "path": str(path.relative_to(REPO_ROOT)).replace("\\", "/"),
    }

    # Optional fields
    if meta.get("verified_date"):
        okf["verified_date"] = meta["verified_date"]
    if meta.get("domain_expert"):
        okf["domain_expert"] = meta["domain_expert"]

    return okf


def build_records(domain_filter: str | None = None) -> list[dict]:
    """The OKF records for the canonical corpus, in order. No clock, no environment: same input, same output.

    Split out of `main()` so `--check` (and `tests/test_okf_export_freshness.py`) can compare a fresh export
    against the tracked one without writing a file first. Determinism is a property this file *needs*: the
    tracked `data/okf/lessons.jsonl` is refreshed by a daily job, and a non-reproducible export would show up
    as a change every single day.
    """
    from misakanet.lesson_index import canonical_lessons

    records = []
    for path in canonical_lessons(LESSONS_DIR):
        if path.name == "README.md":
            continue
        record = lesson_to_okf(path, domain_filter=domain_filter)
        if record:
            records.append(record)
    return records


def serialise(records: list[dict], fmt: str = "jsonl") -> str:
    """Exactly the bytes the export writes — one place, so `--check` cannot drift from the writer."""
    if fmt == "jsonl":
        return "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records)
    return json.dumps(records, ensure_ascii=False, indent=2)


def check_export(output_dir: Path, domain_filter: str | None, fmt: str) -> int:
    """Compare a fresh export with the tracked one. 0 = identical, 1 = stale, 2 = missing."""
    target = output_dir / ("lessons.jsonl" if fmt == "jsonl" else "lessons.json")
    if not target.is_file():
        print(f"{target} does not exist — run `python3 scripts/export_okf.py` to create it.", file=sys.stderr)
        return 2

    fresh = serialise(build_records(domain_filter), fmt)
    tracked = target.read_text(encoding="utf-8")
    if fresh == tracked:
        print(f"{target}: up to date ({len(fresh.splitlines())} records)")
        return 0

    fresh_lines = fresh.splitlines()
    tracked_lines = tracked.splitlines()
    print(f"{target}: STALE — the tracked export has {len(tracked_lines)} records, the corpus exports "
          f"{len(fresh_lines)} ({len(fresh_lines) - len(tracked_lines):+d}).", file=sys.stderr)
    for index, (a, b) in enumerate(zip(tracked_lines, fresh_lines)):
        if a != b:
            print(f"  first difference at record {index + 1}:", file=sys.stderr)
            print(f"    tracked: {a[:120]}", file=sys.stderr)
            print(f"    fresh:   {b[:120]}", file=sys.stderr)
            break
    print("  Run `python3 scripts/export_okf.py` — `data/sag.db` is built from this file, and the search "
          "path prefers SAG over the complete BM25 index (issue #2185).", file=sys.stderr)
    return 1


def main():
    parser = argparse.ArgumentParser(description="Export MisakaNet lessons to OKF format")
    parser.add_argument("--output", type=str, default=str(DEFAULT_OUTPUT), help="Output directory")
    parser.add_argument("--domain", type=str, default=None, help="Filter by domain")
    parser.add_argument("--format", choices=["jsonl", "json"], default="jsonl", help="Output format")
    parser.add_argument("--from-index", action="store_true", help="Read from data/lessons.json instead of raw files")
    parser.add_argument("--check", action="store_true",
                        help="Only compare: exit 1 when the tracked export does not match the corpus")
    args = parser.parse_args()

    if args.check:
        sys.exit(check_export(Path(args.output), args.domain, args.format))

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Fast path: read from pre-built lessons.json index
    if args.from_index:
        index_path = REPO_ROOT / "data" / "lessons.json"
        if not index_path.exists():
            print(f"Error: {index_path} not found. Run misakanet-index.py first.", file=sys.stderr)
            sys.exit(1)
        lessons = json.loads(index_path.read_text(encoding="utf-8"))
        okf_records = []
        for lesson in lessons:
            if args.domain and lesson.get("domain") != args.domain:
                continue
            okf_records.append({
                "type": "lesson",
                "title": lesson.get("title", ""),
                "description": lesson.get("summary", lesson.get("description", "")),
                "tags": lesson.get("tags", []),
                "timestamp": lesson.get("created", lesson.get("updated", "")),
                "domain": lesson.get("domain", ""),
                "source": lesson.get("source", ""),
                "status": lesson.get("status", "published"),
                "path": lesson.get("url", lesson.get("path", "")),
            })
        # Write output
        if args.format == "jsonl":
            output_file = output_dir / "lessons.jsonl"
            with open(output_file, "w", encoding="utf-8") as f:
                for record in okf_records:
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
        else:
            output_file = output_dir / "lessons.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(okf_records, f, ensure_ascii=False, indent=2)
        print(f"Exported {len(okf_records)} lessons from index to {output_file}")
        print(f"Domains: {len(set(r['domain'] for r in okf_records))}")
        return

    # Collect canonical (deduped) lessons and convert — one implementation, shared with `--check`
    # (audit T2.5 parity with the local search corpus and public index).
    from misakanet.lesson_index import canonical_lessons

    okf_records = build_records(args.domain)
    skipped = sum(1 for path in canonical_lessons(LESSONS_DIR)
                  if path.name != "README.md" and lesson_to_okf(path, domain_filter=args.domain) is None)

    # Write output
    output_file = output_dir / ("lessons.jsonl" if args.format == "jsonl" else "lessons.json")
    output_file.write_text(serialise(okf_records, args.format), encoding="utf-8")

    # Summary
    print(f"Exported {len(okf_records)} lessons to {output_file}")
    if skipped:
        print(f"Skipped {skipped} files (no valid frontmatter)")
    print(f"Domains: {len(set(r['domain'] for r in okf_records))}")
    print(f"Format: {args.format}")

    # Validate OKF required fields
    missing = []
    for r in okf_records:
        for field in ["type", "title", "description", "tags", "timestamp"]:
            if not r.get(field):
                missing.append(f"{r.get('path', '?')}: missing {field}")
    if missing:
        print(f"\nWarnings ({len(missing)} missing fields):")
        for m in missing[:10]:
            print(f"  {m}")
        if len(missing) > 10:
            print(f"  ... and {len(missing) - 10} more")


if __name__ == "__main__":
    main()

