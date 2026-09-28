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
    # The badge outlived the number by two days and nothing looked at it (#2313 retired the metric on
    # 2026-09-26; this line was still there on 2026-09-28, reading `badges/nodes.json` — a file that
    # stopped being written the moment `canonical_nodes` was deleted, so the image showed a frozen
    # 4,926 to every reader of the Chinese README). A *stale* published number is worse than a
    # missing one, and an `<img>` whose data source has no writer is exactly how it happens.
    ("README.zh-CN.md", r"badges/nodes\.json"),
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


# ── the registry may shrink, never grow ──────────────────────────────────────
# Three files, eight rows (2026-09-28). The count of managed surfaces is itself the defect the previous
# shape grew into: every incident ("this page says 385+", "this manifest says 320+") was answered by
# registering one more file, until 38 rows across 24 files meant the daily job rewrote the corpus total
# into places that only ever quoted it. These caps are what stops the next incident from being answered
# the same way — the fix is a badge, a pointer, or dropping the number, and if a new surface genuinely
# cannot be read without a literal, raise the cap *here*, where the reason has to be written down.
MAX_MANAGED_ROWS = 8
MAX_MANAGED_FILES = 3


def test_the_managed_registry_stays_small():
    """The surface count is capped, so "just register it" is not the default answer anymore."""
    rows = slc.SITES + slc.DOMAIN_SITES
    files = {site.path for site in rows}
    assert len(rows) <= MAX_MANAGED_ROWS, (
        f"{len(rows)} managed count rows (cap {MAX_MANAGED_ROWS}): "
        f"{sorted(site.path for site in rows)}"
    )
    assert len(files) <= MAX_MANAGED_FILES, (
        f"{len(files)} managed count files (cap {MAX_MANAGED_FILES}): {sorted(files)}"
    )


# ── and a de-numbered surface must not quietly get its number back ───────────
# The surfaces that left the registry are still the ones a reader sees first, so "we removed the row" is
# only half a fix: nothing would fail if someone wrote the total back into the README tagline, which is
# exactly the drift that created the registry. These files carry no historical snapshots (ROADMAP does,
# so it is checked positively further down), which is what lets the pattern be a plain corpus-count
# search instead of a per-sentence allowlist.
_DE_NUMBERED_SURFACES = (
    "README.md",
    "README.zh-CN.md",
    "README.ja.md",
    "ARCHITECTURE.md",
    "JOIN.md",
    "docs/skill.md",
    "docs/mcp-quickstart.md",
    "docs/search/index.html",
    "docs/integrations/README.md",
    "docs/integrations/cursor.md",
    "docs/integrations/continue.md",
    "docs/integrations/claude-code.md",
    "docs/integrations/gemini-cli.md",
    "docs/install/index.html",
    "docs/worker-bm25-search.md",
    "docs/json-ld-schema.md",
    ".github/ISSUE_TEMPLATE/config.yml",
    ".github/ISSUE_TEMPLATE/ai-bounty-template.md",
    "docs/.well-known/mcp.json",
    "docs/.well-known/agent.json",
    "docs/.well-known/agent-card.json",
    "docs/.well-known/glama.json",
)

# `(?<![\w%])` keeps URL-encoded spaces out of it: `promotional/search%20lesson.gif` in the READMEs reads
# as "20lesson" to a naive `\b\d+…lessons?\b` and would fail this test on an image path.
_CORPUS_COUNT_CLAIM = re.compile(
    r"(?<![\w%])\d{2,5}\+?\s*(?:indexed\s+|verified\s+)?"
    r"(?:failure[-\s]?recovery\s+|failure\s+|debugging\s+)?lessons?\b"
    r"|(?<![\w%])\d{2,5}\+?\s*(?:curated\s+|个)?\s*domains?\b"
    r"|(?<![\w%])\d{2,5}\s*条[^|\n]{0,12}(?:经验|课程)"
    r"|(?<![\w%])\d{2,5}\s*件[^|\n]{0,12}レッスン"
    r"|(?<![\w%])\d{2,5}\s*个[^|\n]{0,6}(?:领域|域名)"
    r"|\|\s*📚 Lessons \|\s*\d",
    re.IGNORECASE,
)


def test_de_numbered_surfaces_do_not_grow_a_count_back():
    offenders = []
    for rel in _DE_NUMBERED_SURFACES:
        text = (REPO / rel).read_text(encoding="utf-8")
        for match in _CORPUS_COUNT_CLAIM.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            offenders.append(f"{rel}:{line}: {match.group(0)!r}")
    assert offenders == [], (
        "these surfaces point at the count now, they do not quote it (see the module docstring of "
        "scripts/sync_lesson_count.py, 'Count surfaces: three, not twenty-four'):\n  - "
        + "\n  - ".join(offenders)
        + "\nUse the shields dynamic badge (data branch badges/lessons.json) in rendered markdown, or "
        "name the source in prose. If a surface genuinely needs the literal, register it in SITES and "
        "raise MAX_MANAGED_ROWS with the reason."
    )


