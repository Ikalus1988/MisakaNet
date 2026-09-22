"""The registration block must not sell registration as the way in (#2057).

Reading has been anonymous and unlimited since 2026-09-18 (`AGENTS.md` §3.3): registration only
unlocks the write tools (`write_lesson` / `preflight`) and mints a stable pseudonymous node. Three
spots on the homepage still told the older story — "没有 GitHub？直接注册" as the way in, "最新注册"
as if the node count measured members, and a bare "Agent 类型" label — and both locale dictionaries
carried the same framing, so editing the HTML default text alone changes nothing: the locale value
overwrites it at render time (`switchLang` writes `el.textContent`), and a key missing from one
dictionary falls back to English silently — the trap that left a statistic in English in zh mode.

The second thing pinned here is the **protocol**. `Agent 类型` is copy; `Agent 类型: **X**` is the
machine-readable line the registration issue body is built from and read back by. A global replace
of the visible label rewrites both and breaks registration while every other test stays green, so
builder and parser are asserted *by shape and by round trip*, and
`test_a_global_label_replace_is_caught` proves this file can go red rather than merely passing.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "docs" / "index.html"
LOCALES = {lang: ROOT / "docs" / "locales" / f"{lang}.json" for lang in ("en", "zh")}

# The machine-readable surface of the registration flow.
PROTOCOL_BUILDER = re.compile(
    r"const agentLine = `\\nAgent 类型: \*\*\$\{selectedAgent\.toUpperCase\(\)\}\*\*`"
)
PROTOCOL_PARSER = re.compile(
    r"body\.match\(/Agent\\s\*类型\[：:\]\\s\*\\\*\\\*\(\\w\+\)\\\*\\\*/i\)"
)
# The JS regex literal on its own, so the round-trip test can compile and run it.
JS_PARSER_LITERAL = re.compile(r"/(Agent\\s\*类型\[：:\]\\s\*\\\*\\\*\(\\w\+\)\\\*\\\*)/i")
PROTOCOL_TEMPLATE = "Agent 类型: **YOUR_AGENT**"


@pytest.fixture(scope="module")
def page() -> str:
    return INDEX.read_text(encoding="utf-8")


def locale(lang: str) -> dict[str, str]:
    return json.loads(LOCALES[lang].read_text(encoding="utf-8"))


def default_text(page: str, key: str) -> str:
    """Text between a `data-i18n="key"` element's tags.

    That is what renders before the locale file loads, and what renders at all without JS.
    """
    match = re.search(rf'data-i18n="{re.escape(key)}"[^>]*>(.*?)</', page, re.S)
    assert match, f"no element carries data-i18n={key!r}"
    return match.group(1).strip()


# ── the three copy spots ──────────────────────────────────────────────────────


def test_the_title_says_reading_needs_no_registration(page: str) -> None:
    assert "注册只解锁写入工具" in default_text(page, "registerTitle")
    assert "注册只解锁写入工具" in locale("zh")["registerTitle"]
    assert "write tools" in locale("en")["registerTitle"]
    # The old framing, in both languages.
    assert "没有 GitHub" not in locale("zh")["registerTitle"]
    assert "No GitHub" not in locale("en")["registerTitle"]


def test_the_description_describes_registration_correctly() -> None:
    zh, en = locale("zh")["registerDesc"], locale("en")["registerDesc"]
    assert "写入类工具" in zh and "都无需注册" in zh
    assert "write tools" in en and "need no registration" in en
    # It used to promise "access to the knowledge base", which registration no longer gates.
    assert "访问权限" not in zh
    assert "access to the Misaka Network knowledge base" not in en


def test_the_node_count_is_labelled_as_nodes_not_members(page: str) -> None:
    assert "最近创建的 node" in default_text(page, "recentSection")
    assert locale("zh")["recentSection"] == "最近创建的 node"
    assert locale("en")["recentSection"] == "Recently created nodes"
    for lang in ("en", "zh"):
        assert "最新注册" not in locale(lang)["recentSection"]


def test_the_node_count_carries_an_honest_annotation(page: str) -> None:
    zh, en = locale("zh")["recentNodesNote"], locale("en")["recentNodesNote"]
    assert "自声明" in zh and "无需注册" in zh
    assert "self-declared" in en and "no registration" in en
    # …and it has to sit next to the number, not merely exist in the dictionary.
    assert 'id="recent-count"' in page
    assert page.index('data-i18n="recentNodesNote"') > page.index('id="recent-count"')


def test_the_agent_type_label_is_marked_optional_and_statistical(page: str) -> None:
    assert "可选" in default_text(page, "agentTypeLabel")
    assert "可选" in locale("zh")["agentTypeLabel"] and "仅统计" in locale("zh")["agentTypeLabel"]
    assert "optional" in locale("en")["agentTypeLabel"]
    assert "statistics only" in locale("en")["agentTypeLabel"]
    # The "why ask" line is translatable too, not English-only.
    assert "自声明" in locale("zh")["agentTypeHint"]
    assert "self-declared" in locale("en")["agentTypeHint"]


# ── the i18n trap ─────────────────────────────────────────────────────────────


def test_every_key_the_page_renders_exists_in_both_dictionaries(page: str) -> None:
    used = set(re.findall(r'data-i18n="([^"]+)"', page)) | set(
        re.findall(r'data-i18n-placeholder="([^"]+)"', page)
    )
    assert used, "no i18n keys found — did the page stop using data-i18n?"
    for lang in ("en", "zh"):
        missing = sorted(used - set(locale(lang)))
        assert not missing, f"{lang}.json is missing keys the page renders: {missing}"


def test_the_two_dictionaries_have_the_same_keys() -> None:
    assert set(locale("en")) == set(locale("zh"))


# ── the protocol (the AC's required proof) ────────────────────────────────────


def test_the_registration_protocol_strings_are_untouched(page: str) -> None:
    assert PROTOCOL_BUILDER.search(page), "the issue-body builder changed shape"
    assert PROTOCOL_PARSER.search(page), "the issue-body parser changed shape"
    assert PROTOCOL_TEMPLATE in page, "the registration issue template lost its protocol line"


def test_the_builder_output_is_parsed_by_the_parser(page: str) -> None:
    """The two halves must stay compatible: build the line the way the page does, run it through the
    parser's own regex, and require the agent type back."""
    match = JS_PARSER_LITERAL.search(page)
    assert match, "the parser regex is no longer a JS literal we can compile"
    pattern = re.compile(match.group(1))
    built = f"Agent 类型: **{'hermes'.upper()}**"  # what `agentLine` emits
    assert pattern.search(built), f"{built!r} is not matched by the page's own parser"
    assert pattern.search(built).group(1) == "HERMES"


def test_a_global_label_replace_is_caught(page: str) -> None:
    """Guard-the-guard: the failure mode the issue names is a *global* replace of the visible label.

    Simulating it shows which halves are actually load-bearing. The builder and the issue template
    spell the label literally (`Agent 类型: **…`), so a global replace rewrites the line the
    registration issue body is built from — registration breaks. The parser is spelled
    `Agent\\s*类型`, so it survives that particular replace and keeps matching the *old* wording: a
    page that writes one label and parses another, with every other test still green.

    That asymmetry is why all three are pinned separately instead of by one grep for the label.
    """
    mutated = page.replace("Agent 类型", "智能体类型")
    assert mutated != page, "the label was not found — the pins above match nothing"
    assert not PROTOCOL_BUILDER.search(mutated), "the builder pin has no teeth"
    assert PROTOCOL_TEMPLATE not in mutated, "the template pin has no teeth"
    # …and the parser survives, which is the trap rather than a flaw in the pin.
    assert PROTOCOL_PARSER.search(mutated)
    assert PROTOCOL_PARSER.search(page)
