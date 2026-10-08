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
    """Extract a lesson's frontmatter: JSON first, YAML second, and neither silently wrong.

    This used to walk the lines doing `key, _, val = line.partition(":")` after `line.strip()`.
    That destroyed three things at once (#3004): indentation (so `provenance:` and its nested
    `  issue:` collapsed onto one level, and a nested `provenance.source` overwrote the top-level
    `source`), escape handling, and block sequences (a `tags:` written as a `- item` list parsed
    to nothing). Measured: 48 lessons declare `provenance.issue` and the export carried **none**
    of them, in any record.

    32 older lessons carry a *mixed* block — a JSON object followed by a YAML-ish `provenance:`
    (081e64d5). `yaml.safe_load` rejects that outright, and dropping them would have silently cut
    32 lessons out of the index, so the JSON path uses `raw_decode` to take the leading object and
    then parses the remainder as YAML and merges it. `update_lessons_json.parse_frontmatter`
    handles the same shape but stops at the object, losing those lessons' provenance; this one
    keeps it.

    PyYAML is a declared dependency (requirements.txt, pyproject.toml), installed by the lesson
    gate, and used by fix_frontmatter.py / check_lesson_quality.py / emit_intake_receipt.py — so
    the hand-rolled version was never a constraint here, only an oversight.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    import re

    m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return None
    raw = m.group(1).strip()
    if not raw:
        return None

    import yaml

    if raw.startswith("{"):
        try:
            obj, consumed = json.JSONDecoder().raw_decode(raw)
        except (json.JSONDecodeError, ValueError):
            obj = None
        if isinstance(obj, dict):
            tail = raw[consumed:].strip()
            if tail:
                try:
                    extra = yaml.safe_load(tail)
                except yaml.YAMLError:
                    extra = None
                if isinstance(extra, dict):
                    obj.update(extra)
            return _jsonable(obj)

    try:
        loaded = yaml.safe_load(raw)
    except yaml.YAMLError:
        return None
    if not isinstance(loaded, dict):
        return None
    return _jsonable(loaded)


def _jsonable(meta: dict) -> dict:
    """YAML turns `created: 2026-10-01` into a date, which json.dumps cannot serialise.

    `update_lessons_json.py` normalises the same way; keep the two consistent.
    """
    return {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in meta.items()}

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
    # `provenance.issue` is the anchor of the receipt chain: it is what pairs an intake with
    # the lesson that answers it, and therefore what makes `converted: true` nameable.
    # It used to be dropped on the floor — the hand-rolled parser flattened
    # `provenance:` / `  issue:` onto one level and the nested `source` overwrote the top-level
    # one, so all 48 lessons that declare it exported without it (#3004). Only `issue` and
    # `source` are carried; anything else a lesson puts there is left to that lesson.
    provenance = meta.get("provenance")
    if isinstance(provenance, dict):
        kept = {k: provenance[k] for k in ("issue", "source") if provenance.get(k)}
        if kept:
            okf["provenance"] = kept
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


def corpus_size() -> int:
    """How many lessons a complete export covers: `lessons/**/*.md`, READMEs excluded.

    The denominator of the coverage floor below. `build_sag_index.export_coverage` counts the corpus the
    same way; both sides read the number from the same place, so "what the corpus is" cannot move for one
    of them and not the other.
    """
    from misakanet.lesson_index import canonical_lessons

    return sum(1 for path in canonical_lessons(LESSONS_DIR) if path.name != "README.md")


def coverage_shortfall(covered: int, total: int) -> tuple[bool, str]:
    """Should the writer refuse to write an export covering `covered` of `total` lessons?

    `--check` cannot answer this one, and that is the point: it re-runs the same `build_records()` and
    compares the result with the file that run just wrote, so a *short* export agrees with itself and
    passes. Only a relation to the corpus can see it — `build_sag_index.py` states the same relation for
    the reader (`COVERAGE_FLOOR`, with the historical numbers behind it); this is the writer's half, and
    it exists because the writer had none: `main()` printed "Skipped N files (no valid frontmatter)" and
    exited 0, so a frontmatter parser that quietly stops parsing (the shape of #1726, where CI lacking
    PyYAML degraded the parser for 91% of the corpus) would write a small file and look successful.

    Not cosmetic: `data/sag.db` is built from this file and the local search path prefers SAG over the
    complete BM25 index, so the 47%-covering export #2185 was filed about made search *worse* than having
    no index. A short export is worse than a stale one, because a stale one is at least the whole corpus
    as of a date.
    """
    from scripts.build_sag_index import COVERAGE_FLOOR

    if not total:
        return True, "the corpus is empty (LESSONS_DIR resolved to nothing), so the export would be empty"
    if covered < total * COVERAGE_FLOOR:
        missing = total - covered
        return True, (f"it would cover {covered} of {total} lessons ({missing} missing, "
                      f"{100 * missing / total:.0f}%), and the floor is {COVERAGE_FLOOR:.0%}")
    return False, ""


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

    # Before, not after the write: a guard that runs afterwards has already replaced the tracked file
    # (and staged it for the self-merging pull request), which is the artifact this refuses to produce.
    # `--domain` is a filter by definition, so it is exempt — the floor is about the complete export.
    if args.domain is None:
        short, why = coverage_shortfall(len(okf_records), corpus_size())
        if short:
            print(f"refusing to write {output_file}: {why}.", file=sys.stderr)
            print(f"  {output_file} is unchanged. A short export is worse than a stale one: "
                  f"`data/sag.db` is built from this file and the search path prefers SAG over the complete "
                  f"BM25 index, so a partial export makes search *worse* than no index (#2185).",
                  file=sys.stderr)
            print("  Fix the cause (the corpus path, the frontmatter parser) and run again; the daily "
                  "`update-lessons.yml` job lands a complete export through the self-merging pull request.",
                  file=sys.stderr)
            sys.exit(1)

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

