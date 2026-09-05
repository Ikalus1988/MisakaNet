#!/usr/bin/env python3
"""Heal/diagnose mode for the MisakaNet CLI.

Extracted from search_knowledge.py (audit 2026-09-05, T1.1 stage 1) — the
CLI entry keeps dispatching to :func:`heal` via a module-level import.

`--heal` parses error logs, searches lessons and reports coverage. Fixtures
for unmatched signatures are opt-in (``--write``) so raw logs — which may
contain credentials/PII — are never auto-saved (audit QW5).
"""
import re
import sys
import time

# ── Heal mode: parse error logs, search lessons, return diagnosis ──
# 4-level cascading fallback: traceback → error signature → exit code → last N lines

# ANSI escape sequence pattern
_ANSI_RE = re.compile(r'\x1b\[[0-9;]*m')


def _strip_ansi(text: str) -> str:
    """Remove ANSI color codes from log text."""
    return _ANSI_RE.sub('', text)


def _parse_error_signature(log_text: str) -> str:
    """
    4-level cascading error signature extractor.
    Returns the most specific error signature found.
    """
    text = _strip_ansi(log_text)

    # Level 1: Traceback — find the last exception line
    tb_matches = re.findall(
        r"(?:[a-zA-Z0-9_]+Error|Exception|RuntimeError|Warning|Fault):\s*.+", text
    )
    if tb_matches:
        return tb_matches[-1]

    # Level 2: ERROR / Error: <message>
    err_match = re.search(r"(?:Error|ERROR|FATAL|CRITICAL):\s*(.+)", text)
    if err_match:
        return err_match.group(0)

    # Level 3: exit code / status
    exit_match = re.search(
        r"(?:exit code\s*|status\s*|returned\s*)(-?\d+)", text, re.IGNORECASE
    )
    if exit_match:
        return f"Process failed with exit code {exit_match.group(1)}"

    # Level 4: last 5 non-empty lines as raw keyword block
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return " ".join(lines[-5:]) if lines else text[:500]


def _read_log(source: str = "") -> str:
    """Read log from file or stdin. Caps at last 200 lines for safety."""
    if source:
        with open(source, errors='replace') as f:
            lines = f.readlines()
    else:
        print(
            "[MisakaNet] 📡 Reading error log from stdin "
            "(pipe your agent's stderr)...",
            file=sys.stderr,
        )
        lines = sys.stdin.readlines()

    if len(lines) > 200:
        lines = lines[-200:]

    return "".join(lines)


def _extract_all_signatures(log_text: str) -> list[str]:
    """Extract ALL error signatures from log (not just the last one)."""
    text = _strip_ansi(log_text)
    sigs = []

    # Level 1: all traceback exceptions
    tb_matches = re.findall(
        r"(?:[a-zA-Z0-9_]+Error|Exception|RuntimeError|Fault):\s*.+", text
    )
    sigs.extend(tb_matches)

    # Level 2: ERROR / FATAL / CRITICAL markers
    err_matches = re.findall(
        r"(?:^|\n)(?:\[?\s*(?:Error|ERROR|FATAL|CRITICAL)\s*\]?):\s*(.+)", text
    )
    sigs.extend([f"ERROR: {m.strip()}" for m in err_matches])

    # Level 3: exit codes
    exit_match = re.search(
        r"(?:exit code\s*|status\s*|returned\s*)(-?\d+)", text, re.IGNORECASE
    )
    if exit_match:
        sigs.append(f"Process failed with exit code {exit_match.group(1)}")

    # Fallback: if nothing found, use raw last lines
    if not sigs:
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        sigs.append(" ".join(lines[-5:]) if lines else text[:500])

    # Deduplicate while preserving order
    seen = set()
    return [s for s in sigs if not (s in seen or seen.add(s))]


