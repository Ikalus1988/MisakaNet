#!/usr/bin/env python3
"""Heal/diagnose mode for the MisakaNet CLI.

Extracted from search_knowledge.py (audit 2026-09-05, T1.1 stage 1) — the
CLI entry keeps dispatching to :func:`heal` via a module-level import.

`--heal` parses error logs, searches lessons and reports coverage. Fixtures
for unmatched signatures are opt-in (``--write``) and carry only the matched
signature — never the raw log body, which may hold credentials/PII and must
not be auto-persisted (audit QW5, #1775).
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


#: Credential shapes that must never reach a fixture file. Same four families the repository's
#: publication scanner uses (`scripts/check_published_secrets.py`), trimmed to the prefix + length
#: test it applies, because that scanner deliberately does not read `tests/fixtures/**` and a
#: fixture is one `git add` away from being published (#1775).
_SECRET_SHAPES = (
    re.compile(r"\bmcp_[A-Za-z0-9_-]{32}\b"),
    re.compile(r"\bghp_[A-Za-z0-9]{36}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{82}\b"),
    re.compile(r"\bsk-[A-Za-z0-9]{48}\b"),
)


def _looks_like_credential(text: str) -> bool:
    """True when `text` carries something shaped like a credential."""
    return any(pattern.search(text) for pattern in _SECRET_SHAPES)


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
    ``write_fixtures=True`` (opt-in via ``--heal --write``), and the fixture
    holds the extracted signature only — the raw log body is never written,
    because it may contain credentials/PII (audit 2026-09-05, QW5; #1775).
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
            sig_hash = hashlib.sha256(sig.encode()).hexdigest()[:8]
            fixture_name = f"unmatched_{sig_hash}.log"
            if write_fixtures:
                os.makedirs(fixture_dir, exist_ok=True)
                fixture_path = os.path.join(fixture_dir, fixture_name)
                # Only the signature reaches the fixture — never the raw log body. The module's
                # own contract (audit QW5) is that raw logs may hold credentials/PII and must not
                # be auto-persisted; a signature hash as the *filename* does not make the *content*
                # safe. The signature is the extracted error line (what a lesson needs), and this
                # file is one `git add` away from the repository (#1775).
                #
                # One line is not proof of safety: an error line can quote the token that caused
                # it (`401 with Authorization: Bearer …`, a curl echo, a config dump). A fixture
                # whose whole purpose is to be committed later must refuse those rather than write
                # them, so the shape test decides.
                if _looks_like_credential(sig):
                    print("      → fixture skipped: the signature carries a credential-shaped token")
                    continue
                with open(fixture_path, "w") as f:
                    f.write(sig + "\n")
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
