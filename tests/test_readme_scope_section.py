#!/usr/bin/env python3
"""The README's scope note — and the comic that carries it — must survive translation.

The four-panel comic makes the same promise the search contract makes: MisakaNet answers for the
failures it has indexed, and a miss returns `no_match` plus a ready-to-call intake. It landed in all
three READMEs at once, which is the kind of change that rots in two of them — the localized READMEs
have already drifted structurally, and `README.ja.md` still carries the retired "Swarm Knowledge
Protocol" heading and its 「サーバー不要。データベース不要。」 framing.

So this file holds the three copies together: one image path, one asset, an alt text per language.

It deliberately does **not** assert the absence of the stale framing in every language yet. The ja
README still says it, so such a rule would redden `main` on the day it landed — the trap #2694 fell
into when a positive control pinned `origin/main`. Retiring that section is its own change; this file
pins what shipped today, and the claim gate for the modal
(`tests/test_onboarding_modal.py`) covers the page.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
IMAGE = "promotional/misakanet-scope-comic.png"
ASSET = REPO / IMAGE
READMES = ("README.md", "README.zh-CN.md", "README.ja.md")
#: The first-screen image of the repository's front page; the two assets beside it are 2.7 MB and
#: 6.2 MB, so a budget is the only thing keeping a re-upload from getting silly.
BUDGET_BYTES = 400_000


def dictionary(name: str) -> str:
    text = (REPO / name).read_text(encoding="utf-8")
    assert IMAGE in text, f"{name} does not show the scope comic"
    return text


def alt_of(text: str) -> str:
    match = re.search(rf"!\[([^\]]+)\]\({re.escape(IMAGE)}\)", text)
    assert match, f"the comic is not a markdown image with alt text: {IMAGE}"
    return match.group(1)


def test_every_readme_shows_the_same_comic():
    """One file, three READMEs: a moved or renamed asset cannot leave a language broken."""
    assert ASSET.exists(), f"{IMAGE} is missing"
    for name in READMES:
        text = dictionary(name)
        assert text.count(IMAGE) == 1, f"{name} references the comic {text.count(IMAGE)} times"


def test_the_alt_text_is_translated_not_copied():
    """A reader on a screen reader gets the same joke, in their language."""
    alts = {name: alt_of(dictionary(name)) for name in READMES}
    for name, alt in alts.items():
        assert len(alt) >= 40, f"{name}'s alt text says too little to replace the image: {alt!r}"
    assert len(set(alts.values())) == len(READMES), (
        "the same alt text is used in more than one language, so it was not translated: "
        f"{[n for n, a in alts.items() if list(alts.values()).count(a) > 1]}")


@pytest.mark.parametrize("name", READMES)
def section_of(text: str) -> str:
    """The subsection that carries the comic, from its own heading to the next one."""
    index = text.index("![" + alt_of(text))
    heading = text.rindex("\n### ", 0, index)
    following = text.find("\n### ", index)
    return text[heading:following if following != -1 else len(text)]


@pytest.mark.parametrize("name", READMES)
def test_the_scope_note_names_the_miss_shape(name):
    """The point of the section: a miss is `no_match` + intake, not a dead end.

    Scoped to the section rather than the file: both tokens occur elsewhere in the READMEs, so a
    whole-file check would pass even if this section lost the sentence.
    """
    section = section_of(dictionary(name))
    assert "no_match" in section and "intake" in section, (
        f"{name}'s scope section shows the comic without saying what a miss returns")


def test_the_comic_stays_affordable():
    """It renders on every visit to the repository front page."""
    size = ASSET.stat().st_size
    assert size <= BUDGET_BYTES, (
        f"{IMAGE} is {size:,} bytes; the budget is {BUDGET_BYTES:,} so the front page stays light")
