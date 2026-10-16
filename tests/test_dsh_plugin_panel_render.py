#!/usr/bin/env python3
"""The panel, actually rendered: one click, one vote, one visible consequence.

`tests/test_dsh_plugin_surface.py` pins the panel's rules as static properties of the source. This file
runs the bundle instead: it mounts the registered component through `apply()` with a stub React, seeds the
session log exactly as the transcript rows do, clicks the two affordances the owner asked for, and reads
back what happened.

Why a render rather than another regex: the acceptance list records that two of this panel's defects —
"1 reports" and the double `/api/helpful` round — were found by rendering and *not* by reading. A source
scan cannot answer "does the button reach the tree", "does one click post one vote", or "does the number
the click produced appear in the row". Layout, CSS and real-browser behaviour are still out of reach here;
the browser render the acceptance doc asks for (items E4/E5) remains owed and is named as owed there.

Run: python3 -m pytest tests/test_dsh_plugin_panel_render.py -q
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
CLIENT = REPO / "lib" / "client.js"
HARNESS = REPO / "tests" / "dsh_panel_render_harness.cjs"


def _render(client_file: Path = CLIENT) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node renders the client half")
    assert HARNESS.is_file(), "the render harness is a test asset of this file"
    done = subprocess.run([node, str(HARNESS), str(client_file)],
                          capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stderr[-800:]
    # The harness writes one JSON line; take the last line that parses, so a warning printed to stdout (a
    # different node version, a platform quirk) cannot turn a passing render into a decode error.
    for line in reversed(done.stdout.strip().splitlines()):
        try:
            return json.loads(line)
        except ValueError:
            continue
    raise AssertionError("the render harness printed no JSON result: " + done.stdout[-400:])


def test_one_click_posts_one_vote_with_the_fixed_source_label():
    """The panel's affordance performs the same action as the verdict row, and sends the same body."""
    result = _render()
    assert result["votePosts"] == 1, (
        "one click must post exactly one vote; the render measured " + str(result["votePosts"]))
    post = result["votePost"]
    assert post and post["url"] == "https://misakanet.org/api/helpful", post
    assert post["body"] == {"lesson_id": "pip-timeout", "source": "dsh-web"}, (
        "the body is the lesson id plus the constant surface label, and nothing else: " + str(post["body"]))


def test_the_click_says_what_it_changed_in_the_words_the_project_uses():
    """The receipt is the server's count, and it is the sentence section ③ already states."""
    receipt = _render()["receipt"]
    assert "external reuse evidence: 2 human confirmations" in receipt, (
        "the count from `/api/helpful` must land in the trust row, not only in the click's own line: "
        + receipt[receipt.find("external reuse evidence"):][:120])
    assert "2 human confirmations" in receipt and "E4" in receipt, (
        "the confirmation repeats the rule in the project's vocabulary (one is the reuse event, the "
        "second is what agents read as E4)")
    assert "→ E4" in receipt, "a row past the threshold carries the marker the acceptance list pins"
    assert "not voted" not in receipt, (
        "the row must stop offering a vote it already has: one sighting, one vote")
    assert "1 lesson reused · 1 vote ·" in receipt, (
        "the click must also move the panel's own counters, in both scopes: " + receipt[receipt.find("Your activity"):][:200])


def test_a_miss_offers_a_copyable_line_and_files_nothing():
    """Change #3, rendered: the distinct miss row, the clipboard line, and no POST from that row."""
    result = _render()
    assert result["missRow"] == "labelled", "a recorded no_match must be visually distinct (B1)"
    assert "misakanet_submit_intake" in result["copied"], (
        "the copyable line names the tool the agent has to call: " + result["copied"])
    assert '"pip install timeout behind proxy"' in result["copied"], (
        "the line carries the query that missed, so the agent can submit the same text")
    assert result["votePosts"] == 1, (
        "the copy affordance must post nothing — the only POST in this render is the vote, found "
        + str(result["votePosts"]))


def test_the_render_harness_can_go_red(tmp_path):
    """A gate nobody has seen fail: remove the affordances and the same run must report them missing."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("node renders the client half")
    source = CLIENT.read_text(encoding="utf-8")
    stripped = source.replace('controls.push(h("button", {\n\t\t\t\t\t\t\tkey: "v", type: "button", style: BUTTON, title: T("panel.asked.voteHint"),\n\t\t\t\t\t\t\tonClick: function () { voteFromPanel(entry); },\n\t\t\t\t\t\t}, T("tool.helpful")));', "")
    assert stripped != source, "the vote affordance is no longer where this fixture expects it"
    path = tmp_path / "client.js"
    path.write_text(stripped, encoding="utf-8")
    done = subprocess.run([node, str(HARNESS), str(path)], capture_output=True, text=True, timeout=120)
    assert done.returncode != 0, "the harness must fail when the affordance is gone"
    assert "one-click vote" in done.stderr, done.stderr[-400:]
