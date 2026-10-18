#!/usr/bin/env python3
"""#1893 — the Quickstart copy buttons must put the code block in the clipboard, byte for byte.

What was wrong before this change: the six Quickstart steps showed commands the reader had to
select by hand. The one copy button on the page (`copyAndToast`) copied a *hardcoded* string
that does not match the code beside it, and its toast logic was fused into that function, so
there was nothing to reuse for the Quickstart blocks.

Four things are pinned here, one per acceptance item:

1. **Every code block gets a copy button, and the clipboard receives that block's text
   verbatim.** "Verbatim" is the whole point: the payload is the element's `textContent` — the
   string the reader sees — and nothing may trim it, re-encode it (`innerHTML` would hand back
   `&amp;` where the block shows `&`) or re-wrap it (`innerText` folds the curl blocks'
   continuations). The goldens below are the exact bytes of each block; the behavioural half
   runs the page's own `copyQS` under node against a DOM stub and compares the recorded write
   to those same bytes, with a stub `innerHTML`/`innerText` that would poison a wrong read.
2. **Every step carries one concrete self-check** — an executable command or an observable
   signal ("claude mcp list … lists misakanet", "the response has results, or no_match …"),
   never "it should just work".
3. **The buttons are labelled and keyboard-reachable**: real `<button type="button">`
   elements (native Enter/Space activation) with an `aria-label`.
4. **No build step and no external JS** was introduced: the handler is inline in the page's
   existing script, and the only external `<script src>` on the page is still DOMPurify.

The i18n contract for the new sentences lives in `tests/test_site_i18n.py` (#1894): every
sentence inside `#quickstart-section` is behind `data-i18n`, and its `zh.json` value is real
Chinese. That file is owned by #1894; this one asserts the copy/keyboard behaviour.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
INDEX = REPO / "docs" / "index.html"
LOCALES = {lang: REPO / "docs" / "locales" / f"{lang}.json" for lang in ("en", "zh")}
QS_BLOCK = re.compile(r'<div id="quickstart-section".*?(?=<!-- Voices)', re.S)

# The exact bytes of every code block in the Quickstart — what the reader sees and therefore
# what the clipboard must hold. These are not decoration: if the HTML gains a trailing newline
# before `</div>`, or an entity is written where the block should show `&`, `textContent`
# changes and this list must change with it. That is the "逐字一致" contract made checkable.
GOLDEN_TEXT = {
    "qs-a1": "npx @misaka-net/misakanet-setup",
    "qs-a2": "npx @misaka-net/misakanet-setup --verify",
    "qs-a3q1": "switch vision model",
    "qs-a3q2": "context window exceeded",
    "qs-b1": (
        "curl -sS https://misakanet.org/mcp \\\n"
        "  -H 'Content-Type: application/json' -H 'Accept: application/json' \\\n"
        "  -H 'MCP-Protocol-Version: 2025-06-18' -H 'Origin: https://misakanet.org' \\\n"
        "  -d '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/call\",\n"
        "       \"params\":{\"name\":\"misakanet_search\",\"arguments\":{\"query\":\"database is locked\",\"top\":3}}}'"
    ),
    "qs-b2": (
        '{"structuredContent":{"source":"worker-bm25",\n'
        '  "results":[{"id":"hermes-state-database-lock-issues-cleanup-protocol",\n'
        '              "title":"Hermes State Database Lock Issues - Cleanup Protocol"}]}}'
    ),
    "qs-b3": (
        "curl -sS https://misakanet.org/mcp \\\n"
        "  -H \"Content-Type: application/json\" \\\n"
        "  -H \"MCP-Protocol-Version: 2025-06-18\" \\\n"
        "  -d '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/call\",\"params\":{\"name\":\"misakanet_register\",\"arguments\":{\"agent_type\":\"your-agent\"}}}'"
    ),
}


class _Quickstart(HTMLParser):
    """The Quickstart section as the DOM sees it: code blocks by id, copy buttons by target.

    `convert_charrefs=True` is load-bearing — it decodes entities exactly the way the DOM's
    `textContent` does, so what this parser collects *is* what the browser would copy.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: dict[str, str] = {}
        self.code_elements: list[dict[str, str | None]] = []
        self.buttons: list[dict[str, str | None]] = []
        self.steps: list[dict[str, object]] = []
        self.links: list[str] = []
        self._capture: str | None = None
        self._capture_buf: list[str] = []
        self._depth = 0
        self._step: dict[str, object] | None = None

    def handle_starttag(self, tag: str, attrs) -> None:
        ad = dict(attrs)
        classes = (ad.get("class") or "").split()
        if ad.get("href"):
            self.links.append(ad["href"])
        if "qs-step" in classes:
            self._step = {"checks": []}
            self.steps.append(self._step)
        if "qs-check" in classes:
            key = ad.get("data-i18n")
            assert key, f"check line without data-i18n: {ad}"
            if self._step is not None:
                self._step["checks"].append(key)
        if tag == "button":
            self.buttons.append(
                {
                    "type": ad.get("type"),
                    "aria-label": ad.get("aria-label"),
                    "data-copy-target": ad.get("data-copy-target"),
                    "data-i18n": ad.get("data-i18n"),
                }
            )
        # Every code-looking element: the four `.qs-cmd` commands, the sample response
        # (`.qs-sample`), and the bare <code> example queries.
        is_code = "qs-cmd" in classes or "qs-sample" in classes or tag == "code"
        if is_code and self._capture is None:
            self.code_elements.append({"id": ad.get("id"), "tag": tag, "class": ad.get("class")})
            self._capture = ad.get("id") or ""
            self._capture_buf = []
            self._depth = 1
        elif self._capture is not None:
            self._depth += 1

    def handle_endtag(self, tag: str) -> None:
        if self._capture is not None:
            self._depth -= 1
            if self._depth == 0:
                if self._capture:
                    self.blocks[self._capture] = "".join(self._capture_buf)
                self._capture = None

    def handle_data(self, data: str) -> None:
        if self._capture is not None:
            self._capture_buf.append(data)


