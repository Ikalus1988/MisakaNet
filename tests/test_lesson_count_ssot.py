#!/usr/bin/env python3
"""Lesson-count SSOT invariants (2026-09-12).

Background — the failure these tests exist to prevent
----------------------------------------------------
The first SSOT attempt (`update_lessons_json.refresh_lesson_count_markers`,
audit QW6) replaced a ``{{LESSONS_COUNT}}`` placeholder with the literal number.
That *consumes* the placeholder, so the second run matched nothing and every
managed count silently froze at its first materialization:

    README.md        "310+ failure lessons"
    ARCHITECTURE.md  "358+ .md files"
    docs/index.html  "435 indexed failure-recovery lessons"
                     (<meta description> + og:description — the copy Google and
                      social cards show)
    docs/search/…    "249 indexed failure-recovery lessons"

The replacement registry (`scripts/sync_lesson_count.py`) is idempotent: each
surface is a regex whose numeric group is re-matched on every run. Two bugs found
while building it are pinned here as well: a pattern that cannot match its own
output (so the second run reports "reworded"), and per-row writes onto a file
clobbering the earlier rows (only the last row survived on disk).
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import sync_lesson_count as slc  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "sync_lesson_count.py"

# Two fixture rows aimed at the same file, mirroring docs/index.html (4 rows).
_TAGLINE = slc.Site("README.md", r"(?P<n>\d{2,4})\+ failure lessons",
                    "{n}+ failure lessons", "fixture tagline")
_BODY = slc.Site("README.md", r"(?P<n>\d{2,4}) lessons in the index",
                 "{n} lessons in the index", "fixture body line")


def test_repo_count_surface_is_consistent():
    """The gate: every managed surface == data/lessons.json, nothing reworded."""
    problems = slc.stale_entries(slc.canonical_count(REPO), root=REPO)
    assert problems == [], (
        "lesson counts drifted from data/lessons.json:\n  - "
        + "\n  - ".join(problems)
        + "\nFix: python3 scripts/sync_lesson_count.py"
    )


def test_registry_patterns_are_idempotent_fixed_points():
    """Every registered row must still match the text it just wrote."""
    count = slc.canonical_count(REPO)
    for site in slc.SITES:
        text = (REPO / site.path).read_text(encoding="utf-8")
        once, first = site.compiled().subn(site.replace.format(n=count), text)
        assert first >= site.min_matches, f"{site.path}: row matched nothing"

        twice, _ = site.compiled().subn(site.replace.format(n=count), once)
        assert twice == once, f"{site.path}: rewriting is not a fixed point"

        mutated, again = site.compiled().subn(site.replace.format(n=count + 1), once)
        assert again >= site.min_matches, (
            f"{site.path}: a /newer/ count no longer matches the pattern — this "
            "is the write-once bug all over again"
        )
        assert str(count + 1) in mutated, f"{site.path}: newer count not written"


def test_sync_reruns_with_a_new_count(tmp_path):
    """Regression: the old placeholder mechanism could only ever run once."""
    readme = tmp_path / "README.md"
    readme.write_text("MisakaNet searches 310+ failure lessons.\n", encoding="utf-8")

    _, errors = slc.sync_all(400, root=tmp_path, sites=(_TAGLINE,))
    assert errors == []
    assert "400+ failure lessons" in readme.read_text(encoding="utf-8")

    _, errors = slc.sync_all(500, root=tmp_path, sites=(_TAGLINE,))
    assert errors == []
    assert "500+ failure lessons" in readme.read_text(encoding="utf-8")


def test_several_rows_on_one_file_all_survive(tmp_path):
    """Regression: writing each row from the scan-time text clobbered the rest."""
    readme = tmp_path / "README.md"
    readme.write_text(
        "MisakaNet searches 310+ failure lessons. 999 lessons in the index.\n",
        encoding="utf-8")

    changes, errors = slc.sync_all(400, root=tmp_path, sites=(_TAGLINE, _BODY))
    assert errors == [] and changes
    text = readme.read_text(encoding="utf-8")
    assert "400+ failure lessons" in text
    assert "400 lessons in the index" in text


def test_reworded_sentence_is_a_hard_error(tmp_path):
    """A managed surface that stops matching must fail, never be skipped."""
    (tmp_path / "README.md").write_text("MisakaNet has a lot of lessons.\n",
                                        encoding="utf-8")

    changes, errors = slc.sync_all(400, root=tmp_path, sites=(_TAGLINE,))
    assert not any("README.md" in change for change in changes)
    assert errors and "README.md" in errors[0] and "expected ≥1" in errors[0]

    problems = slc.stale_entries(400, root=tmp_path, sites=(_TAGLINE,))
    assert any("expected ≥1" in problem for problem in problems)


def test_stale_value_is_reported_with_its_line(tmp_path):
    (tmp_path / "README.md").write_text(
        "line one\nMisakaNet searches 310+ failure lessons.\n", encoding="utf-8")

    problems = slc.stale_entries(400, root=tmp_path, sites=(_TAGLINE,))
    assert any(problem.startswith("README.md:2:") for problem in problems), problems


def test_cli_check_passes_on_this_repo():
    # PYTHONIOENCODING: the CLI prints ✅/❌, and on Windows a pipe defaults to the
    # locale codec (cp1252) — the child would die with UnicodeEncodeError and this
    # gate would look red for a reason that has nothing to do with counts.
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run([sys.executable, str(SCRIPT), "--check"],
                          cwd=REPO, capture_output=True, text=True, env=env)
    assert proc.returncode == 0, proc.stdout + proc.stderr


# ── trust vocabulary on public surfaces ─────────────────────────────────────
# docs/trust-semantics.md: "indexed" for scale claims, "verified" only for lessons
# fact-checked against source material. The registry listing (server.json), the
# agent-discovery documents, the npm/codex manifests and the README had all drifted
# into "N verified failure lessons" — the registry would have republished that
# claim with 2.29.0 (found 2026-09-12, minutes before the publish).
PUBLIC_SURFACES = (
    "server.json",
    "glama.json",
    "README.md",
    "package.json",
    ".codex-plugin/plugin.json",
    "docs/index.html",
    "docs/llms.txt",
    "docs/.well-known/llms.txt",
    "docs/.well-known/mcp.json",
    "docs/.well-known/agent.json",
    "docs/.well-known/agent-card.json",
)
FORBIDDEN_TRUST_CLAIM = re.compile(r"verified (failure|debugging) lessons?", re.IGNORECASE)


def test_public_surfaces_do_not_claim_verified_lessons():
    offenders = []
    for rel in PUBLIC_SURFACES:
        text = (REPO / rel).read_text(encoding="utf-8")
        for match in FORBIDDEN_TRUST_CLAIM.finditer(text):
            offenders.append(f"{rel}: {match.group(0)!r}")
    assert offenders == [], (
        "these surfaces claim lessons are 'verified' without fact-checking them "
        "(use 'indexed' / 'evidence-rated'):\n  - " + "\n  - ".join(offenders)
    )


def test_registry_listing_stays_publishable():
    """The MCP registry rejects a >100-char description (HTTP 422)."""
    server = json.loads((REPO / "server.json").read_text(encoding="utf-8"))
    assert len(server["description"]) <= 100, len(server["description"])
    assert "verified" not in server["description"].lower()
    assert server["version"] == server["packages"][0]["version"], (
        "server.json registry version and its pypi package entry must agree (R3)"
    )
