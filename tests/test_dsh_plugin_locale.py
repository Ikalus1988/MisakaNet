#!/usr/bin/env python3
"""The two dictionaries must stay in step, and every key the code asks for must exist in both.

`lib/client.js` carries its dictionaries inline — `locale/*.json` are the *package metadata* the host reads
for the plugin page's title and description (`dsh-app-boot`'s `dictionariesOf`), not the UI copy, which goes
through `ctx.locale`. Two failure modes are silent: a key added to English only (a Chinese reader gets the
English string, or the raw key), and a `T("…")` call whose key was never added at all (the surface shows the
key). Both are caught here.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CLIENT = REPO / "lib/client.js"


def _dict_blocks() -> tuple[str, str]:
    text = CLIENT.read_text(encoding="utf-8")
    en = re.search(r"\n\t\tvar en = \{(.*?)\n\t\t\};", text, re.S)
    zh = re.search(r"\n\t\tvar zh = \{(.*?)\n\t\t\};", text, re.S)
    assert en, "the English dictionary is no longer a `var en = {…}` block"
    assert zh, "the Chinese dictionary is no longer a `var zh = {…}` block"
    return en.group(1), zh.group(1)


def _keys(block: str) -> set[str]:
    return set(re.findall(r'"([a-z][\w.]*)":\s*"', block))


def test_both_dictionaries_declare_the_same_keys():
    en, zh = _dict_blocks()
    en_keys, zh_keys = _keys(en), _keys(zh)
    assert en_keys, "the English dictionary is empty"
    assert en_keys == zh_keys, (
        f"missing from zh: {sorted(en_keys - zh_keys)}; missing from en: {sorted(zh_keys - en_keys)}")


def test_every_key_the_code_asks_for_exists():
    text = CLIENT.read_text(encoding="utf-8")
    asked = set(re.findall(r'T\(\s*"([a-z][\w.]*)"', text))
    en_keys = _keys(_dict_blocks()[0])
    assert asked, "no `T(\"key\")` calls found; the wiring moved"
    assert asked <= en_keys, f"asked for but never declared: {sorted(asked - en_keys)}"


def test_package_metadata_is_localized():
    """The plugin page's title and description come from these files, one per language."""
    for lang in ("en", "zh"):
        path = REPO / "locale" / f"{lang}.json"
        assert path.is_file(), f"{path.relative_to(REPO)} is missing (the host reads ./locale/*.json)"
        meta = json.loads(path.read_text(encoding="utf-8")).get("meta", {})
        assert meta.get("title") and meta.get("description"), f"{lang}.json needs meta.title and meta.description"
    zh_title = json.loads((REPO / "locale/zh.json").read_text(encoding="utf-8"))["meta"]["title"]
    assert any("\u4e00" <= ch <= "\u9fff" for ch in zh_title), "the Chinese metadata is not in Chinese"


def test_the_locale_files_ship():
    """`files` decides what npm publishes; a locale folder left out is a localization nobody receives."""
    listed = json.loads((REPO / "package.json").read_text(encoding="utf-8")).get("files", [])
    assert "locale/" in listed or "locale" in listed, f"package.json files does not include locale/: {listed}"


# ── the completeness rule ───────────────────────────────────────────────────────────────────────────
#
# The dictionaries above only help if the code actually asks them. This walks every `h(...)` call in the
# client bundle and looks at its **children** (argument three onward — argument two is the props object), so
# "a string the reader can see" is a syntactic fact rather than a guess. Anything left is either brand or
# technical text, or copy that never made it into the dictionaries.

PROPS = r'[A-Za-z-]+:\s*"'
#: Attribute and CSS values that reach a children chunk but are never read as prose. Anything else that is
#: visible must come from the dictionaries.
TECHNICAL = {"MisakaNet", "MCP", "misakanet.org", "misakanet", "×", "→", "·", "E4", "GET",
             "aria-label", "target", "rel", "role", "title", "d", "viewBox", "fill", "stroke",
             "transparent", "not-allowed", "relative", "absolute", "fixed", "inherit", "currentColor",
             "_blank", "noreferrer", "true", "false", "auto", "none", "pointer", "center", "wrap",
             "pre-wrap", "block", "inline-flex", "streamable-http", "monospace", "Canvas", "CanvasText"}
CSSISH = re.compile(r"(px|rem|rgba?\(|Canvas|#[0-9a-fA-F]{3,6}|solid|flex|grid|auto|monospace|pre-wrap|^wrap$|^center$|^pointer$|^none$|^block$|^inherit$)")