def quickstart() -> _Quickstart:
    page = INDEX.read_text(encoding="utf-8")
    m = QS_BLOCK.search(page)
    assert m, "could not find #quickstart-section — did the markup change shape?"
    parser = _Quickstart()
    parser.feed(m.group(0))
    return parser


def _function_source(page: str, name: str) -> str:
    """`function name(...)` source, top level, brace-matched (the a11y gate's same trick)."""
    start = page.index(f"function {name}")
    opening = page.index("{", start)
    depth = 0
    for i in range(opening, len(page)):
        if page[i] == "{":
            depth += 1
        elif page[i] == "}":
            depth -= 1
            if depth == 0:
                return page[start : i + 1]
    raise AssertionError(f"unbalanced braces in function {name}")


# ── acceptance 1: every command block has a copy button, clipboard == block ────────────────────


def test_every_code_block_in_the_quickstart_has_exactly_one_copy_button():
    """Every segment a reader would paste — the four commands, the sample response, the two
    example queries — is the `data-copy-target` of exactly one button, and every button points
    at a real block. A block with no button is the defect this issue was filed for."""
    qs = quickstart()
    ids = [c["id"] for c in qs.code_elements]
    assert all(ids), f"code block without an id (cannot be a copy target): {qs.code_elements}"
    assert len(ids) == len(set(ids)), f"duplicate code-block ids: {ids}"
    assert set(ids) == set(GOLDEN_TEXT), (
        f"code blocks changed: {sorted(ids)} != {sorted(GOLDEN_TEXT)}"
    )
    targets = [b["data-copy-target"] for b in qs.buttons]
    assert all(targets), f"copy button without data-copy-target: {qs.buttons}"
    assert len(targets) == len(set(targets)), f"two buttons share a target: {targets}"
    assert set(targets) == set(ids), (
        f"button/block mismatch — untargeted: {sorted(set(ids) - set(targets))}, "
        f"dangling: {sorted(set(targets) - set(ids))}"
    )


