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


# Surfaces that quoted the node count until 2026-09-26, with the sentence each carried. The
# registry that kept them consistent is gone (the number is not a measurement of anything a reader
# would take it for — see the `sync_lesson_count.py` docstring), so what has to be gated now is the
# opposite direction: it must not come back, on a surface or in a dictionary.
_FORMER_NODE_SURFACES = (
    ("docs/llms.txt", r"\b\d[\d,]*\+?\s+registered nodes\b"),
    ("docs/.well-known/llms.txt", r"\b\d[\d,]*\+?\s+registered nodes\b"),
    ("README.zh-CN.md", r"\|\s*🌐\s*Nodes\s*\|"),
    ("README.ja.md", r"\|\s*登録ノード\s*\|"),
    ("docs/index.html", r'id="total-nodes"'),
)


def test_the_node_count_is_not_published_anywhere():
    """The inverse gate for issue #1683's metric, retired 2026-09-26.

    A node count was published in five places and synced from `data/counter.json`. It is not a
    population: `current` is a monotonic allocation counter (the first node is Misaka10001, nothing
    is ever removed, and an anonymous caller gets a fresh node per call), so it grows with our own
    automation and cannot show usage. Renaming the label twice did not fix that; removing the number
    did. This test is what keeps it removed — a re-added line here would otherwise be invisible
    until someone read the same page in two languages.
    """
    found = []
    for rel, pattern in _FORMER_NODE_SURFACES:
        text = (REPO / rel).read_text(encoding="utf-8")
        if re.search(pattern, text):
            found.append(rel)
    assert not found, f"the node count is published again in: {found}"


def test_the_node_metric_is_gone_from_the_registry():
    """No metric, no sites, no CLI value — otherwise the gate above has a writer again."""
    assert not hasattr(slc, "NODE_SITES"), "sync_lesson_count still registers node surfaces"
    assert not hasattr(slc, "canonical_nodes"), "sync_lesson_count still reads the counter"
    proc = subprocess.run([sys.executable, str(SCRIPT), "--check", "--metric", "nodes"],
                          capture_output=True, text=True)
    assert proc.returncode == 2, (
        f"`--metric nodes` is still an accepted value (exit {proc.returncode}); a choice nothing "
        f"implements invites the metric back:\n{proc.stderr[-300:]}"
    )
    assert "invalid choice" in proc.stderr, proc.stderr[-300:]


def _registries():
    """(sites, canonical value, owns-count-file) for every managed metric."""
    return (
        (slc.SITES, slc.canonical_count(REPO), True),
        (slc.DOMAIN_SITES, slc.canonical_domains(REPO), False),
    )


def test_registry_patterns_are_idempotent_fixed_points():
    """Every registered row must still match the text it just wrote.

    Runs over every metric: the domain rows carry a full-width unit ("44 个") and a
    normalisation step, which is where a pattern that cannot match its own output would hide.
    """
    for sites, count, _ in _registries():
        for site in sites:
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


def test_a_metric_without_its_own_count_file_does_not_write_the_lesson_count_file():
    """Guarding the `write_count_file` flag both ways (found by the gate, 2026-09-15).

    The first version of a second metric reused `sync_all` unchanged and overwrote
    docs/_lessons_count.txt with its own count — a lesson-count surface silently holding a different
    measure. The flag exists for that; the lesson metric must keep writing the file. This used the
    node metric until it was retired (2026-09-26), and runs on the domain metric now, which is the
    remaining metric that owns no count file.
    """
    changes, errors = slc.sync_all(slc.canonical_domains(REPO), root=REPO, sites=slc.DOMAIN_SITES,
                                   dry_run=True, write_count_file=False)
    assert errors == []
    assert not any("_lessons_count.txt" in change for change in changes), changes

    lesson_changes, _ = slc.sync_all(slc.canonical_count(REPO), root=REPO,
                                     dry_run=True, write_count_file=True)
    # already consistent: the file matches, so no change is reported — the point is
    # only that the lesson metric is still the one that owns that path.
    assert not any("_lessons_count.txt" in change for change in lesson_changes), lesson_changes


def test_cli_checks_more_than_the_lesson_metric(tmp_path):
    """`--check` must fail on a stale domain surface too, not only on a stale lesson surface.

    Same shape as the retired `--metric nodes` test: a second metric that only the Python API can
    check is a metric the CI gate cannot see.
    """
    (tmp_path / "data").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "data" / "lessons.json").write_text("[]", encoding="utf-8")
    (tmp_path / "docs" / "install").mkdir()
    (tmp_path / "docs" / "install" / "index.html").write_text(
        "99 domains of failure knowledge\n", encoding="utf-8")

    stale = subprocess.run([sys.executable, str(SCRIPT), "--check", "--metric", "domains",
                            "--root", str(tmp_path)],
                           capture_output=True, text=True)
    assert stale.returncode == 1, stale.stdout + stale.stderr
    assert "domain-count SSOT drift" in stale.stderr, stale.stderr


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
FORBIDDEN_TRUST_CLAIM = re.compile(
    # The hyphenated "failure-recovery" form slipped past the original
    # alternation: README.md advertised "385+ **verified failure-recovery
    # lessons**" — stale count *and* forbidden vocabulary — while this test
    # stayed green (found 2026-09-14, in the very publish path it guards).
    r"verified (?:failure|debugging)(?:-recovery)? lessons?",
    re.IGNORECASE,
)


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


