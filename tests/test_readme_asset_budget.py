#!/usr/bin/env python3
"""README images must exist, and must not be megabyte recordings.

What this is about is not bytes in the clone — `docs/maintainer/clone-size-measurement-2026-10-06.md`
§2 measured that **deleting files from HEAD saves exactly zero bytes of clone**, because the object
store keeps the history. So a size rule here is not a clone-size rule.

It is a *rendered README* rule, which is a different thing: a browser fetching `README.md` from
GitHub downloads the tree, not the history. Whatever an image weighs, every reader pays it, every
time, before they see the words around it.

The concrete failure this pins came from `promotional/search lesson.gif`: 6,023 KB referenced from
`README.md` and `README.ja.md`, carrying a screen recording of the search page whose header read
**`235 searchable lessons`** while `data/lessons.json` held **469** (measured 2026-10-07). It sat
under `### Use it as a GitHub Action` although it demonstrated web search, and `739cae4d` had
already deleted it once as an unused asset — `b6b712bf` restored it *only* because the README
referenced it, which is how a 6 MB recording with a baked-in number came back.

The number is the part that matters, and no gate could see it: a count inside an image is not text,
so `tests/test_lesson_count_ssot.py` — which requires counts on counted surfaces to point at the
dynamic badge rather than quote a literal — passed over it. `test_readme_scope_section.py` passed
over it. A recording is exactly the place where a stale claim survives review.

So: every README image must resolve, and none may exceed the budget below. One real image remains
across all three READMEs at 111 KB, so the budget is roughly nine times what is actually used —
generous enough that nobody hits it by accident, small enough that the next recording cannot.
"""
from __future__ import annotations

import pathlib
import re

REPO = pathlib.Path(__file__).resolve().parents[1]

READMES = ["README.md", "README.zh-CN.md", "README.ja.md"]

# 1 MB. The only image referenced by any README is 111 KB (promotional/misakanet-scope-comic.webp).
# See the module docstring for why this is a rendered-page budget and not a clone-size budget.
ASSET_BUDGET_BYTES = 1024 * 1024

IMAGE_REFERENCE = re.compile(r"!\[[^\]]*\]\(\s*([^)\s]+)")


def _referenced_images(readme: pathlib.Path) -> list:
    text = readme.read_text(encoding="utf-8")
    return [m.group(1) for m in IMAGE_REFERENCE.finditer(text)]


def test_every_readme_image_reference_resolves():
    missing = []
    for name in READMES:
        for src in _referenced_images(REPO / name):
            path = REPO / src.replace("%20", " ")
            if not path.exists():
                missing.append(f"{name}: {src}")
    assert missing == [], (
        "these README image references do not resolve — GitHub renders them as a broken image:\n  - "
        + "\n  - ".join(missing)
    )


def test_no_readme_image_is_a_megabyte_recording():
    oversized = []
    for name in READMES:
        for src in _referenced_images(REPO / name):
            path = REPO / src.replace("%20", " ")
            if not path.exists():
                continue
            size = path.stat().st_size
            if size > ASSET_BUDGET_BYTES:
                oversized.append(f"{name}: {src} is {size / 1024:.0f} KB")
    assert oversized == [], (
        f"README images must stay under {ASSET_BUDGET_BYTES // 1024} KB. A browser fetching the "
        "rendered README pays for every image on it, and a screen recording is where a stale claim "
        "hides — no gate can read a number baked into pixels:\n  - " + "\n  - ".join(oversized)
    )


def test_the_gate_would_not_have_survived_the_asset_it_exists_for():
    """The removal is only real if the gate is the reason it cannot come back.

    Written as an assertion about the *deleted* file so that a future contributor who restores it
    from history finds this test failing with a name, rather than re-introducing 6 MB silently.
    """
    removed = REPO / "promotional" / "search lesson.gif"
    assert not removed.exists(), (
        "promotional/search lesson.gif is back. It carried `235 searchable lessons` while the "
        "corpus held 469, and it was the reason this gate exists — if it is coming back, it needs "
        "a fresh recording with no baked-in count, not a restore."
    )