def _arguments(code: str, open_paren: int) -> list[tuple[int, int]]:
    """Top-level argument spans of the call whose `(` is at `open_paren`."""
    depth, index, spans, start, quote = 0, open_paren, [], open_paren, None
    while index < len(code):
        char = code[index]
        if quote:
            if char == "\\":
                index += 2
                continue
            if char == quote:
                quote = None
        elif char in "\"'":
            quote = char
        elif char == "(":
            depth += 1
            if depth == 1:
                start = index + 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                spans.append((start, index))
                return spans
        elif char == "," and depth == 1:
            spans.append((start, index))
            start = index + 1
        index += 1
    return spans


def _strip_calls(chunk: str, name: str) -> str:
    """Remove every `name(...)` call from a chunk, balanced — nested calls included."""
    pattern = re.compile(rf"\b{name}\(")
    while True:
        call = pattern.search(chunk)
        if not call:
            return chunk
        spans = _arguments(chunk, call.end() - 1)
        if not spans:
            return chunk
        chunk = chunk[:call.start()] + chunk[spans[-1][1] + 1:]


def _strip_nested_calls(chunk: str) -> str:
    """Remove nested `h(...)` calls from a children chunk.

    Without this the outer call's text contains the inner call's tag name and props, and the rule drowns in
    `"div"`, `"span"`, `"center"` — the inner calls are scanned on their own turn.
    """
    while True:
        call = re.search(r"\bh\(", chunk)
        if not call:
            return chunk
        spans = _arguments(chunk, call.end() - 1)
        if not spans:
            return chunk
        chunk = chunk[:call.start()] + chunk[spans[-1][1] + 1:]
        if not spans:
            return chunk


def untranslated_copy(source: str) -> list[str]:
    """Visible strings rendered as `h()` children that do not go through `T(...)`."""
    code = source[source.index("var T = function (key, params)"):]
    code = re.sub(r"/\*.*?\*/", "", code, flags=re.S)
    code = re.sub(r"(?m)^\s*//.*$", "", code)
    found: list[str] = []
    for call in re.finditer(r"\bh\(", code):
        for start, end in _arguments(code, call.end() - 1)[2:]:
            chunk = _strip_nested_calls(code[start:end])
            chunk = _strip_calls(chunk, "T")                              # already translated
            chunk = re.sub(PROPS + r'"(?:[^"\\]|\\.)*"', "", chunk)     # props, not children
            chunk = re.sub(r'"(?:[a-z-]+)":\s*', "", chunk)               # a quoted key is not copy
            chunk = re.sub(r'[!=]==?\s*"(?:[^"\\]|\\.)*"', "", chunk)   # values compared, not shown
            for literal in re.finditer(r'"((?:[^"\\]|\\.)*)"', chunk):
                text = literal.group(1)
                if not text.strip() or text in TECHNICAL or CSSISH.search(text):
                    continue
                # What is left has to *look like prose*: two words, a capitalised word, or an ellipsis.
                # Without that bar every attribute value and CSS keyword in a nested literal arrives as a
                # finding, and a rule that cries wolf is a rule people switch off.
                if not (re.search(r"[A-Za-z]{2,}\s+[A-Za-z]{2,}", text)
                        or re.match(r"^[A-Z][A-Za-z]{2,}", text)
                        or ("…" in text and re.search(r"[A-Za-z]", text))):
                    continue
                found.append(text)
    return found


def test_every_visible_string_goes_through_the_dictionaries():
    """The panel, the cards and the tool rows: if a reader can see it, `T` produced it."""
    left = untranslated_copy(CLIENT.read_text(encoding="utf-8"))
    assert left == [], (
        "these strings are rendered but never translated — add them to `en` and `zh` and wrap them in `T`: "
        + repr(left[:6]))


def test_the_completeness_rule_can_go_red():
    """Replayed the way `test_workflow_inventory.py` does it: a mutated copy must trip the same rule."""
    source = CLIENT.read_text(encoding="utf-8")
    assert untranslated_copy(source) == [], "the unmutated source must be clean for the replay to mean anything"
    mutated = source.replace('T("panel.asked")', '"What this session asked"', 1)
    assert mutated != source, "the mutation did not take — update the replay with the code"
    assert "What this session asked" in untranslated_copy(mutated), "the completeness rule did not fire"