def test_domain_count_normalises_quotes_and_case(tmp_path):
    """Issue #1687: `devops`, `"devops"` and `DevOps` are one domain, not three.

    The badge counted raw strings, so it reported 69 for a corpus whose normalised vocabulary
    is 61 — and neither number was derivable from anything a reader could check. The definition
    is now the normalised frontmatter value, and this pins the normalisation.
    """
    contrib = tmp_path / "lessons" / "contrib"
    contrib.mkdir(parents=True)
    for index, domain in enumerate(["devops", '"devops"', "DevOps", "  ops  "]):
        (contrib / f"lesson-{index}.md").write_text(
            f"---\ndomain: {domain}\n---\n\n# t\n", encoding="utf-8")
    (contrib / "README.md").write_text("---\ndomain: not-a-lesson\n---\n", encoding="utf-8")

    assert slc.canonical_domains(tmp_path) == 2, "devops×3 collapses to one; ops is a second"


# ── the two numbers in one sentence must not be confused ─────────────────────
# 2026-09-15: the install page carries both counts in a single line —
# "393+ lessons across 55 domains". The lesson-count row referenced the domain
# number as `\g<1>`, but `_COUNT` is `(?P<n>\d{2,4})` and a *named* group is also
# a numbered one, so `\g<1>` was the lesson count: the daily `update-lessons`
# run rewrote the sentence to "393+ lessons across 393 domains", committed it,
# and left `main` failing test_cli_check_passes_on_this_repo. Both numbers looked
# plausible, which is why nothing else noticed.
_INSTALL_PAGE = "docs/install/index.html"
_TWO_NUMBERS = re.compile(r"(\d{2,4})\+ lessons across (\d{2,4}) domains")


def test_lesson_count_row_preserves_the_domain_count():
    """A lesson-count rewrite must leave the domain number alone."""
    rows = [site for site in slc.SITES if site.path == _INSTALL_PAGE]
    assert rows, f"no lesson-count row manages {_INSTALL_PAGE}"

    text = (REPO / _INSTALL_PAGE).read_text(encoding="utf-8")
    before = _TWO_NUMBERS.search(text)
    assert before, f"{_INSTALL_PAGE} no longer carries the two-number sentence"

    # A count that differs from the domain count, so a mixed-up backreference is
    # visible rather than coincidentally equal (393 vs 393 is what shipped).
    rewritten = text
    for row in rows:
        rewritten, _ = row.compiled().subn(row.replace.format(n=1234), rewritten)

    after = _TWO_NUMBERS.search(rewritten)
    assert after, f"the sentence stopped matching its own output:\n{rewritten}"
    assert after.group(1) == "1234", "the lesson number was not rewritten"
    assert after.group(2) == before.group(2), (
        f"the domain number was rewritten by a lesson-count row: "
        f"{before.group(2)} -> {after.group(2)}"
    )


def test_domain_count_row_preserves_the_lesson_count():
    """And the mirror case: the domain row must not touch the lesson number."""
    rows = [site for site in slc.DOMAIN_SITES if site.path == _INSTALL_PAGE]
    assert rows, f"no domain-count row manages {_INSTALL_PAGE}"

    text = (REPO / _INSTALL_PAGE).read_text(encoding="utf-8")
    before = _TWO_NUMBERS.search(text)
    assert before, f"{_INSTALL_PAGE} no longer carries the two-number sentence"

    rewritten = text
    for row in rows:
        rewritten, _ = row.compiled().subn(row.replace.format(n=777), rewritten)

    after = _TWO_NUMBERS.search(rewritten)
    assert after, f"the sentence stopped matching its own output:\n{rewritten}"
    assert after.group(2) == "777", "the domain number was not rewritten"
    assert after.group(1) == before.group(1), (
        f"the lesson number was rewritten by a domain-count row: "
        f"{before.group(1)} -> {after.group(1)}"
    )


# ── The root `llms.txt`: a pointer, not a second copy ────────────────────────────────────────────────
# It is the file an agent gets from `raw.githubusercontent.com/.../llms.txt`, and for months it was a
# second, unmanaged copy of the served `docs/llms.txt`. It went stale invisibly (317 lessons against a
# corpus of 393), advertised three `misaka://` resources the server does not implement, and named the
# wrong package under "MCP Server" (`misakanet-core`, the library, instead of `misakanet`, which ships
# the stdio server). None of that could fail a check, because no check read the file.
#
# The resolution was to stop duplicating: the root file now points at the managed copy. These two rules
# keep it a pointer.

ROOT_LLMS = "llms.txt"


def test_root_llms_points_at_the_managed_copy():
    text = (REPO / ROOT_LLMS).read_text(encoding="utf-8")
    assert "docs/llms.txt" in text or "misakanet.org/llms.txt" in text, (
        f"{ROOT_LLMS} no longer points at a managed copy of the agent description. Whatever it says "
        "instead is a second source of truth with nobody maintaining it — which is exactly how it came "
        "to advertise 317 lessons and three resources that do not exist."
    )


def test_root_llms_carries_no_count_of_its_own():
    """A number here would be a fact with no writer — the defect this whole module exists to prevent.

    Only counts read as *measurements* are forbidden (`N lessons`, `N indexed`, `N nodes`, `N domains`);
    a year or a port is not a claim about the corpus, so the regex stays narrow on purpose.
    """
    text = (REPO / ROOT_LLMS).read_text(encoding="utf-8")
    claims = re.findall(
        r"\b\d{2,5}\+?\s*(?:indexed\s+)?(?:lessons?|failure[- ]lessons?|nodes?|domains?)\b",
        text, re.IGNORECASE)
    assert not claims, (
        f"{ROOT_LLMS} states a corpus count of its own: {claims}. Counts are managed by "
        "`scripts/sync_lesson_count.py` for the files listed in its SITES registry; this file is not "
        "one of them and must stay a pointer."
    )