# ROADMAP.md is excluded above because it *is* a dated record: its 2026-08-22 adjudication table quotes
# the numbers it adjudicated (377/393/411) on purpose, and this repo keeps history rather than rewriting
# it. So its live block is gated positively — the current-numbers section has to point at the badges.
_ROADMAP_CURRENT_BLOCK = re.compile(r"(?m)^###\s+当前数字")


def test_roadmap_current_numbers_point_at_the_badges():
    text = (REPO / "ROADMAP.md").read_text(encoding="utf-8")
    start = _ROADMAP_CURRENT_BLOCK.search(text)
    assert start, "ROADMAP.md lost its '当前数字' section — moving it means updating this reader"
    rest = text[start.end():]
    end = rest.find("\n### ")
    section = rest if end == -1 else rest[:end]
    for badge in ("badges/lessons.json", "badges/domains.json"):
        assert badge in section, (
            f"ROADMAP's current-numbers block no longer reads {badge}: either the number is back in "
            "the bytes, or the badge was dropped without a replacement"
        )


# ── the retired two-number sentence, kept as a forward guard ─────────────────
# 2026-09-15: the install page carried both counts in one line — "393+ lessons across 55 domains" — and
# its lesson-count row referenced the domain number positionally. `_COUNT` is `(?P<n>\d{2,4})`, and a
# *named* group is also a numbered one, so `\g<1>` was the lesson count: the daily `update-lessons` run
# rewrote the sentence to "393+ lessons across 393 domains", committed it, and left `main` failing while
# both numbers looked plausible. The sentence is gone (2026-09-28), so it cannot recur in that file — but
# "reference a named group by number" is the transferable mistake and one row is all it needs, so it is a
# lint over the registry rather than a test over one page.
def test_registry_rows_reference_named_groups_by_name_only():
    for sites, *_ in _registries():
        for site in sites:
            for name, index in site.compiled().groupindex.items():
                assert f"\\g<{index}>" not in site.replace, (
                    f"{site.path}: the replace template references group {index} positionally, and "
                    f"that group is named {name!r}. Numbers are not stable — a later edit to the "
                    "pattern (adding a capture around some prose) silently repoints them, which is how "
                    "'393+ lessons across 393 domains' shipped."
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


# ── the README's 当前数据 table: two of its three rows had no writer ──────────
# Measured 2026-09-28. `README.zh-CN.md`'s 当前数据 table read `| 🎤 Network Voices | 5 条 |` and
# `| 📡 Feed Items | 11 条 |`. The sources are `docs/community/voices.json` and `docs/data/feed.json`,
# and on that day both numbers happened to be **right** — which is the whole reason nobody had noticed
# the class rather than the instance: nothing wrote them, so the next voice or feed item would leave the
# table silently behind, and the row above them (`📚 Lessons`) had already been answered with a live
# badge. The same file answers its corpus total with a pointer too ("当前条数见顶部「知识」徽章").
#
# Sibling of `_DE_NUMBERED_SURFACES` (that rule is about corpus counts); this one is about the table
# that lists counts next to two other live numbers. `\d+ 条` is deliberately the only shape it forbids:
# the table's third row names domains, not counts.
_README_TABLE_COUNT = re.compile(r"\|\s*[^|\n]*\|\s*\d+\s*条\s*\|")


def readme_table_counts(text: str) -> list[str]:
    """Hand-written `N 条` cells in a markdown table — the shape the README's data table must not use."""
    return [line.strip() for line in text.splitlines() if _README_TABLE_COUNT.search(line)]


def test_the_readme_data_table_carries_no_hand_written_count():
    text = (REPO / "README.zh-CN.md").read_text(encoding="utf-8")
    offenders = readme_table_counts(text)
    assert not offenders, (
        "a count in this table has no writer, so it goes stale unobserved — point at the source "
        f"(`docs/community/voices.json`, `docs/data/feed.json`) instead: {offenders}"
    )


def test_the_readme_table_rule_notices_a_count_coming_back():
    """Guard: the rule above reads the real repository, so its failure mode needs a fixture."""
    assert readme_table_counts("| 🎤 Network Voices | 见 [voices.json](docs/community/voices.json) |") == [], \
        "the pointer form must pass, or the rule is unusable"
    assert readme_table_counts("| 🎤 Network Voices | 5 条 |") == ["| 🎤 Network Voices | 5 条 |"], \
        "a hand-written count must be reported"
    assert readme_table_counts("| 📡 Feed Items | 11  条 |") != [], "spacing must not defeat the rule"
    # A non-count cell that merely contains a number (a year, a port) is not a claim about the corpus.
    assert readme_table_counts("| 📚 Lessons | 418 lessons, canonical |") == [], (
        "the rule is about `N 条` cells; a corpus count is the `_DE_NUMBERED_SURFACES` rule's business")