def test_each_code_block_text_is_exactly_the_command_the_reader_sees():
    """The block text, read the way the DOM reads it (`textContent`: entities decoded, every
    newline and space intact), equals the golden bytes. Catches a reformatted `</div>` adding a
    trailing newline — the trap the issue names — and any entity drift."""
    qs = quickstart()
    for block_id, expected in GOLDEN_TEXT.items():
        got = qs.blocks[block_id]
        assert got == expected, f"{block_id}: {got!r} != {expected!r}"
        assert not got.endswith("\n"), f"{block_id} gained a trailing newline"
        assert not got.startswith("\n"), f"{block_id} gained a leading newline"


def test_the_copied_text_is_the_code_block_text_byte_for_byte():
    """Run the page's own `copyQS` against a DOM stub and compare the recorded clipboard write
    to the golden bytes. The stub gives the element a *different* `innerHTML` and `innerText`,
    so a handler that reached for either would copy the wrong string and fail here."""
    qs = quickstart()
    harness = _node_harness(INDEX.read_text(encoding="utf-8"), qs.blocks, force_fallback=False)
    result = _run_node(harness)
    assert result["writes"] == [GOLDEN_TEXT[b] for b in result["order"]], (
        f"clipboard payloads differ from the code blocks: {result}"
    )


def test_the_exec_command_fallback_copies_the_same_bytes():
    """The `document.execCommand('copy')` fallback must carry the identical string — the issue
    asks for both paths, and a fallback that trims would be a silent half-fix."""
    harness = _node_harness(
        INDEX.read_text(encoding="utf-8"), quickstart().blocks, force_fallback=True
    )
    result = _run_node(harness)
    assert result["execCommand"] is True, "the fallback never reached document.execCommand"
    assert result["textareaValues"] == [GOLDEN_TEXT[b] for b in result["order"]], (
        f"fallback payloads differ: {result}"
    )


def test_textcontent_passthrough_handles_entities_and_newlines():
    """The two traps named in the issue, on synthetic input: an entity (`&` inside the block is
    `&amp;` in the HTML and `&` in `textContent`) and a trailing newline. A handler that read
    `innerHTML` or trimmed would fail one of these."""
    weird = "echo 'a & b' > out.txt\n"
    harness = _node_harness(
        INDEX.read_text(encoding="utf-8"), {"qs-weird": weird}, force_fallback=False
    )
    result = _run_node(harness)
    assert result["writes"] == [weird], f"passthrough broke: {result}"


def test_the_copy_payload_is_textcontent_not_innerhtml_or_trimmed():
    """Static half of the byte-identity claim: the payload path is `textContent` end to end.
    `innerHTML` would hand back `&amp;`; `innerText` re-wraps; `trim()`/`replace()` would eat
    the curl blocks' leading spaces."""
    page = INDEX.read_text(encoding="utf-8")
    body = _function_source(page, "codeTextOf")
    assert ".textContent" in body, body
    assert "innerHTML" not in body and "innerText" not in body, body
    assert not re.search(r"\.(trim|replace|normalize)\s*\(", body), body
    copy_body = _function_source(page, "copyQS")
    assert "codeTextOf(" in copy_body, copy_body
    assert "innerHTML" not in copy_body and "innerText" not in copy_body, copy_body
    assert not re.search(r"\.(trim|replace|normalize)\s*\(", copy_body), copy_body


# ── acceptance 2: every step has a concrete self-check ─────────────────────────────────────────

