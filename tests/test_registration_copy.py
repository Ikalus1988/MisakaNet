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

Two additions after that:

* **The count is labelled as what it counts.** `#recent-count` is filled from a GitHub Issues query
  for `labels=registration&per_page=100`, so it counts registration-labelled issues — capped at 100.
  It is not a node count, and "最近创建的 node" claimed one. The tail `· showing latest 6` was
  hardcoded English with no locale key and said nothing the "view all" link below does not.
* **The client list is not hand-maintained in three places.** The selector offered five clients, the
  npm installer wires ten, the bootstrap installer eleven — and `let agentType = 'hermes'` meant
  every registration whose type could not be read was *displayed as Hermes*. The selector is now
  derived from the installers' own list (minus the bootstrap-only `dsh`, plus a free-text `other`),
  an unreadable type renders as unknown, and the gate below compares the page against both
  installers so the three lists cannot drift apart one commit at a time.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "docs" / "index.html"
LOCALES = {lang: ROOT / "docs" / "locales" / f"{lang}.json" for lang in ("en", "zh")}
NPM_INSTALLER = ROOT / "packages" / "misakanet-setup" / "bin" / "misakanet-setup.mjs"
PY_INSTALLER = ROOT / "integrations" / "agent-autostart" / "install_misakanet_agent.py"
WORKER = ROOT / "workers" / "register-proxy-sw.js"

# The executor of the registration issue body, where `agent_type` is sanitized and truncated.
WORKER_AGENT_MAX = re.compile(r"^const MAX_AGENT_TYPE = (\d+);", re.M)

# The selector's free-text escape hatch. Not a client, so it has no installer counterpart.
SITE_ONLY = {"other"}
# The bootstrap installer's extra target: a DSH `SKILL.md`, not an MCP config file, so the npm
# installer has no counterpart — and neither has a browser visitor registering *through* the site.
# `tests/test_installer_parity.py` owns the installer-vs-installer half of this contract.
PY_ONLY = {"dsh"}

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

# `client: 'agentKey',` rows of the page's own name → locale-key map, comment-tolerant.
AGENT_LABEL_ROW = re.compile(r"^\s{2}([a-z][a-z0-9-]*): '(agent[A-Za-z]+)',\s*(?://.*)?$", re.M)
# Any emoji or pictograph — the per-client brand glyphs that used to be the only thing
# distinguishing one option from another.
GLYPH = re.compile("[\U0001f000-\U0001faff\u2600-\u27bf\ufe0f]")


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


def npm_targets(text: str) -> list[str]:
    """The npm installer's `AGENTS` list — the extraction `test_installer_parity.py` also uses."""
    match = re.search(r"^const AGENTS = \[([^\]]+)\]", text, re.M)
    assert match, "the npm installer's AGENTS array moved; fix this gate rather than deleting it"
    return re.findall(r"'([^']+)'", match.group(1))


def python_targets(text: str) -> list[str]:
    match = re.search(r"^AGENTS = \(([^)]+)\)", text, re.M)
    assert match, (
        "the bootstrap installer's AGENTS tuple moved; fix this gate rather than deleting it"
    )
    return re.findall(r'"([^"]+)"', match.group(1))


def selector_block(page: str) -> str:
    """The `<div class="agent-selector">` container, delimited by div depth.

    Cutting to the first `</div>` would stop after the first option, and line numbers go stale the
    moment the form is reordered — so walk the tags and return the balanced element.
    """
    at = page.index('class="agent-selector"')
    start = page.rindex("<div", 0, at)
    depth, i = 0, start
    while i < len(page):
        if page.startswith("<div", i):
            depth, i = depth + 1, i + 4
        elif page.startswith("</div>", i):
            depth, i = depth - 1, i + 6
            if depth == 0:
                return page[start:i]
        else:
            i += 1
    raise AssertionError("the .agent-selector container is never closed")


def site_clients(page: str) -> list[str]:
    """Every `data-agent` value inside the selector, in the order the visitor sees them."""
    return re.findall(r'data-agent="([^"]+)"', selector_block(page))


