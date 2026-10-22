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
from html.parser import HTMLParser
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
INDEX = REPO / "docs" / "index.html"
# #3641: the registration form moved to its own page, and the page shares the site's one
# dictionary. So the dictionary now has two surfaces, and the rules below are about the pair:
# every key must be reachable from one of them, and every key either of them reaches must exist.
REGISTER = REPO / "docs" / "register" / "index.html"
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


@pytest.fixture(scope="module")
def register_page() -> str:
    return REGISTER.read_text(encoding="utf-8")


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


def test_every_key_the_register_page_renders_exists_in_both_dictionaries(register_page):
    """The register page reads the same dictionary, so its keys are held to the same rule."""
    problems = {lang: missing(register_page, set(dictionary(lang))) for lang in ("en", "zh")}
    problems = {lang: keys for lang, keys in problems.items() if keys}
    assert not problems, (
        f"these keys are rendered on the register page but absent, so the page shows the "
        f"identifier instead of the copy: {problems}"
    )


def test_no_key_in_the_dictionaries_is_dead(page, register_page):
    """A key is dead when *no* surface reaches it.

    The dictionary is the site's, and the site has two pages that read it: the homepage and the
    register page (#3641). The rule is still one rule — a dictionary entry nothing renders is the
    correct wording sitting one line away from the wrong one being shipped — but the surfaces are
    a pair, so the check is over the pair.
    """
    keys = set(dictionary("en"))
    dead = sorted(keys - (referenced(page, keys) | referenced(register_page, keys)))
    assert not dead, (
        f"nothing on either page reaches {dead}. Either wire it up or delete it — an unused key is "
        f"how the *correct* wording for a number sat in the dictionary while a wrong one shipped"
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


# ── Quickstart (#1894): the block this issue is about ─────────────────────────────────────────────
#
# The parity rules above cannot see the failure #1894 is named after: Quickstart prose written
# straight into the HTML with no `data-i18n` attribute. That adds no key to either dictionary and
# removes none, so every rule above stays green while Chinese mode shows the English sentence —
# the same silent half-translation `README.zh-CN.md` fell into. The block is therefore checked as
# text, not as keys: whatever a visitor can read there must either be keyed, or be a command /
# sample payload / example query (those are inputs and outputs, not copy).

QS_BLOCK = re.compile(r'<div id="quickstart-section".*?(?=<!-- Voices)', re.S)


class _ProseOutsideSurfaces(HTMLParser):
    """Visible text of the Quickstart block that is not behind a translation surface.

    Opaque (never collected): `script`/`style`, anything carrying `data-i18n`(-placeholder),
    and the command/sample containers (`.qs-cmd`, `code`, `pre`).
    """

    VOID = {"br", "hr", "img", "input", "meta", "link", "source", "wbr", "area", "base", "col", "embed", "track"}
    NEVER_COPY = {"style", "script"}
    COPYLESS = {"code", "pre"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._stack: list[tuple[str, bool]] = []  # (tag, opaque)
        self.chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in self.VOID:
            return
        ad = dict(attrs)
        classes = (ad.get("class") or "").split()
        opaque = (
            tag in self.NEVER_COPY
            or tag in self.COPYLESS
            or "qs-cmd" in classes
            or "data-i18n" in ad
            or "data-i18n-placeholder" in ad
        )
        self._stack.append((tag, opaque))

    def handle_endtag(self, tag: str) -> None:
        for i in range(len(self._stack) - 1, -1, -1):
            if self._stack[i][0] == tag:
                del self._stack[i:]
                break

    def handle_data(self, data: str) -> None:
        if self._stack and not any(opaque for _, opaque in self._stack):
            self.chunks.append(data)


def quickstart_prose(page: str) -> list[str]:
    """Hardcoded UI copy in the Quickstart block: visible text that is not keyed and not a
    command/sample. Step numbers and separators are punctuation; JSON payloads start with `{`/`[`.
    """
    m = QS_BLOCK.search(page)
    assert m, "could not find #quickstart-section in docs/index.html — did the markup change shape?"
    parser = _ProseOutsideSurfaces()
    parser.feed(m.group(0))
    leftovers = []
    for raw in parser.chunks:
        s = " ".join(raw.split())
        if not s:
            continue
        if re.fullmatch(r"[\d\W]+", s):  # step numbers, · separators
            continue
        if s[0] in "{[":  # sample response payload
            continue
        leftovers.append(s)
    return leftovers


def test_quickstart_ui_copy_is_not_hardcoded_in_the_html(page):
    """#1894 goal 1 / 验收 1: every sentence a visitor reads in Quickstart goes through `data-i18n`."""
    assert quickstart_prose(page) == [], (
        "hardcoded UI copy in the Quickstart block — give it a data-i18n key and add that key to "
        f"both locale files instead: {quickstart_prose(page)}"
    )


def test_quickstart_zh_values_are_chinese_not_english_copies(page):
    """#1894 验收 1, the dictionary side: a key can exist in `zh.json` and still show English.

    `switchLang` falls back to the en value when zh lacks the key — and an *empty* or byte-identical
    English value in `zh.json` has the same effect while looking like coverage. Quickstart keys must
    therefore carry real Chinese copy (CJK, or at least text that differs from the English string).
    """
    en, zh = dictionary("en"), dictionary("zh")
    qs_keys = sorted({k for k in ATTR.findall(page) if k.startswith("qs")})
    assert len(qs_keys) >= 12, f"only {len(qs_keys)} qs* keys on the page — did the Quickstart markup change?"
    untranslated = []
    for k in qs_keys:
        zh_v, en_v = zh.get(k, ""), en.get(k, "")
        if not zh_v.strip():
            untranslated.append((k, zh_v or "<missing>"))
        elif zh_v == en_v and re.search(r"[A-Za-z]{3,}", zh_v):
            untranslated.append((k, zh_v))
    assert not untranslated, (
        f"these Quickstart keys are in zh.json but still read as English (or are empty), so Chinese "
        f"mode would show them unchanged: {untranslated}"
    )


# ── and it can go red ────────────────────────────────────────────────────────────────────────────

def test_a_key_used_only_through_t_is_caught(register_page):
    """The exact regression: a `t()`-only key, which the attribute-only gate could not see."""
    dropped = "regOptionGithub"
    assert dropped in dictionary("en") and dropped in dictionary("zh")
    without = {k: v for k, v in dictionary("en").items() if k != dropped}
    assert missing(register_page, set(without)) == [dropped]


def test_a_dead_key_is_caught(page, register_page):
    keys = set(dictionary("en")) | {"aKeyNothingRenders"}
    reached = referenced(page, keys) | referenced(register_page, keys)
    assert sorted(keys - reached) == ["aKeyNothingRenders"]


def test_the_old_attribute_only_gate_would_have_missed_this(register_page):
    """Why the widened gate exists, demonstrated rather than asserted in prose.

    `referenced()` is the new rule; the old one is `ATTR.findall(page)` alone. On the page as it
    stands the two agree — the seven `t()`-only keys were fixed by adding them. So the difference is
    shown the only honest way: by removing one of them again and watching which rule notices.
    """
    keys = set(dictionary("en")) - {"regViaIssue"}
    assert missing(register_page, keys) == ["regViaIssue"], "the widened rule notices"
    # The attribute-only rule sees neither `t()` calls nor `${key}` placeholders, so it reports
    # nothing here — which is exactly why the previous gate passed while the panel shipped raw
    # identifiers.
    assert "regViaIssue" not in ATTR.findall(register_page), (
        "the attribute-only rule cannot see a t()-only key"
    )


def test_the_detector_ignores_calls_that_are_not_translations():
    """`.get('Retry-After')` is not a translation call, and matching it invents missing keys."""
    sample = "r.headers.get('Retry-After'); document.createElement('span'); el.set('content-type', 1);"
    assert T_CALL.findall(sample) == []


def test_the_detector_still_finds_a_real_call():
    assert T_CALL.findall("const x = t('recentEmpty') + t(\"agentUnknown\");") == [
        "recentEmpty", "agentUnknown"]


if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([__file__, "-q"]))


# ── the search page's own dictionary ──────────────────────────────────────────────────────────────
# It carries an inline `I18N` object rather than `docs/locales/*.json` (a single page's strings), so
# the homepage gate above cannot see it. Before this, the page's *results area* was English in both
# languages: "Why this matched", the section labels, the fold toggle, the no-match help, the feedback
# alert. A zh visitor got a translated heading over an English body.

SEARCH = REPO / "docs" / "search" / "index.html"
HARDCODED_BEFORE = (
    "Why this matched", "Common references (", "Try using fewer keywords",
    "Feedback copied to clipboard.",
)


@pytest.fixture(scope="module")
def search_page() -> str:
    return SEARCH.read_text(encoding="utf-8")


def search_dictionary(page: str) -> dict[str, set[str]]:
    """The page's two inline maps, as key sets: the `en:` / `zh:` blocks, keys four spaces in."""
    block = re.search(r"const I18N = \{(.*?)\n\};", page, re.S)
    assert block, "the inline I18N object is gone"
    out: dict[str, set[str]] = {}
    for lang, body in re.findall(r"(\w+):\s*\{(.*?)\n  \}", block.group(1), re.S):
        out[lang] = set(re.findall(r"^    (\w+):", body, re.M))
    return out


def test_the_search_page_translates_both_languages_identically(search_page):
    maps = search_dictionary(search_page)
    assert set(maps) == {"en", "zh"}, sorted(maps)
    assert maps["en"] == maps["zh"], sorted(maps["en"] ^ maps["zh"])


def test_every_key_the_search_page_uses_exists_in_its_dictionary(search_page):
    keys = search_dictionary(search_page)["en"]
    used = set(T_CALL.findall(search_page)) | set(ATTR.findall(search_page))
    unknown = sorted(used - keys)
    assert not unknown, f"these keys are used but not defined (the page would render the raw key): {unknown}"


def test_the_results_area_is_not_hardcoded_english(search_page):
    """The strings that were English in both languages, checked as absent from the render code.

    Comments are stripped first: the code explains *why* each string moved, and quoting the old text
    in that explanation is the point, not a leak.
    """
    body = re.sub(r"const I18N = \{.*?\n\};", "", search_page, flags=re.S)
    body = re.sub(r"^\s*//.*$", "", body, flags=re.M)
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.S)
    leaked = [s for s in HARDCODED_BEFORE if s in body]
    assert not leaked, f"still hardcoded in the render path: {leaked}"
