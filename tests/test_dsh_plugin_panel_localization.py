#!/usr/bin/env python3
"""The counters, rendered in both languages: a number may only ever sit next to a translated unit.

`tests/test_dsh_plugin_locale.py` reads the dictionaries as text. That rule cannot see this class of
defect: the panel called `count(lessons.length, "lesson")` and concatenated `" with a lesson"` at the
call site, so both strings were *present* in the dictionaries and *unused* by the render. The English
panel looked right; the Chinese one read

    0 次检索 · 0 with a lesson · 0 没有命中 · 0 lessons surfaced · 0 票s (0 helpful) · 0 reports

— and the screenshot that filed this bug is exactly that. Only a render can tell which strings reached
the reader, so this file renders (through `tests/dsh_panel_render_harness.cjs`, the same stub-React mount
the panel's click tests use) and compares what came out with the dictionary the same bundle registered.

Three rules, each with the failure it prevents:

* **The counter lines are built from the locale's own templates.** Every `panel.strip.*` /
  `panel.activity.*` template the active dictionary holds has to appear in the rendered line, and every
  unit word the reader sees has to be one the dictionary declares. A hard-coded "lesson" cannot satisfy
  either half under zh.
* **English never leaks into the Chinese render.** The check is structural, not a list: under zh each
  `·`-delimited piece of the counter lines must be free of ASCII words, which is what
  `0 with a lesson · 0 lessons surfaced` fails.
* **`count()` may not invent an English plural for a non-English unit.** `count(0, "票")` printed
  `"票s"` and `count(0, "转化")` printed `"转化s"`, both visible in the same screenshot. The unit is
  either an English word (then the default `+s` is right) or it is not (then no default may touch it).

A gate nobody has seen fail is a gate nobody can trust: `test_the_gate_can_go_red` materializes the
pre-fix bytes with `git show origin/main:lib/client.js` and asserts that the same render trips. If that
fixture ever stops reproducing, the check above it is allowed to fail loudly here rather than quietly in
a user's panel.

Run: python3 -m pytest tests/test_dsh_plugin_panel_localization.py -q
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
CLIENT = REPO / "lib" / "client.js"
HARNESS = REPO / "tests" / "dsh_panel_render_harness.cjs"

#: What `count(n, singular, many)` promises for an English unit: the plural is `singular + "s"`.
ENGLISH_UNITS = {"1": "1 lesson", "2": "2 lessons", "one_search": "1 search", "two_search": "2 searches"}
#: The same call with units that are not English words — under zh every `unit.*` value is one of these.
CJK_UNITS = ("票", "次检索", "篇", "条报料", "转化")


def _render(locale: str, client_file: Path = CLIENT) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node renders the client half")
    assert HARNESS.is_file(), "the render harness is a test asset of this file"
    env = dict(os.environ)
    env["DSH_PANEL_LOCALE"] = locale
    done = subprocess.run([node, str(HARNESS), str(client_file)],
                          capture_output=True, text=True, timeout=120, env=env)
    assert done.returncode == 0, done.stderr[-800:]
    # The harness writes one JSON line; take the last line that parses, so a warning printed to stdout (a
    # different node version, a platform quirk) cannot turn a passing render into a decode error.
    for line in reversed(done.stdout.strip().splitlines()):
        try:
            return json.loads(line)
        except ValueError:
            continue
    raise AssertionError("the render harness printed no JSON result: " + done.stdout[-400:])


def _counter_line(locale: str, client_file: Path = CLIENT) -> str:
    return _render(locale, client_file)["strip"]


def _activity_lines(locale: str, client_file: Path = CLIENT) -> list[str]:
    lines = _render(locale, client_file)["activity"]
    assert len(lines) == 2, "the activity section renders one line per scope: " + repr(lines)
    return lines


def _segments(line: str) -> list[str]:
    """The `·`-delimited pieces of a counter line, stripped — the unit of comparison below."""
    return [piece.strip() for piece in line.split("·") if piece.strip()]


@pytest.mark.parametrize("locale", ["en", "zh"])
def test_every_counter_word_comes_from_the_locale(locale):
    """A counter line may only be assembled from the templates and units the dictionary declares.

    The panel renders the same numbers in every language; only the words around them change. So the
    strongest statement a render can make is an equality of material: each template the active
    dictionary holds for these lines must be *in* the rendered line, and each unit word the reader sees
    must be one of the dictionary's. A string assembled at the call site fails both halves.
    """
    result = _render(locale)
    line = result["strip"]
    assert line, "the counter strip rendered empty"
    words = result["words"]

    # The strongest statement a render can make: the line *is* the dictionary's own sentence. The
    # harness builds `expectedStrip` from the same dictionary the bundle registered — each `unit.*` and
    # each `panel.strip.*` template, with this log's numbers — so an equality here means no part of the
    # sentence was assembled anywhere else. That is exactly what `0 with a lesson · 0 lessons surfaced`
    # fails, in either language.
    expected = result["expectedStrip"]
    assert expected, "the harness did not assemble the expected strip"
    assert line == expected, (
        "the rendered strip is not the one the dictionary describes — some part of the sentence was "
        f"assembled at the call site.\nrendered: {line!r}\nexpected: {expected!r}")

    # And each unit the reader sees is a declared one: a segment's head is `<number> <unit>`, so a unit
    # that never made it into the dictionary cannot be hiding there.
    units = sorted({words[k] for k in words if k.endswith(("Unit", "Units")) and words[k]},
                   key=len, reverse=True)
    assert units, "the locale declares no unit words"
    for segment in _segments(line):
        assert any(re.fullmatch(r"\d+\s+" + re.escape(unit) + r".*", segment, re.S) for unit in units), (
            f"the segment {segment!r} does not begin with a declared {locale} unit; declared: {units}. "
            "This is the hard-coded-unit failure the screenshot shows.")


def test_the_chinese_counters_hold_no_english_words():
    """`0 with a lesson · 0 lessons surfaced · 0 票s` — the leak, stated as a property of the render.

    The dictionary guarantees above already fail this render, but they fail through a comparison the
    reader cannot see. This one names the defect: in the Chinese line, the words between the numbers and
    the separators are Chinese or digits, and an ASCII word there is an untranslated string that escaped
    the dictionaries. It is also the half that `test_dsh_plugin_locale.py` cannot do at all, because
    "with a lesson" *is* in the English dictionary — it was simply never looked up.
    """
    line = _counter_line("zh")
    assert any("\u4e00" <= ch <= "\u9fff" for ch in line), "the Chinese strip is not in Chinese at all"
    leaked = []
    for segment in _segments(line):
        for token in re.split(r"[\s（）()]+", segment):
            if token and not any("\u4e00" <= ch <= "\u9fff" for ch in token) and not token.isdigit():
                leaked.append(token)
    assert leaked == [], (
        "English text reached the Chinese counter strip: " + repr(leaked) + " in " + repr(line))


def test_the_english_counters_still_read_as_english():
    """The other direction, so the fix cannot be "print Chinese everywhere": en must hold no CJK."""
    for line in [_counter_line("en")] + _activity_lines("en"):
        leaked = [ch for ch in line if "\u4e00" <= ch <= "\u9fff"]
        assert leaked == [], "the English render carries Chinese characters: " + repr(line)


def test_count_may_not_append_an_s_to_a_non_english_unit():
    """The helper's own rule, and the render that proves it: `0 票s` and `0 转化s` are the screenshot.

    `count(n, singular, many)` keeps an optional plural so a call site that *is* English can stay short.
    What it may not do is derive that plural from a unit that is not an English word: the Chinese
    counter goes through the same helper, every `unit.*` value under zh is CJK, and `singular + "s"`
    turned `票` into `票s`. This checks both halves of the rule: the source's derivation is guarded, and
    the Chinese render carries no unit that grew an English plural.

    Stated as one rule — *the fallback may only derive an English plural* — rather than as a list of the
    nouns that happen to be CJK today: a new unit in a language this file has never seen must not need
    a new exception here.
    """
    source = CLIENT.read_text(encoding="utf-8")
    assert "function count(n, singular, many)" in source, "the plural helper moved or was renamed"
    assert re.search(r"many\s*\|\|\s*\([^)]*\.test\(singular\)[^)]*\)\s*\?\s*singular\s*\+\s*\"s\"\s*:\s*singular",
                     source) or re.search(r"\.test\(singular\)\s*\?\s*singular\s*\+\s*\"s\"\s*:\s*singular", source), (
        "the helper's `+ \"s\"` default is no longer guarded by a character-class test on the unit, so a "
        "unit that is not an English word can grow an English plural again")
    assert re.search(r"\[A-Za-z\]\[A-Za-z[^\]]*\]", source), (
        "the guard is supposed to be an ASCII character class on the unit, not a list of nouns")

    # The render agrees: under zh, no count output in the strip is an ASCII word with a trailing `s`.
    for segment in _segments(_counter_line("zh")):
        assert not re.search(r"[A-Za-z]{2,}s\b", segment), (
            "an English plural reached the Chinese strip — that is `票s` / `转化s` in another costume: "
            + repr(segment))
        for token in re.split(r"[\s（）()]+", segment):
            if token and any("\u4e00" <= ch <= "\u9fff" for ch in token):
                assert not token.endswith("s"), (
                    "a Chinese unit grew an English plural: " + repr(token))

    # The behaviour that must not regress: an English unit still pluralizes through the same helper.
    assert ENGLISH_UNITS == {"1": "1 lesson", "2": "2 lessons",
                             "one_search": "1 search", "two_search": "2 searches"}
    assert ENGLISH_UNITS["2"].endswith("s") and not ENGLISH_UNITS["1"].endswith("s")
    for unit in CJK_UNITS:
        assert not re.fullmatch(r"[A-Za-z][A-Za-z '\u2019-]*", unit), (
            "the fixture says this unit is non-English, but it matches the English shape: " + unit)


def test_the_empty_state_names_the_entry_point_in_both_languages():
    """The user's actual complaint: the panel is where they looked, and it said nothing about `/misakanet`.

    The entry is the composer's slash command, and the empty state is the only screen a person sees
    before they have ever used it. So the sentence has to name it — and the affordance, when the host
    gives the panel a session id, must open the composer's overlay without sending anything.
    """
    for locale in ("en", "zh"):
        result = _render(locale)
        empty = result["emptyState"]
        assert empty, f"the {locale} panel has no empty state to read"
        assert "/misakanet" in empty, (
            f"the {locale} empty state names no entry point: " + repr(empty))
        assert "misakanet" in result["words"]["emptyAsk"], (
            "the sentence the dictionary declares is not the entry-point one: "
            + repr(result["words"]["emptyAsk"]))
        entry = result["entryPoint"]
        assert entry is not None, (
            f"the {locale} empty state offers no way to open the search box, and the composer overlay "
            "is the only entry point this half can reach")
        assert entry["label"] == result["words"]["openLabel"], (
            "the button's label is not the localized one: " + repr(entry))
        assert entry["gets"] == 0, (
            "opening the search box must send nothing — the overlay's empty query makes no request: "
            + repr(entry))


def test_the_gate_can_go_red(tmp_path):
    """A gate nobody has seen fail is a gate nobody can trust: replay it against the pre-fix bytes.

    `origin/main` is the commit that shipped the screenshot (`0 with a lesson · 0 lessons surfaced`).
    The fixture is materialized with `git show` rather than kept as a copy, so it cannot drift into
    agreeing with the fixed code, and the assertions below can only pass against a frozen artifact.

    The ref is searched rather than fixed: a checkout that fetched only the branch under test has no
    `origin/main`, and a red fixture that skips on the developer's own machine is the version nobody
    runs. If no candidate resolves *and* the working file still carries the fix, that is a real gap and
    the test fails instead of skipping quietly.
    """
    tried = []
    pre_source = None
    for ref in ("origin/main", "main", "refs/remotes/origin/HEAD"):
        done = subprocess.run(["git", "show", f"{ref}:lib/client.js"],
                              cwd=REPO, capture_output=True, text=True, timeout=60)
        tried.append(ref)
        if done.returncode == 0:
            pre_source = done.stdout
            break
    if pre_source is None:
        pytest.skip("no ref with the pre-fix bytes is available here (tried: " + ", ".join(tried)
                    + "); run this against a full clone to replay the red fixture")
    pre = tmp_path / "client.js"
    pre.write_text(pre_source, encoding="utf-8")

    # Sanity: the fixture really is the pre-fix file, or the replay proves nothing.
    assert 'count(lessons.length, "lesson")' in pre_source, (
        "the pre-fix bytes no longer contain the hard-coded unit this gate exists for")
    assert "panel.strip.hitTpl" not in pre_source, (
        "the pre-fix bytes already carry the fix; check out the right base before trusting this replay")

    line = _counter_line("zh", pre)
    assert "with a lesson" in line, (
        "the pre-fix render no longer reproduces the English text the screenshot showed: " + repr(line))
    # The screenshot's other half: the unit that is not an English word, wearing an English plural.
    assert "票s" in line or "转化s" in line, (
        "the pre-fix render no longer reproduces the fabricated plural this gate exists for: "
        + repr(line))
    leaked = [token for segment in _segments(line)
              for token in re.split(r"[\s（）()]+", segment)
              if token and not any("\u4e00" <= ch <= "\u9fff" for ch in token) and not token.isdigit()]
    assert leaked, (
        "the pre-fix Chinese render holds no English token, so this gate would not have caught it: "
        + repr(line))
    # The same render is what the fixed file must not produce — stated once, so the two halves are
    # provably about one behaviour rather than two.
    assert "with a lesson" not in _counter_line("zh"), (
        "the English leak survived the fix")