# Tokens that make a check line *checkable*: a command the reader can run, or a field/signal
# they can look for in an output. A line with none of these is "应该就可以了" in disguise.
SIGNAL = re.compile(
    r"mcp list|no_match|\bresults\b|node_id|\btoken\b|exits? 0|lesson\b|\bid\b|\btitle\b|verify",
    re.I,
)
VAGUE = re.compile(r"should (just |be )?(work|be fine)|probably|hopefully|应该就可以", re.I)


def test_every_step_has_one_concrete_self_check_line():
    qs = quickstart()
    assert len(qs.steps) == 6, f"expected 6 steps, found {len(qs.steps)}"
    en = json.loads(LOCALES["en"].read_text(encoding="utf-8"))
    for i, step in enumerate(qs.steps):
        checks = step["checks"]
        assert checks, f"step {i + 1} has no self-check line"
        for key in checks:
            text = en.get(key, "")
            assert text, f"{key} missing from en.json"
            assert SIGNAL.search(text), f"{key} names no command or observable signal: {text!r}"
            assert not VAGUE.search(text), f"{key} is vague: {text!r}"


def test_the_track_a_signal_names_both_mcp_clients():
    """The issue's 轨A signal is `claude mcp list` / `codex mcp list` — both, because the
    reader may have either assistant. The pre-existing `qsAVerify` names only claude."""
    en = json.loads(LOCALES["en"].read_text(encoding="utf-8"))
    qs = quickstart()
    track_a = " ".join(en[k] for s in qs.steps[:3] for k in s["checks"])
    assert "claude mcp list" in track_a and "codex mcp list" in track_a, track_a


def test_the_track_b_signal_accepts_a_miss_as_success():
    """The issue's 轨B signal: `results`, or `no_match` + `intake` — a miss is also success."""
    en = json.loads(LOCALES["en"].read_text(encoding="utf-8"))
    qs = quickstart()
    track_b = " ".join(en[k] for s in qs.steps[3:] for k in s["checks"])
    assert "results" in track_b and "no_match" in track_b and "intake" in track_b, track_b


# ── acceptance 3: labelled, keyboard-triggerable buttons ───────────────────────────────────────


def test_every_copy_button_is_labelled_and_keyboard_reachable():
    """A `<button type="button">` is natively focusable and fires on Enter/Space — no extra JS
    needed. A div with onclick would pass a click test and fail a keyboard user."""
    qs = quickstart()
    assert qs.buttons, "no copy buttons found"
    for btn in qs.buttons:
        assert btn["type"] == "button", f"copy button without type=button: {btn}"
        assert (btn["aria-label"] or "").strip(), f"copy button without aria-label: {btn}"
        assert btn["data-i18n"], f"copy button label is not keyed for i18n: {btn}"
    section = QS_BLOCK.search(INDEX.read_text(encoding="utf-8")).group(0)
    assert not re.search(r'<div[^>]*onclick="copyQS', section), (
        "a copy trigger on a non-button element"
    )


# ── acceptance 4: no build step, no external JS ────────────────────────────────────────────────


def test_the_copy_handler_is_inline_and_no_external_js_was_added():
    """The handler ships in the page's existing inline script. The page's only external script
    is still DOMPurify — no CDN addition, no bundler, no npm."""
    page = INDEX.read_text(encoding="utf-8")
    assert "function copyQS(" in page, "copyQS is not inline in docs/index.html"
    srcs = re.findall(r'<script[^>]*\bsrc="([^"]+)"', page)
    assert srcs == [
        "https://cdnjs.cloudflare.com/ajax/libs/dompurify/3.4.16/purify.min.js"
    ], f"external script set changed: {srcs}"
    assert not re.search(r"<script[^>]*type=\"module\"", page), "a module script was added"
    pkg = json.loads((REPO / "package.json").read_text(encoding="utf-8"))
    assert "build" not in (pkg.get("scripts") or {}), "a build step appeared in package.json"


# ── the exit line and the shared toast ─────────────────────────────────────────────────────────


