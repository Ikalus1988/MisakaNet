#!/usr/bin/env python3
"""The public-surface rule: a lesson may not teach a command name the corpus has never seen.

Why a gate and not a guideline
------------------------------
`lesson_gate` is the only thing between a submission and a permanently public lesson. The intake side
already carries an advisory banner (`unknownCommandSurface` in the worker), but an advisory banner
cannot stop anything: #3983 was published with its employer's private CLI in the thread, and the same
text in a lesson would have been published with it *and* indexed.

The false-positive rate is the reason this file exists at all. Measured while building the rule, with
the extractor reading every fenced block and every inline span as a command: **182 of 651 lessons
(28%)** were flagged, overwhelmingly for writing *code* — `case1`, `normalizerow`, `conftest.py`,
`e1`, `e3`. A gate that red-lights a quarter of the corpus is a gate people route around, so the
extraction now demands evidence (shell fence, or arguments, or a flag), and the tests below pin that
in both directions: the shapes that must fire, and the shapes that must stay quiet.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import lesson_gate  # noqa: E402

VOCAB = {"pytest", "npm", "docker", "git", "node", "pip", "curl", "cat", "lessons"}


def test_a_repeated_private_command_is_caught():
    """The #3983 shape: no backticks anywhere, a name repeated in command position with a flag."""
    text = ("mico login 无效。\n"
            "mico issue rerun 会把错误原文打出来。\n"
            "mico im message history 看最后一条回复。\n"
            "mico wiki search --json 正常。\n")
    assert "mico" in lesson_gate.unknown_surface_names(text, VOCAB)


def test_a_quoted_command_with_arguments_is_caught():
    assert lesson_gate.unknown_surface_names("run `zetaqx deploy --prod` first", VOCAB) == ["zetaqx"]


def test_a_known_tool_is_not_flagged():
    assert lesson_gate.unknown_surface_names("`pytest -q tests/` then `npm run build`", VOCAB) == []


def test_code_in_a_javascript_fence_is_not_a_command():
    """The 182-lesson false positive: a fence with no shell dialect is code, not a command."""
    text = "```js\ncase1(service, 'fail');\nnormalizerow(sqlite_constraint_unique);\n```\n"
    assert lesson_gate.unknown_surface_names(text, VOCAB) == []


def test_a_shell_fence_is_a_command():
    assert lesson_gate.unknown_surface_names("```bash\nzetaqx deploy\n```", VOCAB) == ["zetaqx"]


def test_a_single_inline_identifier_is_not_a_command():
    """`e1` in prose is a label; a command has arguments. This is the line that keeps prose quiet."""
    assert lesson_gate.unknown_surface_names("见 `e1` 与 `current_dt` 两处", VOCAB) == []


def test_a_dollar_prompt_is_a_command():
    assert lesson_gate.unknown_surface_names("$ zetaqx status", VOCAB) == ["zetaqx"]


def test_the_corpus_prefix_is_tolerated():
    """`node.js` is known because `node` is; the token splits on the dot exactly as the worker does."""
    assert lesson_gate.unknown_surface_names("`node.js --version`", VOCAB) == []


def test_public_analogue_is_an_accepted_answer():
    fm = {"title": "t", "public_analogue": "an agent whose liveness signals stay green after revocation"}
    assert lesson_gate.validate_public_surface(fm, "```bash\nmico issue rerun\n```", REPO) == []


def test_an_unknown_name_fails_the_lesson():
    problems = lesson_gate.validate_public_surface({}, "```bash\nzetaqx deploy\n```", REPO)
    assert len(problems) == 1
    assert "zetaqx" in problems[0]
    assert "public_analogue" in problems[0], "the failure has to name an accepted answer"


def test_a_missing_vocabulary_is_a_warning_not_a_pass(tmp_path, monkeypatch):
    """No vocabulary means no judgement. Silence would render as 'clean' — the failure mode this
    whole gate is about — so it must say so."""
    monkeypatch.setattr(lesson_gate, "load_public_vocabulary", lambda *a, **k: None)
    problems = lesson_gate.validate_public_surface({}, "```bash\nzetaqx deploy\n```", tmp_path)
    assert problems and problems[0].startswith("[warn]")
    assert "cannot check" in problems[0]


RENDERED = """---
title: "A checked-in skill can exist without being available to the client"
summary_plain: "A checked-in skill can exist without being available to the client."
trigger: "A checked-in skill can exist without being available to the client."
verify: "The client lists the skill."
---

## Problem

A checked-in skill can exist without being available to the client.

## Root Cause

The loader reads one directory.

## Fix

Reload it.

## Verification

The client lists the skill.
"""


def _gate(text: str, vocab=VOCAB) -> list[str]:
    """What the gate actually decides: prose for repetition, the whole document for code evidence."""
    fm, _ = lesson_gate.parse_frontmatter(text)
    return lesson_gate.validate_public_surface(fm, text, REPO)


def test_the_derived_fields_are_not_repetition():
    """One sentence copied into `title`/`summary_plain`/`trigger` is not three mentions.

    The bare-mention path exists so a name written in prose three times counts as evidence of a
    command. Counting the whole rendered file made the *converter's* copying look like the author's
    repetition: measured 2026-11-23, **18 of the 29** intake candidates the gate refused were refused
    only by this path — `checked-in`, `task-list`, `exhaust`, `arrival`, `vacancy` — each of which
    appears once in the prose and three times in the file.
    """
    assert _gate(RENDERED) == [], "prose, not a command name"
    # The raw counter still sees the body's own repetition; what changed is that the derived fields
    # are no longer counted. `checked-in` appears exactly once there.
    body = lesson_gate._lesson_body(RENDERED)
    assert body.count("checked-in") == 1


def test_real_repetition_in_the_prose_still_counts():
    """The other direction: the rule this replaced was not decoration.

    #3983 published an employer's private CLI written in plain prose. Three *different* sentences is
    still the evidence that a bare mention is a command, and reading the body does not touch it.
    """
    text = "mico login is refused.\nmico issue rerun prints the error.\nmico wiki search is empty.\n"
    assert lesson_gate.unknown_surface_names(text, VOCAB) == ["mico"]
    assert any("`mico`" in problem for problem in _gate(text))


def test_a_name_with_code_evidence_survives_the_derivation():
    """A private name does not become prose because it is also in the title.

    Code evidence (span, fence, prompt) is read from the whole document, frontmatter included — only
    the bare-mention *count* moved to the author's prose.
    """
    lesson = RENDERED.replace(
        "## Fix\n\nReload it.",
        "## Fix\n\n```bash\nrequires_openai_auth --set\n```", 1)
    assert lesson != RENDERED, "fixture did not change"
    assert "requires_openai_auth" in lesson_gate.unknown_surface_names(
        lesson, VOCAB, prose_source=lesson_gate._lesson_body(lesson))
    assert any("requires_openai_auth" in problem for problem in _gate(lesson))
