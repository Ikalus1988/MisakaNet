#!/usr/bin/env python3
"""A third-party script may not hold up the first paint, and its absence may not become injected markup.

Measured on `docs/index.html`, 2026-10-02, with a route-level delay on `cdnjs.cloudflare.com`:

| cdnjs delay | FCP while DOMPurify blocked | FCP with `defer` + readiness gate |
|---|---|---|
| 0 ms | 464 ms | **236 ms** |
| 1000 ms | **1468 ms** | **236 ms** |

`defer` alone is not enough, and the first attempt at this proved it: with the script deferred but the
sanitising paths unchanged, three of three runs threw `DOMPurify is not defined`, because a top-level
`switchLang(LANG)` / `loadLessons()` / `loadVoices()` reaches `DOMPurify.sanitize` before the deferred
script has run. Waiting only for `DOMContentLoaded` was not enough either — instrumented, `readyState`
was already `interactive` with `DOMPurify` still undefined, so the gate waits for `load` as well.

The failure that matters most is the quiet one: `cdnjs` is a common block-list target, and a page that
cannot sanitise must render **plain text** rather than inject what it could not sanitise. That is what the
`onMissing` arm of `whenPurifyReady` is for, and this file keeps both halves in place.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PAGE = (REPO / "docs" / "index.html").read_text(encoding="utf-8")
#: Functions that call `DOMPurify.` — every one of them has to wait for the deferred script.
SANITISERS = ("renderErrorBoundaryUI", "renderVoices", "onSearchFocus", "searchLessons")


def _body_of(name: str) -> str:
    tail = PAGE.split(f"function {name}(", 1)[1]
    return tail.split("\nfunction ", 1)[0]


def test_the_third_party_sanitiser_does_not_block_the_parser():
    tag = re.search(r"<script[^>]*purify[^>]*>", PAGE)
    assert tag, "the DOMPurify script tag is gone; this rule needs updating"
    assert " defer" in tag.group(0), f"the sanitiser blocks the parser again: {tag.group(0)[:120]}"


def test_every_sanitising_path_waits_for_it():
    assert "function whenPurifyReady(run, onMissing)" in PAGE, (
        "the readiness helper is gone; a deferred sanitiser is undefined until it loads")
    for name in SANITISERS:
        body = _body_of(name)
        assert "DOMPurify." in body, f"{name} no longer sanitises; update SANITISERS"
        assert "whenPurifyReady" in body, (
            f"{name} sanitises without waiting for the deferred script — under a slow CDN it throws "
            "`DOMPurify is not defined` (measured 3/3 runs)")


def _on_missing_arm(name: str) -> str:
    """The second argument of that function's `whenPurifyReady(...)` call — its degraded path.

    Extracted rather than searched for in the whole file: an earlier version asserted
    `re.search(r"el\.textContent = ", PAGE)`, which some *other* function satisfies permanently, so
    changing a degraded arm to `innerHTML` stayed green (an independent review's M5).
    """
    body = _body_of(name)
    start = body.index("whenPurifyReady(") + len("whenPurifyReady(")
    depth = 1
    index = start
    while index < len(body) and depth:
        if body[index] in "([{":
            depth += 1
        elif body[index] in ")]}":
            depth -= 1
        index += 1
    call = body[start:index - 1]
    # the arm is everything after the first top-level comma of the call
    depth = 0
    for position, char in enumerate(call):
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
        elif char == "," and depth == 0:
            return call[position + 1:]
    raise AssertionError(f"{name}'s whenPurifyReady call has no missing-arm at all: {call!r}")


def test_a_missing_sanitiser_degrades_to_text_not_markup():
    """The quiet failure: cdnjs blocked, and every sanitised fragment would become an injection."""
    helper = PAGE.split("function whenPurifyReady(run, onMissing) {", 1)[1].split("\nfunction ", 1)[0]
    assert "onMissing" in helper, "the helper must offer a missing-arm"
    assert re.search(r'addEventListener\(\s*["\']load["\']', helper), (
        "the helper must keep a `load` listener: `DOMContentLoaded` can fire while the script is still in "
        "flight, and `complete` is the only state that means it cannot arrive")
    assert "readyState === \"complete\"" in helper, (
        "settling on anything but `complete` resolves false while the sanitiser is still loading — the "
        "voices wall then never renders (measured under a 1 s CDN delay)")
    for name in SANITISERS:
        arm = _on_missing_arm(name)
        assert "innerHTML" not in arm, (
            f"{name}'s degraded path injects markup instead of writing text: {arm.strip()[:120]}")
    for name in ("renderErrorBoundaryUI", "searchLessons"):
        arm = _on_missing_arm(name)
        assert "textContent" in arm, (
            f"{name}'s degraded path says nothing to the reader: {arm.strip()[:120]}")
