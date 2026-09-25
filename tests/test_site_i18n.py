#!/usr/bin/env python3
"""Two dictionaries, one page: nothing missing, nothing dead.

`docs/locales/{en,zh}.json` are the whole i18n surface of the homepage, and they fail in two
directions. Both have been measured, on this page:

**A key the page renders but a dictionary lacks** renders as the key name. Seven of them were live
until 2026-09-24 and they were all written the same way — `t("regOptionGithub") || "选项一：有 GitHub
账号"` — inside the registration panel that appears when the worker is unreachable. The `||` reads
like a fallback and is dead code: `t()` ends in `|| key`, which is a non-empty string, so it is always
truthy. The visitor who saw that panel saw `regOptionGithub`, `regWorkerOfflineHint` and five more
identifiers in place of five sentences — precisely when something was already broken.

The old gate in `tests/test_registration_copy.py` checked `data-i18n="…"` attributes only, which is
why it passed: those seven are reached through `t()`, a call site the gate never looked at. It is
moved here and widened to both.

**A key that exists but nothing renders** is dead copy that looks like coverage. `statLatest` —
"最新节点编号" / "Latest Node" — sat in both dictionaries describing exactly what the node counter
*is*, while the stats card rendered a different key whose label was wrong in both languages (and
differently wrong in each: "已注册节点" against "Active Nodes"). A dictionary entry nothing uses is not
harmless: it is the correct wording sitting one line away from the wrong one being shipped.

So: every key in the dictionaries must be reachable from the page, and every key the page reaches
must exist in both.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
INDEX = REPO / "docs" / "index.html"
LOCALES = {lang: REPO / "docs" / "locales" / f"{lang}.json" for lang in ("en", "zh")}

# `t('key')` / `t("key")`, with a lookbehind so `.get('x')`, `.set('x')`, `createElement('span')` and
# friends are not mistaken for translation calls — matching those is what produced a false "missing
# key" list of `content-type`, `Retry-After` and `span` on the first attempt at this gate.
T_CALL = re.compile(r"""(?<![A-Za-z0-9_$.])t\(['"]([^'"]+)['"]\)""")
ATTR = re.compile(r'data-i18n(?:-placeholder)?="([^"]+)"')
# A quoted literal anywhere in the page. The activity panel wires its class labels through a table
# (`[['mcp', 'activityClassMcp'], …]`) and interpolates the key into `data-i18n`, so neither the
# attribute nor a `t()` call carries those names as text the first two patterns can see.
QUOTED = re.compile(r"""['"]([A-Za-z][A-Za-z0-9_]*)['"]""")


@pytest.fixture(scope="module")
def page() -> str:
    return INDEX.read_text(encoding="utf-8")


def dictionary(lang: str) -> dict[str, str]:
    return json.loads(LOCALES[lang].read_text(encoding="utf-8"))


def referenced(page: str, keys: set[str]) -> set[str]:
    """The dictionary keys the page actually reaches.

    A key counts as reached when it appears as a `data-i18n` value, in a `t()` call, or as a quoted
    literal (which is how the one dynamically-wired table passes its keys). `${key}`-shaped
    placeholders are not keys.
    """
    found = set(ATTR.findall(page)) | set(T_CALL.findall(page))
    found |= keys & set(QUOTED.findall(page))
    return {k for k in found if "$" not in k and "{" not in k}


def missing(page: str, keys: set[str]) -> list[str]:
    return sorted(referenced(page, keys) - keys)


def unused(page: str, keys: set[str]) -> list[str]:
    return sorted(keys - referenced(page, keys))


# ── the rule, both directions ────────────────────────────────────────────────────────────────────

def test_the_two_dictionaries_have_the_same_keys():
    assert set(dictionary("en")) == set(dictionary("zh")), (
        "a key in one dictionary and not the other falls back to English silently — which is how a "
        "statistic stayed in English in Chinese mode"
    )


def test_every_key_the_page_renders_exists_in_both_dictionaries(page):
    problems = {lang: missing(page, set(dictionary(lang))) for lang in ("en", "zh")}
    problems = {lang: keys for lang, keys in problems.items() if keys}
    assert not problems, (
        f"these keys are rendered but absent, so the page shows the identifier instead of the "
        f"copy (and `t(key) || 'fallback'` cannot save them: `t()` returns the key, which is "
        f"truthy): {problems}"
    )


def test_no_key_in_the_dictionaries_is_dead(page):
    keys = set(dictionary("en"))
    dead = unused(page, keys)
    assert not dead, (
        f"nothing on the page reaches {dead}. Either wire it up or delete it — an unused key is how "
        f"the *correct* wording for a number sat in the dictionary while a wrong one shipped"
    )


def test_the_gate_sees_both_surfaces(page):
    """Guard the guard: if either pattern stopped matching, both rules above would pass vacuously."""
    keys = set(dictionary("en"))
    attrs = set(ATTR.findall(page))
    calls = set(T_CALL.findall(page))
    assert len(attrs) > 50, f"only {len(attrs)} data-i18n values found — did the markup change shape?"
    assert len(calls) > 20, f"only {len(calls)} t() calls found — did the JS change shape?"
    assert len(keys - (attrs | calls)) > 0, (
        "every key is now reachable through the two text patterns, so the quoted-literal fallback "
        "is no longer exercised — keep it or drop it deliberately"
    )


# ── and it can go red ────────────────────────────────────────────────────────────────────────────

def test_a_key_used_only_through_t_is_caught(page):
    """The exact regression: a `t()`-only key, which the attribute-only gate could not see."""
    dropped = "regOptionGithub"
    assert dropped in dictionary("en") and dropped in dictionary("zh")
    without = {k: v for k, v in dictionary("en").items() if k != dropped}
    assert missing(page, set(without)) == [dropped]


def test_a_dead_key_is_caught(page):
    keys = set(dictionary("en")) | {"aKeyNothingRenders"}
    assert unused(page, keys) == ["aKeyNothingRenders"]


def test_the_old_attribute_only_gate_would_have_missed_this(page):
    """Why the widened gate exists, demonstrated rather than asserted in prose.

    `referenced()` is the new rule; the old one is `ATTR.findall(page)` alone. On the page as it
    stands the two agree — the seven `t()`-only keys were fixed by adding them. So the difference is
    shown the only honest way: by removing one of them again and watching which rule notices.
    """
    keys = set(dictionary("en")) - {"regViaIssue"}
    assert missing(page, keys) == ["regViaIssue"], "the widened rule notices"
    # The attribute-only rule sees neither `t()` calls nor `${key}` placeholders, so it reports
    # nothing here — which is exactly why the previous gate passed while the panel shipped raw
    # identifiers.
    assert "regViaIssue" not in ATTR.findall(page), "the attribute-only rule cannot see a t()-only key"


def test_the_detector_ignores_calls_that_are_not_translations():
    """`.get('Retry-After')` is not a translation call, and matching it invents missing keys."""
    sample = "r.headers.get('Retry-After'); document.createElement('span'); el.set('content-type', 1);"
    assert T_CALL.findall(sample) == []


def test_the_detector_still_finds_a_real_call():
    assert T_CALL.findall("const x = t('recentEmpty') + t(\"agentUnknown\");") == [
        "recentEmpty", "agentUnknown"]


if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([__file__, "-q"]))
