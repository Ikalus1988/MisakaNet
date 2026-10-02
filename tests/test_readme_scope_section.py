#!/usr/bin/env python3
"""The README's scope note — and the comic that carries it — must survive translation.

The four-panel comic makes the same promise the search contract makes: MisakaNet answers for the
failures it has indexed, and a miss returns `no_match` plus a ready-to-call intake. It landed in all
three READMEs at once, which is the kind of change that rots in two of them — the localized READMEs
have drifted apart structurally, so the same thought sits in a different neighbourhood in each (see
the placement test below, which names where each one keeps it).

What is deliberately **not** asserted here: the absence of the stale framing. `README.ja.md` still
carries the retired "Swarm Knowledge Protocol" heading and its 「サーバー不要。データベース不要。」
claim, and `README.zh-CN.md` repeats that claim in its own words. The onboarding modal no longer makes
that claim — PR #2706 landed the fix (squash `2aad28f14`, merged 2026-10-02T07:47:25Z, eighty-seven
seconds before this file's parent commit) — but the READMEs still do, so a rule like "no README claims a
local-only architecture" would redden `main` today, which is the trap #2694 fell into by pinning
`origin/main` as a positive control. Retiring that framing from the localized READMEs is its own change.
An earlier version of this docstring said that branch was *not* merged yet; an independent review checked
the merge timestamp and corrected it, which is the second time a claim in this pull request's description
was wrong while its artifact was right.

An independent review of the first version of this file found three false claims in its *description*
(not in the artifact) and four ways to walk around these assertions; the rules below are the answer to
both, and the review is linked from the pull request.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
IMAGE = "promotional/misakanet-scope-comic.webp"
ASSET = REPO / IMAGE
READMES = ("README.md", "README.zh-CN.md", "README.ja.md")
#: The lesson/skill boundary in each README. The scope note belongs on the near side of it, whatever
#: the surrounding structure looks like — the three have drifted apart, so "beside the is NOT table"
#: (the first version's claim) is true in `README.md` only.
BOUNDARY = {
    "README.md": "### Lesson vs Skill",
    "README.zh-CN.md": "### Lesson 和 Skill 有什么区别？",
    "README.ja.md": "### レッスン vs スキル",
}
#: The retired heading the comic must not be buried in, where it still exists.
RETIRED = {"README.ja.md": "## スワンKnowledgeプロトコルとは？"}
#: The front page renders this on every visit; the two assets beside it are 2.7 MB and 6.2 MB. Bounds
#: on both sides: an upper one alone is satisfied by a 1x1 placeholder.
BUDGET = (20_000, 200_000)
CJK = re.compile(r"[\u4e00-\u9fff]")


def dictionary(name: str) -> str:
    text = (REPO / name).read_text(encoding="utf-8")
    assert IMAGE in text, f"{name} does not show the scope comic"
    return text


def alt_of(text: str) -> str:
    match = re.search(rf"!\[([^\]]+)\]\({re.escape(IMAGE)}\)", text)
    assert match, f"the comic is not a markdown image with alt text: {IMAGE}"
    return match.group(1)


def section_of(text: str) -> str:
    """The subsection that carries the comic, from its own heading to the next one."""
    index = text.index("![" + alt_of(text))
    heading = text.rindex("\n### ", 0, index)
    following = text.find("\n### ", index)
    return text[heading:following if following != -1 else len(text)]


def test_every_readme_shows_the_same_comic():
    """One file, three READMEs: a moved or renamed asset cannot leave a language broken."""
    assert ASSET.exists(), f"{IMAGE} is missing"
    for name in READMES:
        text = dictionary(name)
        assert text.count(IMAGE) == 1, f"{name} references the comic {text.count(IMAGE)} times"


def test_the_alt_text_is_translated_not_copied():
    """A reader on a screen reader gets the same joke, in their language.

    Compared with whitespace collapsed: appending a space to a copied alt text was one of the ways an
    independent review walked around the first version of this rule.
    """
    alts = {name: " ".join(alt_of(dictionary(name)).split()) for name in READMES}
    for name, alt in alts.items():
        assert len(alt) >= 40, f"{name}'s alt text says too little to replace the image: {alt!r}"
    assert len(set(alts.values())) == len(READMES), (
        "the same alt text is used in more than one language, so it was not translated: "
        f"{[n for n, a in alts.items() if list(alts.values()).count(a) > 1]}")


@pytest.mark.parametrize("name", READMES)
def test_the_section_is_written_in_the_language_it_claims(name):
    """Rules out the shortcut of pasting the English prose into the zh and ja READMEs.

    The check is on the **body after the image**, not on the section as a whole: an independent review
    kept each localized heading, replaced everything below the image with the English prose, and the
    whole-section rule stayed green because the heading alone satisfied it.
    """
    if name == "README.md":
        pytest.skip("the English README is the original, not a translation")
    section = section_of(dictionary(name))
    image = section.find("![")
    image_end = section.find(")", image) if image != -1 else -1
    body = section[image_end + 1:] if image_end != -1 else section
    assert CJK.search(body), (
        f"{name}'s scope section is not written in its own language — the heading is localized but the "
        f"body after the comic is not: {body.strip()[:120]!r}")
    assert CJK.search(section), f"{name}'s scope section has no CJK characters: {section[:80]!r}"


@pytest.mark.parametrize("name", READMES)
def test_the_scope_note_names_the_miss_shape(name):
    """The point of the section: a miss is `no_match` + intake, not a dead end.

    Scoped to the section rather than the file: both tokens occur elsewhere in the READMEs, so a
    whole-file check would pass even after this sentence was deleted.
    """
    section = section_of(dictionary(name))
    assert "no_match" in section and "intake" in section, (
        f"{name}'s scope section shows the comic without saying what a miss returns")


@pytest.mark.parametrize("name", READMES)
def test_the_comic_sits_beside_the_scope_note_not_inside_a_retired_one(name):
    """Placement, per README: before the lesson/skill boundary, and never inside a retired section.

    The first version of this change claimed the comic followed "the is NOT table" in all three — it
    does in `README.md` only (`README.zh-CN.md` has no such table at all — its v2.17.0 "new features"
    list claims such a comparison shipped, which it never did, and that is its own piece of drift), and
    in `README.ja.md` the insertion landed inside `## スワンKnowledgeプロトコー
    ルとは？` — the heading this repository has retired — because that is where the localized README
    keeps its `Lesson vs Skill` heading. The boundary rule catches an insertion that drifts too far
    down; the retired-section rule catches this specific burial, which the first draft walked into.
    """
    text = dictionary(name)
    here = text.index("![" + alt_of(text))
    boundary = text.index(BOUNDARY[name])
    assert here < boundary, f"{name}: the comic sits after {BOUNDARY[name]!r}"
    retired = RETIRED.get(name)
    if retired is not None and retired in text:
        assert here < text.index(retired), (
            f"{name}: the comic is inside the retired section {retired!r} — move it next to the scope "
            "note it belongs to")


def test_the_comic_stays_affordable():
    """It renders on every visit to the repository front page. Bounded on both sides."""
    low, high = BUDGET
    size = ASSET.stat().st_size
    assert low <= size <= high, (
        f"{IMAGE} is {size:,} bytes; the budget is {low:,}-{high:,} so the front page stays light "
        "without a placeholder passing for the image")