def client_drift(offered, installed) -> tuple[list[str], list[str]]:
    """(clients only the page offers, clients only the installers offer)."""
    offered, installed = set(offered), set(installed)
    return sorted(offered - installed), sorted(installed - offered)


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


def test_the_registration_count_is_labelled_as_registrations_not_nodes(page: str) -> None:
    """The number is registration-labelled issues, so that is what the label may say.

    #2057 fixed the older "最新注册" (members) framing by calling it "最近创建的 node" — still a
    claim the number cannot support: it is capped at `per_page=100` and a deleted node never comes
    off it. The label now names the thing it counts, and the query it is counted from is pinned
    alongside it so the two cannot drift.
    """
    assert "最近注册记录" in default_text(page, "recentSection")
    assert locale("zh")["recentSection"] == "最近注册记录"
    assert locale("en")["recentSection"] == "Recent registrations"
    # Both languages name the thing the number counts…
    assert "注册记录" in locale("zh")["recentSection"]
    assert "registration" in locale("en")["recentSection"].lower()
    # …and neither keeps the members framing this block was fixed for in #2057.
    for lang in ("en", "zh"):
        assert "最新注册" not in locale(lang)["recentSection"]
    # What the label claims must be what the query returns…
    assert "labels=registration" in page
    # …and the old claims are gone, in both the dictionary and the HTML default.
    assert "最近创建的 node" not in page
    assert "Recently created nodes" not in page


def test_the_registration_block_is_translated_end_to_end(page: str) -> None:
    """Two strings in this block never reached the dictionaries: the empty state (zh only, so an
    English reader saw Chinese) and the "view all" link (English only, count and all)."""
    assert "暂无注册记录" not in page
    assert "View all ${registrations.length} registered nodes" not in page
    assert "t('recentEmpty')" in page, "the empty state is not read from the dictionaries"
    assert "formatText(t('recentViewAll'), { count: registrations.length })" in page, (
        "the view-all link must go through formatText with the {count} placeholder convention "
        "updateLessonCountSearch() already uses for searchPanelStats"
    )
    assert locale("zh")["recentEmpty"] == "暂无注册记录"
    assert not re.search(r"[\u4e00-\u9fa5]", locale("en")["recentEmpty"]), (
        "the English empty state is still Chinese"
    )
    for lang in ("en", "zh"):
        assert "{count}" in locale(lang)["recentViewAll"], f"{lang}.json lost the count placeholder"


def test_the_noise_tail_is_gone(page: str) -> None:
    """`· showing latest 6` duplicated the "view all" link in hardcoded English, with no key."""
    assert "showing latest" not in page
    assert "recent-showing" not in page


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


# ── the client list: one list, three places that used to disagree ─────────────


def test_the_selector_offers_exactly_the_clients_the_installers_wire(page: str) -> None:
    """The failure this catches: a client wired in the installer but not offered on the site (the
    visitor cannot declare it), or offered on the site but wired nowhere (a statistic for a tool
    nobody installs). `test_installer_parity.py` covers installer-vs-installer; this is the page.
    """
    offered = site_clients(page)
    assert len(offered) == len(set(offered)), f"duplicate data-agent values: {offered}"
    assert SITE_ONLY <= set(offered), f"the free-text escape hatch {sorted(SITE_ONLY)} is gone"
    installed = npm_targets(NPM_INSTALLER.read_text(encoding="utf-8"))
    only_page, only_installer = client_drift(set(offered) - SITE_ONLY, installed)
    assert not only_page, (
        f"the selector offers {only_page}, which no installer wires: a visitor would be counted "
        f"under a client that cannot exist"
    )
    assert not only_installer, (
        f"the installers wire {only_installer} but the selector does not offer it: those users can "
        f"only mis-declare themselves. Add the option (and its agent* locale key), or add it to "
        f"PY_ONLY/SITE_ONLY here with the reason"
    )