def test_the_stuck_line_points_at_start_and_the_troubleshooting_guide():
    """「没成功怎么办」— one line, two doors: /start and docs/troubleshooting.md."""
    qs = quickstart()
    assert any(h.startswith("/start") for h in qs.links), qs.links
    assert any("troubleshooting.md" in h for h in qs.links), qs.links


def test_copy_feedback_reuses_the_pages_one_toast():
    """One toast for the whole page: `copyQS` reports through the same `toast()` the register
    bar uses, and `#toast` stays the only feedback element. A second popup system is what the
    issue tells us not to invent."""
    page = INDEX.read_text(encoding="utf-8")
    assert page.count('id="toast"') == 1, "the toast element is no longer unique"
    copy_body = _function_source(page, "copyQS")
    assert "toast(" in copy_body, copy_body
    assert "alert(" not in copy_body, "copyQS reports through alert(), not the page toast"
    toast_body = _function_source(page, "toast")
    assert "getElementById('toast')" in toast_body, toast_body
    register_body = _function_source(page, "copyAndToast")
    assert "toast(" in register_body, "the register bar no longer shares the toast helper"


# ── running the real page JS ───────────────────────────────────────────────────────────────────


def _node_harness(page: str, blocks: dict[str, str], force_fallback: bool = False) -> str:
    """A node script that evals the page's own copy functions against a DOM stub.

    Only the clipboard path is taken from the page — `toast`/`flashCopied`/`t` are stubbed so
    the harness measures bytes, not UI. Each stub element carries a *different* `innerHTML` and
    `innerText` from its `textContent`, so a handler reaching for either copies the wrong
    string and the comparison fails."""
    sources = "\n".join(
        _function_source(page, n) for n in ("codeTextOf", "legacyCopy", "writeClipboard", "copyQS")
    )
    drop_clipboard = "delete navigator.clipboard;" if force_fallback else ""
    return f"""
'use strict';
const blocks = {json.dumps(blocks)};
const order = [];
const writes = [];
const textareaValues = [];
let execCommandCalled = false;
const elements = {{}};
for (const [id, text] of Object.entries(blocks)) {{
  elements[id] = {{
    textContent: text,
    // Deliberately different from textContent: a wrong read would copy these instead.
    innerHTML: text.replace(/&/g, '&amp;'),
    innerText: text.toUpperCase(),
  }};
}}
const document = {{
  getElementById(id) {{ return elements[id] || null; }},
  createElement() {{
    return {{ value: '', style: {{}}, setAttribute() {{}}, select() {{}} }};
  }},
  body: {{
    appendChild(ta) {{ textareaValues.push(ta.value); }},
    removeChild() {{}},
  }},
  execCommand(cmd) {{ execCommandCalled = cmd === 'copy'; return true; }},
}};
const navigator = {{
  clipboard: {{
    writeText(text) {{ writes.push(text); return Promise.resolve(true); }},
  }},
}};
{drop_clipboard}
function toast(message) {{ /* stub: feedback is not under test here */ }}
function flashCopied(btn) {{ /* stub */ }}
function t(key) {{ return key; }}
{sources}
(async () => {{
  for (const id of Object.keys(blocks)) {{
    order.push(id);
    await copyQS({{ getAttribute: (a) => (a === 'data-copy-target' ? id : null) }});
  }}
  process.stdout.write(JSON.stringify({{ order, writes, textareaValues, execCommand: execCommandCalled }}));
}})();
"""


def _run_node(harness: str) -> dict:
    node = shutil.which("node")
    if node is None:  # pragma: no cover - node is on every CI runner this repo uses
        pytest.skip("node is not on PATH; the behavioural half needs it")
    proc = subprocess.run(
        [node, "-e", harness], capture_output=True, text=True, timeout=60, check=False
    )
    assert proc.returncode == 0, f"node harness failed:\n{proc.stderr}"
    return json.loads(proc.stdout)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([__file__, "-q"]))
