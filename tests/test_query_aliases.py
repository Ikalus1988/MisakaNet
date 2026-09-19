"""Tests for the query alias table (data/query-aliases.json) and the expansion CLI.

The alias table is a reviewed vocabulary like data/domains.json: these tests are the
CI half of that review, and `scripts/expand_query.py --check` is the other half.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import expand_query  # noqa: E402

TABLE = REPO / "data" / "query-aliases.json"
KINDS = {"zh-en", "error-variant", "tool-variant", "product-variant", "abbrev", "typo"}


@pytest.fixture(scope="module")
def table() -> dict:
    return expand_query.load_table(TABLE)


@pytest.fixture(scope="module")
def lesson_corpus() -> str:
    return "\n".join(p.read_text(encoding="utf-8", errors="replace")
                     for p in sorted((REPO / "lessons").rglob("*.md")))


# ── schema + table invariants ────────────────────────────────────────────────

def test_table_file_exists_and_parses(table):
    assert TABLE.is_file()
    assert isinstance(table["schema"], dict)
    assert table["schema"]["version"] >= 1
    assert isinstance(table["kinds"], dict) and table["kinds"]


def test_every_declared_kind_is_documented_and_used(table):
    assert KINDS <= set(table["kinds"])
    for kind, spec in table["kinds"].items():
        assert spec.get("desc"), f"kind {kind} has no description"
        assert spec.get("direction") in ("one-way", "two-way")
        assert 0 < float(spec.get("weight", 0)) <= 1
        assert isinstance(spec.get("replace"), bool)


def test_entry_count_is_within_the_reviewed_range(table):
    """A hand-reviewed table, not a generated one: big enough to matter, small
    enough to read in one sitting.

    The upper bound went 150 → 200 in #1780, when the Feature #532 `_SYNONYM_MAP` was
    unified into this file: 30 of its 34 keys existed nowhere else and were migrated as
    `kind: "related"` entries (each with fresh evidence), so the count is a consequence
    of the migration rather than of new growth. The bound is a review-discipline guard,
    not a measurement — raising it again needs the same kind of justification.
    """
    assert 60 <= len(table["aliases"]) <= 200


def test_entries_have_the_required_fields(table):
    for e in table["aliases"]:
        assert e.get("alias", "").strip(), e
        assert e.get("canonical", "").strip(), e
        assert e["kind"] in table["kinds"], e
        assert isinstance(e.get("justification"), dict), e


def test_no_duplicate_aliases(table):
    seen = {}
    for e in table["aliases"]:
        key = e["alias"].strip().lower()
        assert key not in seen, f"{e['alias']!r} duplicated (already {seen.get(key)!r})"
        seen[key] = e["canonical"]


def test_no_self_maps(table):
    for e in table["aliases"]:
        assert e["alias"].strip().lower() != e["canonical"].strip().lower(), e


def test_no_entry_is_a_token_level_no_op(table):
    """If the canonical adds no new token, the entry cannot change any ranking —
    it would be pure review burden."""
    for e in table["aliases"]:
        a, c = set(expand_query.tokenize(e["alias"])), set(expand_query.tokenize(e["canonical"]))
        adds = a ^ c if expand_query.entry_defaults(table, e)["direction"] == "two-way" else c - a
        assert adds, f"{e['alias']!r} -> {e['canonical']!r} adds nothing"


def test_aliases_are_grounded_in_the_repository(table):
    """Every entry points at a real file AND its quoted sighting is really in that file,
    so a reviewer can re-run the grep the entry was built from. Typo entries may lack an
    alias sighting (a typo is absent from the corpus by definition) but still cite the
    canonical spelling they correct to."""
    for e in table["aliases"]:
        j = e["justification"]
        ev = j.get("canonical_evidence")
        assert ev, f"{e['alias']!r} has no canonical evidence"
        assert j["scope"] in ("lessons", "repo")
        labels = ["canonical_evidence"] + ([] if e["kind"] == "typo" else ["alias_evidence"])
        for label in labels:
            ev = j.get(label)
            assert ev, f"{e['alias']!r} has no {label}"
            path = REPO / ev["file"]
            assert path.is_file(), ev
            # …and git must actually track it. A file that only exists on the author's machine
            # (a gitignored scratch directory, say) is not evidence a reviewer can check: this
            # test passed locally and failed in CI for exactly that reason, which is why the
            # assertion below is a subprocess and not a `Path.exists()`.
            tracked = subprocess.run(
                ["git", "ls-files", "--error-unmatch", "--", ev["file"]],
                cwd=REPO, capture_output=True, text=True)
            assert tracked.returncode == 0, (
                f"{e['alias']!r}: {label} cites {ev['file']!r}, which git does not track — "
                "evidence has to be reproducible from a clean checkout")
            if ev.get("quote"):
                haystack = path.read_text(encoding="utf-8", errors="replace").lower()
                assert ev["quote"].lower() in haystack, f"{e['alias']!r}: {label} quote is stale"


# ── expansion behaviour ─────────────────────────────────────────────────────

# Files whose contents are *generated*, so they cannot serve as evidence: the thing that writes them
# is free to reword, reorder or drop any line, and the citation silently rots.
#
# Found on 2026-09-19: three of 180 aliases cited one — two cited `lessons/index.md` and one cited
# `data/quality_scores.json`. PR #1817 rebuilds the index, and its audit went red with
# `'中文乱码': alias_evidence quote is stale` even though the alias and its canonical lesson had not
# changed. Worse, the third citation was *already* stale in a way the test could not see: it quoted a
# filename (`tts中文编码-powerhsell传参必须用txt文件.md`) that no longer exists, because the citation
# pointed at a generated file that still carried the old name. Evidence has to come from a file a
# reviewer can rely on, so it must be a source file.
GENERATED_EVIDENCE_FILES = (
    "lessons/index.md",
    "data/lessons.json",
    "data/quality_scores.json",
    "data/counter.json",
    "data/leaderboard.json",
)


def test_evidence_never_cites_a_generated_file(table):
    """A citation into a generated file is a citation that will rot without anyone editing it."""
    offenders = []
    for e in table["aliases"]:
        j = e["justification"]
        for label in ("canonical_evidence", "alias_evidence"):
            ev = j.get(label) or {}
            if ev.get("file") in GENERATED_EVIDENCE_FILES:
                offenders.append(f"{e['alias']!r} {label} -> {ev['file']}")
    assert not offenders, (
        "these aliases cite a generated file as evidence, so any regeneration of it can make the "
        "citation stale without touching the alias (this is what turned PR #1817's audit red):\n  - "
        + "\n  - ".join(offenders)
        + "\nPoint the citation at the source file instead (the lesson itself, a script, or a doc)."
    )


def test_canonical_forms_exist_in_the_corpus(table, lesson_corpus):
    """The whole point: an expansion that is not in the corpus retrieves nothing."""
    corpus_tokens = set(expand_query.tokenize(lesson_corpus))
    for e in table["aliases"]:
        for tok in expand_query.tokenize(e["canonical"]):
            assert tok in corpus_tokens, f"{e['alias']!r} -> {tok!r} is not in lessons/"


def test_canonical_forms_survive_the_worker_tokenizer(table):
    """workers/register-proxy-sw.js bm25Tokenize drops CJK and stopwords; a canonical
    that tokenizes to [] there can never be matched by the production index."""
    for e in table["aliases"]:
        assert expand_query.worker_tokens(e["canonical"]), e


def test_worker_tokenizer_matches_the_worker_implementation():
    """Values taken from the real `bm25Tokenize` in workers/register-proxy-sw.js."""
    assert expand_query.worker_tokens("如何切换识图模型") == []
    assert expand_query.worker_tokens("switch vision model") == ["switch", "vision", "model"]
    assert expand_query.worker_tokens("exit code 137") == ["exit", "code", "137"]
    assert expand_query.worker_tokens("DCO sign-off failed") == [
        "dco", "sign", "off", "failed", "signoff"]


def test_chinese_natural_language_query_expands_into_corpus_terms(table, lesson_corpus):
    """The headline gap: a Chinese question is invisible to the production tokenizer
    (zero query terms) but must come out of expansion as real corpus terms."""
    query = "如何切换识图模型"
    assert expand_query.worker_tokens(query) == []          # why the query returns nothing today
    rep = expand_query.expand(query, table)
    assert rep["expanded"], "expansion produced nothing"
    assert rep["changed"] is True
    corpus_tokens = set(expand_query.tokenize(lesson_corpus))
    added = [t["term"] for t in rep["added_terms"]]
    assert added, rep
    for term in added:
        assert term in corpus_tokens, f"expanded term {term!r} is not in the corpus"
    assert "switch" in added and "model" in added
    # and the expanded query now reaches the worker's BM25 index
    assert expand_query.worker_tokens(rep["expanded"])


def test_expansion_is_bidirectional_safe(table, lesson_corpus):
    """For a two-way entry the reverse direction must be just as expandable, and for
    a one-way entry expanding the canonical must not pull the alias back in — that
    asymmetry is what keeps a broad term from being polluted by a narrow variant."""
    checked = 0
    for e in table["aliases"]:
        entry = expand_query.entry_defaults(table, e)
        pair = (e["alias"], e["canonical"])
        forward = expand_query.expand(e["alias"], table)
        assert any((m["alias"], m["canonical"]) == pair for m in forward["matched"]), e
        added = [t["term"] for t in forward["added_terms"]]
        assert added, f"{e['alias']!r} expands into nothing"
        # The reverse direction is the dangerous one: a broad canonical pulling a
        # narrow alias into every query that mentions it.
        reverse = expand_query.expand(e["canonical"], table)
        hit = any((m["alias"], m["canonical"]) == pair for m in reverse["matched"])
        back_terms = [t["term"] for t in reverse["added_terms"] if t["from"] == e["alias"]]
        if entry["direction"] == "two-way":
            assert hit, f"two-way entry {e['alias']!r} does not expand backwards"
            assert back_terms, e
        else:
            # One-way means the canonical side must not pull the alias back in. It may
            # still *contain* the alias as a substring (`crashloop` inside
            # `crashloopbackoff`), which is harmless as long as nothing is injected.
            assert not back_terms, f"one-way entry {e['alias']!r} expanded backwards: {back_terms}"
        checked += 1
    assert checked == len(table["aliases"])


def test_expansion_never_re_adds_a_term_already_in_the_query(table):
    rep = expand_query.expand("内存泄漏 memory leak", table)
    assert "memory" not in [t["term"] for t in rep["added_terms"]]
    assert "leak" not in [t["term"] for t in rep["added_terms"]]


def test_expansion_cap_limits_added_terms(table):
    rep = expand_query.expand("内存不足 权限不足 磁盘空间不足 请求超时", table, max_expansions=1)
    assert len(rep["added_terms"]) == 1
    assert rep["added_terms_suppressed"] >= 1


def test_longest_alias_wins(table):
    """`识图模型` must beat the bare `模型`, otherwise the query loses the specific term."""
    rep = expand_query.expand("如何切换识图模型", table)
    assert "识图模型" in [m["alias"] for m in rep["matched"]]
    assert "vision" in [t["term"] for t in rep["added_terms"]]


# ── the CLI gate ───────────────────────────────────────────────────────────

def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(REPO / "scripts" / "expand_query.py"), *args],
                          capture_output=True, text=True, cwd=str(REPO))


def test_cli_check_passes_on_the_real_table():
    res = _run("--check")
    assert res.returncode == 0, res.stdout + res.stderr


def test_cli_query_prints_original_and_expanded():
    res = _run("--query", "如何切换识图模型")
    assert res.returncode == 0
    assert "original" in res.stdout and "expanded" in res.stdout
    assert "vision switch model" in res.stdout


def test_cli_list_kinds_lists_every_kind():
    res = _run("--list-kinds")
    assert res.returncode == 0
    for kind in KINDS:
        assert kind in res.stdout
    assert "entries" in res.stdout and "TOTAL" in res.stdout


@pytest.mark.parametrize("payload,fragment", [
    ('{"aliases": []}', "schema"),
    ('{"schema": {"version": 1}, "aliases": [{"alias": "a", "canonical": "a"}]}', "kinds"),
    ('{"schema": {"version": 1}, "kinds": {"zh-en": {}}, "aliases": []}', "required"),
    ('{"schema": {"version": 1}, "aliases": []}', "kinds"),
    ('{not json', "not valid JSON"),
])
def test_cli_check_fails_on_a_malformed_table(tmp_path, payload, fragment):
    bad = tmp_path / "bad.json"
    bad.write_text(payload, encoding="utf-8")
    res = _run("--check", "--table", str(bad))
    assert res.returncode != 0
    assert fragment.lower() in (res.stdout + res.stderr).lower()


def test_check_rejects_duplicate_self_map_and_dead_canonical(tmp_path, table):
    good = table["aliases"][0]
    cases = {
        "duplicate": [good, dict(good)],
        "self-map": [{"alias": "timeout", "canonical": "timeout", "kind": "error-variant",
                      "justification": {}}],
        "dead-canonical": [{"alias": "notreal", "canonical": "zzzznotacorpusterm",
                            "kind": "error-variant", "justification": {}}],
    }
    for name, entries in cases.items():
        payload = {"schema": {"version": 1}, "kinds": table["kinds"], "aliases": entries}
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        problems = expand_query.check(path)
        assert problems, f"{name} was accepted"
        res = _run("--check", "--table", str(path))
        assert res.returncode != 0, name


def test_check_reports_a_canonical_chain_loop(tmp_path, table):
    a = {"alias": "AAAA", "canonical": "timeout", "kind": "error-variant", "justification": {}}
    b = {"alias": "timeout", "canonical": "AAAA", "kind": "error-variant", "justification": {}}
    path = tmp_path / "loop.json"
    path.write_text(json.dumps({"schema": {"version": 1}, "kinds": table["kinds"],
                                "aliases": [a, b]}), encoding="utf-8")
    assert any("loops" in p for p in expand_query.check(path))


def test_table_ships_no_code_generation_step(table):
    """domains.json is hand-maintained; so is this. Nothing may rewrite it."""
    for script in (REPO / "scripts").glob("*.py"):
        text = script.read_text(encoding="utf-8", errors="replace")
        if script.name in {"expand_query.py", "eval_query_aliases.py"}:
            continue
        assert "query-aliases.json" not in text, f"{script.name} writes the alias table"