def test_the_installer_exception_this_gate_makes_is_still_the_real_one(page: str) -> None:
    """`dsh` is excluded from the page on purpose — the bootstrap installer's SKILL.md channel has
    no npm counterpart and no browser-visitor use. Recomputing that here means a *new*
    bootstrap-only client fails loudly instead of being swallowed by a stale exception list.
    """
    npm = set(npm_targets(NPM_INSTALLER.read_text(encoding="utf-8")))
    py = set(python_targets(PY_INSTALLER.read_text(encoding="utf-8")))
    assert py - npm == PY_ONLY, (
        f"the bootstrap installer gained {sorted(py - npm - PY_ONLY)} beyond the npm targets; "
        f"decide whether the selector must offer it, then update PY_ONLY"
    )
    assert PY_ONLY.isdisjoint(site_clients(page))


def test_adding_a_client_to_one_place_only_turns_this_gate_red(page: str) -> None:
    """Guard-the-guard, in the shape of `test_a_global_label_replace_is_caught`.

    The gate above is only worth having if a one-sided edit actually moves it, so make the two
    one-sided edits in the *real source text* and run them through the same comparison.
    """
    npm_src = NPM_INSTALLER.read_text(encoding="utf-8")
    offered = set(site_clients(page)) - SITE_ONLY
    assert client_drift(offered, npm_targets(npm_src)) == ([], [])

    # 1) a client added to the installer only.
    installer_drift = client_drift(
        offered, npm_targets(npm_src.replace("'kiro']", "'kiro', 'zencoder']"))
    )
    assert installer_drift == ([], ["zencoder"]), installer_drift

    # 2) a client added to the page only.
    page_drift = client_drift(
        set(site_clients(page.replace('data-agent="kiro"', 'data-agent="zencoder"'))) - SITE_ONLY,
        npm_targets(npm_src),
    )
    assert page_drift == (["zencoder"], ["kiro"]), page_drift

    # 3) and the mutation really is a mutation of what the gate reads.
    assert npm_targets(npm_src.replace("'kiro']", "'kiro', 'zencoder']")) != npm_targets(npm_src)
    assert site_clients(page.replace('data-agent="kiro"', 'data-agent="zencoder"')) != site_clients(
        page
    )


def test_the_options_share_one_neutral_presentation(page: str) -> None:
    """Five options used to be told apart by a brand emoji each (🤖⚡💻🐉🔧). They are gone: one
    uniform card, no glyph, no icon font, no sprite — and no child elements, which also keeps the
    options safe for `data-i18n` (`switchLang` writes `textContent`)."""
    block = selector_block(page)
    assert "agent-icon" not in page, "the per-client emoji spans are back"
    assert not GLYPH.search(block), (
        f"a glyph survives in the selector: {GLYPH.search(block).group(0)!r}"
    )
    options = re.findall(r'<div class="agent-option[^"]*"([^>]*)>(.*?)</div>', block, re.S)
    assert len(options) == len(site_clients(page)), "an option is not a single text-only div"
    shapes = set()
    for attrs, body in options:
        assert "<" not in body, f"an option carries a child element: {body!r}"
        assert body.strip(), "an option has no label"
        assert "data-i18n=" in attrs, f"an option label is not translatable: {attrs!r}"
        shapes.add(
            re.sub(
                r'aria-checked="(?:true|false)"',
                "aria-checked=X",
                re.sub(r'(?:data-agent|data-i18n)="[^"]*"', "data-X", attrs).replace(
                    " selected", ""
                ),
            )
        )
    assert len(shapes) == 1, f"the options are no longer uniform: {sorted(shapes)}"


def test_other_takes_cleaned_free_text_into_the_registration_flow(page: str) -> None:
    """The "other" option sends the visitor's own client name, cleaned like the worker's."""
    assert 'id="agent-other-input"' in page
    assert "cleanAgentText" in page and "[^A-Za-z0-9_-]" in page
    assert "slice(0, AGENT_TEXT_MAX)" in page
    # The cap is the worker's, not an independent constant that can drift from it.
    match = WORKER_AGENT_MAX.search(WORKER.read_text(encoding="utf-8"))
    assert match, "MAX_AGENT_TYPE moved in the worker; fix this gate rather than deleting it"
    assert f"const AGENT_TEXT_MAX = {match.group(1)};" in page
    assert f'maxlength="{match.group(1)}"' in page
    # Empty free text is an absence of information: it must not be recorded as a client.
    sync = re.search(r"function syncSelectedAgent\(\) \{(.*?)\n\}", page, re.S)
    assert sync, "syncSelectedAgent() is gone; the free text no longer reaches the flow"
    assert "cleanAgentText" in sync.group(1) and "'unknown'" in sync.group(1)
    # The success panel echoes what was recorded: a visitor who typed a client name must not be
    # shown "unknown" for it (which is what plain getAgentLabel() would render).
    assert "agentDisplayValue(selectedAgent)" in page


