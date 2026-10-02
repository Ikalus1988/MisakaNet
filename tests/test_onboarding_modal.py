#!/usr/bin/env python3
"""The onboarding modal may not claim more than the network can do.

It used to be a pasted copy of the clone-era README: **184 CJK characters hardcoded** inside an
otherwise bilingual page (so an English reader got Chinese), a five-step join flow that taught the
path agents no longer need, and this architecture sentence —

    搜索在本地完成。完全无服务器架构。

— which was false by the time anyone read it: production search runs on a Cloudflare Worker (hosted
MCP, BM25 over D1), and the local BM25 is the fallback path, not the whole story. "Serverless" was
also doing a lot of unearned work in a sentence about Workers.

The replacement is short, localized, and says the one thing the corpus actually promises: it answers
for the failures it has indexed, and a miss is information (`no_match` plus a ready-to-call intake).
That is the same boundary the four-panel comic tells, and the same one the search contract enforces —
so the modal now points at the entry points instead of re-teaching the README.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PAGE = REPO / "docs" / "index.html"
BLOB = "https://github.com/Ikalus1988/MisakaNet/blob/main/"
CJK = re.compile(r"[\u4e00-\u9fff]")


class _VisibleProse(HTMLParser):
    """Text a reader sees, with a flag for whether a `data-i18n` element is above it."""

    def __init__(self) -> None:
        super().__init__()
        self._stack: list[bool] = []
        self.untranslated: list[str] = []

    def handle_starttag(self, tag, attrs):
        inherited = self._stack[-1] if self._stack else False
        self._stack.append(inherited or any(name == "data-i18n" for name, _ in attrs))

    def handle_endtag(self, tag):
        if self._stack:
            self._stack.pop()

    def handle_data(self, data):
        text = data.strip()
        if text and any(ch.isalpha() for ch in text):
            if not (self._stack and self._stack[-1]):
                self.untranslated.append(text)


def modal() -> str:
    """The modal block, bounded by the marker that has to follow it.

    Sliced from the start of the opening tag: indexing the `id` attribute alone leaves the rest of
    that tag inside the block, and the parser below then reads it as text (it reported
    `onclick="if(event.target===this)toggleModal()">` as an untranslated string when this was first
    written).
    """
    page = PAGE.read_text(encoding="utf-8")
    start = page.index('<div class="modal-overlay" id="onboarding-modal"')
    end = page.index("<!-- Toast -->", start)
    return page[start:end]


def test_the_modal_is_not_hardcoded_chinese():
    """The page is bilingual; the modal was the one block that ignored the switch.

    The Chinese lives in `docs/locales/zh.json` like every other string the page renders, so the
    English reader gets English and the two languages cannot drift apart inside the markup.
    """
    found = CJK.findall(modal())
    assert not found, (
        "the modal carries hardcoded Chinese again (%d characters, e.g. %r); put it in the locale "
        "dictionaries and reference it with data-i18n" % (len(found), "".join(found[:12])))


def test_the_modal_does_not_promise_local_only_search():
    """The sentence that was false, plus the facts a rewrite would have to keep.

    The banned shapes are a word list, and an independent review showed a word list can be walked
    around: "Everything happens on your own machine; there is no backend to depend on." passes it. So
    the rule has two halves — the phrases cannot come back, **and** the section must still say where
    search runs and where a miss is defined. A rewrite that drops those facts fails even when it
    invents fresh wording for the claim.
    """
    block = modal()
    # The banned shapes are the *claims*, not the words: the replacement legitimately says the same
    # BM25 "also runs locally after a git clone", so a bare "runs locally" check would fail on a true
    # sentence (it did, when this test was first written).
    for claim in ("serverless", "no server", "runs only locally", "locally only",
                  "完全无服务器", "搜索在本地完成", "无需服务器"):
        assert claim not in block, (
            f"the modal claims {claim!r} again: production search runs on a Cloudflare Worker and "
            "the local BM25 is the fallback, not the architecture")
    assert "Cloudflare Worker" in block, "say where search actually runs, or say nothing"
    # The positive half: the claim has to stay anchored to the path that actually makes it. The hosted
    # endpoint returns `no_match`; the local handler deliberately keeps no relevance floor (recorded in
    # tests/test_e2e_mcp_pipeline.py), so a sentence that promises `no_match` for both paths is wrong.
    assert "hosted endpoint" in block, "name the path that returns no_match"
    assert "no relevance floor" in block, "the local handler returns its best matches; do not imply it refuses"


def test_the_modal_points_at_entry_points_that_exist():
    """Every link is checked against the repository, so a rename cannot leave a dead CTA."""
    block = modal()
    assert 'href="/start"' in block, "the remote-MCP path is the one that needs no clone"
    for href in re.findall(r'href="([^"]+)"', block):
        if href.startswith(BLOB):
            target = REPO / href[len(BLOB):]
            assert target.exists(), f"{href} points at a file that is not in the repository"
        elif href.startswith("/") and not href.startswith("//"):
            target = REPO / "docs" / (href.lstrip("/") + ".html")
            assert target.exists(), f"{href} has no page in docs/ (looked for {target.name})"


def test_the_modal_says_a_miss_is_an_answer():
    """The scope line: indexed failures, and `no_match` + intake when there are none.

    Without it the modal reads as a general oracle, which is exactly the promise the comic punishes.
    """
    block = modal()
    assert "no_match" in block, "name the miss shape the client actually receives"
    assert "intake" in block, "a miss is only useful if it says how the gap gets recorded"
    assert "indexed" in block.lower(), "say that the knowledge is the indexed failures, not general knowledge"


def test_the_modal_text_is_localized():
    """No string a reader can see may lack a `data-i18n` ancestor.

    Checked over the parsed text rather than by inspecting tags: the entry-point line is one `<p>`
    whose copy lives in three inner `<span data-i18n=…>` elements, so a rule that demanded the
    attribute on the `<p>` itself failed on a correctly translated sentence (it did, when this test
    was written). The License footer is boilerplate — a name, a year range, a link — so it is out of
    scope.
    """
    prose = modal()
    prose = prose[prose.index("<h3"):]            # the brand title and the close button
    prose = prose.split("<h3>License</h3>")[0]    # the boilerplate footer
    assert prose.strip(), "the split left nothing to check, so this rule would pass vacuously"
    parser = _VisibleProse()
    parser.feed(prose)
    assert not parser.untranslated, (
        "these strings have no data-i18n ancestor, so an English reader sees the fallback markup: "
        f"{parser.untranslated[:3]}")
