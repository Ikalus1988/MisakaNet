#!/usr/bin/env python3
"""`docs/_redirects` — the id -> slug table that makes `/lessons/<id>/` resolve.

Background. `misakanet_search` returns a lesson's frontmatter `id`, but its page lives at a title-derived
`/lessons/<slug>/`. For 111 of the 464 lessons those differ, so the documented pattern ("search, then open
the page at the URL the docs give") 404'd. The first fix (2026-09-29) wrote a stub HTML page per alias.
That worked in a browser and worked for nothing else: `<meta http-equiv="refresh">` is invisible to any
client that is not one, so `curl`, an MCP agent resolving a search hit, a feed reader and a link checker
all saw a `200` with a short HTML body. It also kept tripping GitHub's secret-scanning heuristic, because
the body embeds the slug text and ordinary lesson titles contain words like "keys" and "GC pattern".

This table is the structural fix: one line per alias, a real HTTP `301`, honoured by the platform itself.
The properties worth pinning are the ones whose loss is silent:

* **301, not the 302 default** — a slug is sticky (`plan_with_slugs` keeps a lesson on the URL it already
  has), so the old address is permanently moved. This also fails the *other* way if it ever regresses to
  302: nothing breaks, the redirect just stops being truthful, so only an explicit assertion catches it.
* **The table agrees with the corpus** — the failure mode is a table that outlives the slug map, which
  would send readers to a slug that has since been reassigned.
* **Every target is a real page** — a rule pointing at a 404 is worse than no rule.
* **No source is also a real page** — a rule shadowing a lesson would make a real page unreachable.
* **Platform limits** — Cloudflare caps a `_redirects` file at 2,000 static redirects and 1,000 characters
  per declaration. Both are checked against the real file so a corpus growth PR fails here rather than in
  production, where the symptom is a silently dropped rule.

The stub pages are still committed while the 301s are being observed on the live site, so this file also
asserts the two agree rule-for-rule. When the stubs are retired that assertion is what proves the overlap
was clean.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import build_lesson_pages as blp  # noqa: E402

REDIRECTS = REPO / "docs" / "_redirects"

# Cloudflare Workers Static Assets, "Redirects": 2,000 static redirects per file, 1,000 characters per
# declaration. https://developers.cloudflare.com/workers/static-assets/redirects/
MAX_STATIC_REDIRECTS = 2000
MAX_DECLARATION_CHARS = 1000

# A segment is "anything that is not a separator or whitespace": the file format is whitespace-separated,
# so a segment cannot contain a space, and a `/` would end the path. Deliberately not `[A-Za-z0-9-]+` —
# three slugs in the corpus are Chinese (`fanuc-ls-程序解析段标记必须行首锚定否则注释会截断程序体`,
# measured 2026-10-04, live 200), and an ASCII-only class here reduces the table to 108 rules while every
# test still passes, which is the worst possible failure for a drift guard.
RULE = re.compile(r"^(?P<source>/lessons/[^/\s]+/) (?P<target>/lessons/[^/\s]+/) (?P<code>\d{3})$")


def _rules() -> dict[str, tuple[str, str]]:
    """The committed table, parsed. Fails loudly rather than skipping if the file is missing."""
    assert REDIRECTS.exists(), (
        f"{REDIRECTS.relative_to(REPO)} is missing — the generator writes it on every run "
        f"(plan_with_slugs), so this is either a stale checkout or a hand edit")
    parsed: dict[str, tuple[str, str]] = {}
    for lineno, line in enumerate(REDIRECTS.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        m = RULE.match(stripped)
        assert m, f"{REDIRECTS.relative_to(REPO)}:{lineno} is not a rule this parser understands: {line!r}"
        source, target, code = m.group("source"), m.group("target"), m.group("code")
        assert source not in parsed, f"duplicate source rule at line {lineno}: {source}"
        parsed[source] = (target, code)
    return parsed


def _committed_stubs() -> dict[str, str]:
    """The 2026-09-29 stub pages still on disk, as {url: canonical target}."""
    stubs: dict[str, str] = {}
    for page in sorted((REPO / "docs" / "lessons").glob("*/index.html")):
        head = page.read_text(encoding="utf-8", errors="replace")[:400]
        if "<title>Moved — " not in head:
            continue
        m = re.search(r'<link rel="canonical" href="([^"]+)"', head)
        assert m, f"{page.relative_to(REPO)} looks like a stub but has no canonical to compare against"
        stubs[f"/lessons/{page.parent.name}/"] = m.group(1)
    return stubs


def test_the_table_is_not_empty_and_agrees_with_the_committed_stubs():
    """The overlap window: while both exist they must say the same thing, rule for rule.

    They are not interchangeable if they disagree. A redirect is "always followed, regardless of whether
    or not an asset matches", so the table shadows the stub page at the same URL — whichever is wrong is
    the one a reader gets, and the other is invisible. This is the check that makes retiring the stubs a
    mechanical, evidence-backed step rather than a leap of faith.
    """
    rules = _rules()
    stubs = _committed_stubs()
    assert rules, ("the table parsed to zero rules — the parser drifted from the generator, or the corpus "
                   "lost every alias")
    assert stubs, ("no stub pages on disk: either they were retired (drop this half of the check and the "
                   "target check below becomes the only overlap evidence) or the generator changed")
    disagree = {
        source: f"table={target} stub={stubs.get(source, '<no stub>')}"
        for source, (target, _code) in rules.items()
        if stubs.get(source) != target
    }
    assert not disagree, (
        "the redirect table and the stub pages it shadows disagree; the table wins at runtime, so a "
        "disagreement here is a live wrong redirect: " + "; ".join(f"{k} ({v})" for k, v in list(disagree.items())[:5]))
    only_stub = sorted(set(stubs) - set(rules))
    assert not only_stub, (
        f"{len(only_stub)} stub page(s) have no rule, so a supported platform would 404 them once the "
        f"stubs are retired: {only_stub[:5]}")


def test_every_redirect_is_permanent():
    """301, not Cloudflare's 302 default.

    Load-bearing and easy to lose: drop the code and the redirect still works, so nothing fails. A slug
    is sticky by design (`plan_with_slugs` reuses the recorded slug rather than re-deriving it, which is
    what stops a title edit from orphaning a live URL), so the old id address is permanently moved and 301
    is the only truthful status. It is also the status a crawler propagates to the target.
    """
    wrong = {s: c for s, (_t, c) in _rules().items() if c != "301"}
    assert not wrong, (
        "these aliases are not 301. A slug never moves back, so the redirect is permanent; a 302 tells a "
        "crawler the address may return and stops it propagating the move: "
        + "; ".join(f"{s} -> {c}" for s, c in list(wrong.items())[:5]))


def test_every_target_is_a_page_that_exists_and_every_source_is_not_a_real_page():
    """A rule to a 404 is worse than no rule, and a rule over a real page hides that page.

    "Not a real page" rather than "no file": during the overlap window every source *does* have a file —
    the stub it shadows. The distinction that matters is whether that file is a real lesson page (another
    lesson's slug, which the generator must never shadow) or the stub. The generator enforces this with
    `if path in files: continue` ("a real page always wins"); this pins it from disk state, where a hand
    edit or a stale run would reintroduce it.
    """
    for source, (target, _code) in _rules().items():
        assert (REPO / "docs" / target.lstrip("/") / "index.html").exists(), (
            f"{source} redirects to {target}, which has no page on disk — that rule turns a working URL "
            f"into a 404 the moment the stubs are retired")
        source_page = REPO / "docs" / source.lstrip("/") / "index.html"
        if source_page.exists():
            head = source_page.read_text(encoding="utf-8", errors="replace")[:400]
            assert "<title>Moved — " in head, (
                f"{source} has both a redirect rule and a real lesson page; the rule wins at runtime, so "
                f"that lesson becomes unreachable. This is the id-equals-another-lesson's-slug collision "
                f"the generator is supposed to drop")


def test_the_table_is_what_the_generator_produces_from_the_corpus():
    """The drift guard.

    The table is derived state: `plan_with_slugs` writes it from the same slug map the pages use. If the
    committed file disagrees, something wrote it by hand or the corpus moved without a regeneration — and
    the two failures look identical from the outside, as readers being sent to the wrong lesson.
    """
    lessons = json.loads((REPO / "data" / "lessons.json").read_text(encoding="utf-8"))
    files, _assigned = blp.plan_with_slugs(lessons, blp.load_slug_map(REPO))
    assert blp.REDIRECTS.as_posix() in files, (
        "the generator no longer plans the table — the committed file would be a frozen snapshot that "
        "silently stops following the corpus")
    assert files[blp.REDIRECTS.as_posix()] == REDIRECTS.read_text(encoding="utf-8"), (
        f"{REDIRECTS.relative_to(REPO)} is not what the generator produces; run "
        f"`python3 scripts/build_lesson_pages.py` and commit the result")


def test_the_table_stays_inside_the_platforms_limits():
    """Checked against the real file, so corpus growth fails here instead of dropping rules in production.

    A rule past the cap is not an error Cloudflare reports — it is a redirect that silently stops being
    applied, which is the same failure this whole table exists to remove.
    """
    lines = [l for l in REDIRECTS.read_text(encoding="utf-8").splitlines()
             if l.strip() and not l.strip().startswith("#")]
    assert len(lines) <= MAX_STATIC_REDIRECTS, (
        f"{len(lines)} rules exceeds the {MAX_STATIC_REDIRECTS}-redirect cap for a Workers Static Assets "
        f"_redirects file; rules past the cap are dropped silently. Use Bulk Redirects, or drop the "
        f"id-alias guarantee for the overflow")
    too_long = [l for l in lines if len(l) > MAX_DECLARATION_CHARS]
    assert not too_long, (
        f"{len(too_long)} declaration(s) exceed the {MAX_DECLARATION_CHARS}-character limit and would be "
        f"ignored: {[l[:80] for l in too_long[:2]]}")
    # Bytes as well as characters: the limit is the platform's, not ours, and a rule that is short in
    # characters is not short in the bytes a parser reads.
    too_long_bytes = [l for l in lines if len(l.encode("utf-8")) > MAX_DECLARATION_CHARS]
    assert not too_long_bytes, (
        f"{len(too_long_bytes)} declaration(s) exceed {MAX_DECLARATION_CHARS} bytes: "
        f"{[l[:60] for l in too_long_bytes[:2]]}")


def test_the_301_rule_notices_a_302_table():
    """Guard: the rule reads the committed file, so its failure mode needs a fixture.

    Without this, `test_every_redirect_is_permanent` is a passing assertion about a file nobody has ever
    seen fail — the same trap as a source-text grep for behaviour that only exists at runtime.
    """
    table = "\n".join([
        "# header",
        "/lessons/old-id/ /lessons/new-slug/ 302",
    ]) + "\n"
    wrong = {s: c for s, (_t, c) in _parse(table).items() if c != "301"}
    assert wrong == {"/lessons/old-id/": "302"}, wrong
    assert not {s: c for s, (_t, c) in _parse(table.replace(" 302", " 301")).items() if c != "301"}


def _parse(text: str) -> dict[str, tuple[str, str]]:
    """The same parse `_rules()` performs, over a supplied table instead of the committed one."""
    parsed: dict[str, tuple[str, str]] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        m = RULE.match(stripped)
        if m:
            parsed[m.group("source")] = (m.group("target"), m.group("code"))
    return parsed


@pytest.mark.parametrize("path", [
    "/lessons/abc/",
    "/lessons/abc-1.2_3~/",
    "/lessons/fanuc-ls-parser-comment-and-segment-boundary/",
    # The three Chinese slugs in the corpus. Pinned by value, not by shape: they are the only rules whose
    # target is non-ASCII, so they are the only ones where the table's encoding is a real question.
    "/lessons/fanuc-ls-程序解析段标记必须行首锚定否则注释会截断程序体/",
    "/lessons/rag-检索沉底多层机制同章节措辞差异-截断降权拦截短文本精确答案/",
])
def test_the_parser_reads_the_shapes_the_generator_emits(path):
    """Slugify output has to survive the round trip.

    A parser that rejected real slugs would reduce the table to 108 rules rather than fail loudly, which
    is why `test_the_table_is_not_empty...` asserts the rule count against the stubs rather than just
    being non-zero. This pins the character set so a future slugify change cannot quietly fall out.
    """
    parsed = _parse(f"{path} /lessons/target/ 301\n")
    assert parsed == {path: ("/lessons/target/", "301")}, parsed


def test_every_corpus_alias_is_represented_including_the_non_ascii_ones():
    """The count that matters, so a parser that quietly drops a character class cannot pass.

    111 is the number of lessons whose id is not their slug, and 3 of those redirect to a Chinese slug.
    Asserting only "non-empty" would let a regression that drops all non-ASCII targets through.
    """
    rules = _rules()
    assert len(rules) == len(_committed_stubs()), (
        f"{len(rules)} rules vs {len(_committed_stubs())} stub pages")
    non_ascii = sorted(s for s, (t, _c) in rules.items() if any(ord(ch) > 127 for ch in s + t))
    assert len(non_ascii) == 3, (
        f"expected the 3 known Chinese-slug aliases, found {len(non_ascii)}: {non_ascii}")



def test_the_parser_rejects_a_malformed_rule_instead_of_guessing():
    """A line that is not a rule must be ignored by `_parse` and rejected by `_rules`.

    Two different behaviours on purpose: `_rules` asserts on the committed file because a malformed line
    there is a real defect, while `_parse` is the tolerant reader the fixture test above uses. If `_parse`
    started raising, the fixture tests would be testing the failure rather than the rule.
    """
    assert _parse("/lessons/a/ /lessons/b/\n") == {}, "a rule missing its status code must not parse"
    assert _parse("/lessons/a/ /lessons/b/ 200\n") == {
        "/lessons/a/": ("/lessons/b/", "200")}, "the parser is about codes, not about which codes are legal"
    assert _parse("/search /lessons/b/ 301\n") == {}, "only lesson rules are in scope for this table"