def heal(raw_log: str, write_fixtures: bool = False):
    """Diagnose error log: extract signatures → search lessons → coverage report.

    Unmatched signatures are only written to tests/fixtures/openclaw when
    ``write_fixtures=True`` (opt-in via ``--heal --write``) — audit 2026-09-05,
    QW5: raw logs may contain credentials/PII and must never be auto-saved.
    """
    # Step 1: Extract all error signatures
    signatures = _extract_all_signatures(raw_log)
    if not signatures or all(len(s.strip()) < 3 for s in signatures):
        print("[MisakaNet] ❌ No valid error patterns captured from input.")
        return

    print(f"\n[MisakaNet] 🔍 Extracted {len(signatures)} error signature(s)")
    print("-" * 50)

    # Step 2: Search lessons using existing BM25 engine
    from misakanet.search.engine import (
        LESSONS,
        REFERENCES,
        _format_output,
        _load_docs,
        _rank_docs,
        _show_timing,
    )

    t0 = time.time()
    lessons_docs = _load_docs(LESSONS, is_lesson=True)
    ref_docs = _load_docs(REFERENCES, is_lesson=False)
    all_docs = lessons_docs + ref_docs

    # ⑤ Coverage dashboard: track matched vs unmatched signatures
    import hashlib
    import os

    matched_count = 0
    unmatched_count = 0
    fixture_dir = "tests/fixtures/openclaw"

    for sig in signatures:
        ranked = _rank_docs(sig, all_docs, titles_only=False, broad_only=True)
        has_match = ranked and ranked[0][0] > 0.15  # meaningful match threshold

        if has_match:
            matched_count += 1
            top_score = ranked[0][0]
            top_title = ranked[0][1].title
            print(f"  ✅ [{top_score:.0%}] {sig[:80]}")
            print(f"      → matched: {top_title}")
        else:
            unmatched_count += 1
            print(f"  ❌ [uncovered] {sig[:80]}")

            # ⑥ Auto-generate fixture for unmatched signatures (opt-in: --heal --write)
            sig_hash = hashlib.md5(sig.encode()).hexdigest()[:8]
            fixture_name = f"unmatched_{sig_hash}.log"
            if write_fixtures:
                os.makedirs(fixture_dir, exist_ok=True)
                fixture_path = os.path.join(fixture_dir, fixture_name)
                with open(fixture_path, "w") as f:
                    f.write(raw_log)
                print(f"      → fixture: {fixture_path}")
            else:
                print(f"      → fixture (dry-run, not written): {fixture_dir}/{fixture_name}")

    # Coverage summary
    total = matched_count + unmatched_count
    coverage = (matched_count / total * 100) if total > 0 else 0
    print()
    print(f"  📊 Coverage: {matched_count}/{total} signatures matched ({coverage:.1f}%)")
    if coverage < 50:
        print("     ⚠️  Low coverage — consider submitting lessons for the unmatched signatures")
    print("-" * 50)

    # Show top results for primary signature
    primary_sig = signatures[0]
    ranked = _rank_docs(primary_sig, all_docs, titles_only=False, broad_only=True)
    found = _format_output(ranked, titles_only=False, top_k=5,
                           mode_label=f"lessons+reference  (All {len(all_docs)} items)",
                           query=primary_sig, explain=False,
                           all_docs=all_docs)
    _show_timing(time.time() - t0, len(all_docs))

    if unmatched_count > 0:
        if write_fixtures:
            print(
                f"\n  📝 {unmatched_count} unmatched signature(s) — "
                f"auto-generated fixtures in {fixture_dir}/"
            )
            print("     Submit a lesson to improve coverage:")
            print(
                f"     python3 scripts/queue_lesson.py -t 'your title' -d openclaw "
                f"-f {fixture_dir}/unmatched_*.log"
            )
        else:
            print(
                f"\n  📝 {unmatched_count} unmatched signature(s) — "
                "dry-run, no fixtures written."
            )
            print("     Re-run with --heal --write to save fixtures, then submit a lesson:")
            print(
                f"     python3 scripts/queue_lesson.py -t 'your title' -d openclaw "
                f"-f {fixture_dir}/unmatched_*.log"
            )
    elif found:
        print("\n  ✅ All signatures covered by swarm knowledge.")
        print("     💡 Contribute back if you applied a new fix:")
        print("        python3 scripts/queue_lesson.py -t 'your title' -d <domain> 'content...'")

    print()