def test_every_client_the_selector_offers_renders_back_as_itself(page: str) -> None:
    """The round trip that matters for the timeline: the value the flow sends must come back out of
    the page's own parser and be findable in the page's own label map. A client offered by the
    selector but missing from the map shows up in the timeline as "unknown" — the mirror image of
    the Hermes misattribution, and just as wrong."""
    labels = dict(AGENT_LABEL_ROW.findall(page))
    assert labels, "AGENT_LABEL_KEYS moved; fix this gate rather than deleting it"
    offered = set(site_clients(page)) - SITE_ONLY
    missing = sorted(offered - set(labels))
    assert not missing, f"the selector offers {missing} with no locale key in AGENT_LABEL_KEYS"
    assert set(labels) - offered == {"cc"}, (
        "the label map carries clients the selector does not offer (only the legacy `cc` alias may)"
    )
    for lang in ("en", "zh"):
        absent = sorted(k for k in list(labels.values()) if k not in locale(lang))
        assert not absent, f"{lang}.json is missing {absent}, so those badges fall back to English"
    # The parser half: build the line the way the page builds it, parse it with the page's regex.
    match = JS_PARSER_LITERAL.search(page)
    assert match, "the parser regex is no longer a JS literal we can compile"
    pattern = re.compile(match.group(1))
    for client in sorted(offered):
        parsed = pattern.search(f"Agent 类型: **{client.upper()}**")
        assert parsed, f"{client!r} does not survive the page's own parser"
        assert parsed.group(1).lower() in labels, f"{client!r} parses to a value with no label"


def test_an_unreadable_agent_type_is_unknown_and_never_a_default_client(page: str) -> None:
    """The misattribution: `let agentType = 'hermes'` displayed every registration whose type could
    not be read as Hermes — a statistic that lied in the same direction for every parse miss."""
    assert "let agentType = 'hermes'" not in page
    parse = re.search(r"function parseAgentType\(body\) \{(.*?)\n\}", page, re.S)
    assert parse, "parseAgentType() moved; fix this gate rather than deleting it"
    body = parse.group(1)
    assert "return 'unknown';" in body, "a parse miss must be reported as unknown"
    # …and the rendered label for anything without a locale key is the unknown key.
    label = re.search(r"function getAgentLabel\(agentType\) \{(.*?)\n\}", page, re.S)
    assert label, "getAgentLabel() moved; fix this gate rather than deleting it"
    assert "AGENT_LABEL_KEYS[agentType]" in label.group(1)
    assert "t('agentUnknown')" in label.group(1)
    named = re.search(
        r"agent(?:Hermes|CC|Codex|OpenClaw|OpenCode|Codewhale|Cursor|Gemini|Copilot|Kiro)",
        label.group(1),
    )
    assert not named, f"a specific client ({named.group(0)}) is the fallback again"
    # The timeline reads the parsed value through the helper, not through the old inline copy.
    assert page.count("const agentType = parseAgentType(body);") == 2, (
        "both timeline loops must parse the same way"
    )
    # The only hardcoded client defaults left are the selector's own two variables: a client name
    # used as a parse fallback is exactly how the Hermes misattribution was written.
    defaults = re.findall(
        r"= '(?:hermes|claude|codex|openclaw|opencode|codewhale|cursor|gemini|copilot|kiro)'", page
    )
    assert defaults == ["= 'hermes'", "= 'hermes'"], f"unexpected client default(s): {defaults}"


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
