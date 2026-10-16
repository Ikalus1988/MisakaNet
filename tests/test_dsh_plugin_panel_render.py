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

The second half of the file does the same for section ⑥, the network's most-retrieved lessons
(`GET /api/analytics`). That section is a *read* of somebody else's ranking, so its four honesty rules —
what the number is, what an empty payload renders, where the list is capped, and what is deliberately
left out — are properties of the render and are checked here, each with a red proof against the pinned
pre-fix bytes (`PRE_FIX_SHA`) and, where the rule is behavioural, against a mutated copy that breaks
exactly that rule.

Run: python3 -m pytest tests/test_dsh_plugin_panel_render.py -q
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


def _render(client_file: Path = CLIENT, analytics: str = "full", locale: str = "en",
            coverage: str = "full") -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node renders the client half")
    assert HARNESS.is_file(), "the render harness is a test asset of this file"
    env = dict(os.environ)
    env["DSH_PANEL_LOCALE"] = locale
    # Which `/api/analytics` body the harness answers with: the live shape, an empty `top_lessons`, or a
    # body with no such key. Section ⑥'s empty-state rule needs both of the last two.
    env["DSH_PANEL_ANALYTICS"] = analytics
    # The same three choices for section ⑦'s `/api/insights/lesson-coverage` body.
    env["DSH_PANEL_COVERAGE"] = coverage
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
        "the confirmation repeats the rule in the project's vocabulary: a vote is a hint, and the E4 "
        "rung comes from observable reuse rather than the count")
    assert "→ E4" not in receipt, (
        "a vote count must not be marked as the rung — that mapping is what 2026-10-16 removed")
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


# ── section ⑥: the retrieval ranking, and the four ways it could lie ─────────
#
# The owner asked to see the corpus's hottest lessons without waiting for an agent to surface one, and the
# per-lesson half of that already exists: `GET /api/analytics` carries `top_lessons`, one
# `{lesson_id, count}` per lesson. A retrieval count is an observed fact and says nothing about whether the
# lesson helped, so the section has four rules about what it may claim. Each is checked on the render and
# replayed against the pinned pre-fix bytes — the `main` tip this change was cut from, which renders no
# such section at all — and the behavioural rules are additionally replayed against a mutated copy that
# breaks exactly that rule. A rule nobody has seen fail is a rule nobody can trust, and "the section is
# simply absent" proves less than "this copy, with this one thing wrong, is caught".

#: The pre-fix bytes, by commit and never by branch: `a9e0a4b9` is the `main` tip this change was cut from
#: and the parent of the commit that adds section ⑥. A branch would *become* the fixed bytes the moment
#: this lands, inverting the proof; a commit cannot move. (A gate on this repository went red on `main`
#: today for pinning to `origin/main` — this is the same lesson, applied here.)
PRE_FIX_SHA = "a9e0a4b90043178d470c43779871c8314387fbda"

#: What the rule sentence must say in each language: what the number counts, and what it is not. A
#: translation may phrase these differently; it may not drop one.
REQUIRED_RULE_PHRASES = {
    "en": ("retrieval", "not a vote", "not an approval", "not evidence"),
    "zh": ("检索", "次数", "不是投票", "不是认可", "不代表"),
}
#: Words that would dress the count as an opinion. Checked on the title, the cap line and the rows — never
#: on the rule, which has to *name* votes in order to disown them.
OPINION_WORDS = {"en": ("vote", "helpful", "approv", "upvote", "liked"),
                 "zh": ("投票", "有用", "认可", "赞同", "点赞")}


def _pre_fix_source(repo: Path = REPO) -> str:
    """The pre-fix `lib/client.js`, by commit SHA.

    Absent-and-unfetchable is a skip that says so; a SHA that exists and already carries the change is
    reported by the caller's sanity assertion as an expired red proof.
    """
    showed = subprocess.run(["git", "show", f"{PRE_FIX_SHA}:lib/client.js"],
                            cwd=repo, capture_output=True, text=True, timeout=60)
    if showed.returncode != 0:
        pytest.skip(
            "the pre-fix fixture did not run: this clone does not carry " + PRE_FIX_SHA[:12]
            + ". Run `git fetch origin " + PRE_FIX_SHA + "` (or use a full clone) to replay the red "
            "proof; the checks above it ran and are the reason this is a skip rather than a failure.")
    return showed.stdout


@pytest.fixture(scope="session")
def pre_fix_client(tmp_path_factory) -> Path:
    """The pinned pre-fix bundle on disk, once per session, so every red proof reads the same bytes."""
    source = _pre_fix_source()
    assert 'T("panel.hot")' not in source and "/api/analytics" not in source, (
        f"{PRE_FIX_SHA[:12]} already contains section ⑥ or its read, so it cannot replay its absence; "
        "pick the commit before the change and update PRE_FIX_SHA")
    path = tmp_path_factory.mktemp("pre-fix") / "client.js"
    path.write_text(source, encoding="utf-8")
    return path


def _mutation(tmp_path: Path, source: str, name: str, analytics: str = "full",
              locale: str = "en", coverage: str = "full") -> dict:
    """Render a deliberately broken copy. Callers assert the mutation took: this helper cannot tell a
    substitution that landed from one that quietly missed, and a missed one would prove nothing."""
    path = tmp_path / (name + ".js")
    path.write_text(source, encoding="utf-8")
    return _render(path, analytics=analytics, locale=locale, coverage=coverage)


def _label_problems(result: dict, locale: str) -> list[str]:
    """Rule 1: `N retrievals` is how often a search ranked the lesson first — not a vote, not approval."""
    problems: list[str] = []
    words = result["hotWords"]
    rule = words.get("rule")
    if not rule:
        return ["section ⑥ declares no rule sentence, so the number beside each lesson is unexplained"]
    if result["hotRule"] != rule:
        problems.append("the rendered rule is not the dictionary's own sentence: " + repr(result["hotRule"]))
    for phrase in REQUIRED_RULE_PHRASES[locale]:
        if phrase not in rule.lower():
            problems.append(f"the rule never says {phrase!r}: " + repr(rule))
    unit = words.get("retrievalUnits")
    if not unit:
        problems.append("no retrieval unit is declared, so a row's number has nothing to count")
    for row in result["hotRows"]:
        if not unit or not re.search(r"\d+\s+" + re.escape(unit), row):
            problems.append("a row prints a count without the retrieval unit: " + repr(row))
    opinion = " ".join([result["hotTitle"], result["hotLimit"]] + result["hotRows"]).lower()
    for banned in OPINION_WORDS[locale]:
        if banned in opinion:
            problems.append(f"section ⑥ says {banned!r}, which reads an observed count as an opinion: "
                            + repr(opinion))
    return problems


@pytest.mark.parametrize("locale", ["en", "zh"])
def test_section_6_labels_its_number_as_retrievals_not_as_an_opinion(locale, pre_fix_client, tmp_path):
    """The count must be readable as *retrievals* in both languages, and as nothing more."""
    result = _render(locale=locale)
    assert _label_problems(result, locale) == [], _label_problems(result, locale)
    assert result["hotRows"], "the fixture ranks six lessons, so the section must show some"

    # Red proof 1: the pinned pre-fix bytes render no section, so the rule cannot pass there.
    assert _label_problems(_render(pre_fix_client, locale=locale), locale) != [], (
        "the pre-fix bytes pass this rule, so it does not test the change")

    # Red proof 2: the rule stops disowning the vote, in that language.
    source = CLIENT.read_text(encoding="utf-8")
    replaced = {
        "en": ("It is an observed count, not a vote, not an approval, and not evidence that the lesson "
               "helped.", "It is a vote count."),
        "zh": ("它是一个观测到的计数：不是投票，不是认可，也不代表这篇课程真的帮上了忙。", "它就是投票数。"),
    }[locale]
    broken = source.replace(*replaced)
    assert broken != source, "the rule mutation did not take — update it with the copy"
    assert _label_problems(_mutation(tmp_path, broken, "vote-" + locale, locale=locale), locale) != []

    # Red proof 3: a row drops the unit and prints a bare number, which reads as nothing in particular.
    bare = source.replace('count(times, T("unit.retrieval"), T("unit.retrievals"))', "String(times)")
    assert bare != source, "the row mutation did not take — update it with the call site"
    assert _label_problems(_mutation(tmp_path, bare, "bare-" + locale, locale=locale), locale) != []


def _no_ranking_problems(result: dict) -> list[str]:
    """Rule 2: an absent or empty `top_lessons` is stated, never rendered as `0 retrievals`."""
    problems: list[str] = []
    none_sentence = result["hotWords"].get("none")
    if not none_sentence:
        return ["section ⑥ declares no 'no ranking' sentence, so an empty payload has nothing to say"]
    if result["hotEmpty"] != none_sentence:
        problems.append("an unranked payload does not render the dictionary's 'no ranking' sentence: "
                        + repr(result["hotEmpty"]))
    if result["hotRows"]:
        problems.append("an unranked payload still rendered rows: " + repr(result["hotRows"]))
    if result["hotRule"] or result["hotLimit"]:
        problems.append("an unranked payload still described a ranking: "
                        + repr(result["hotRule"] + " | " + result["hotLimit"]))
    return problems


@pytest.mark.parametrize("mode", ["empty", "absent"])
def test_section_6_never_manufactures_a_zero_when_the_payload_ranks_nothing(mode, pre_fix_client, tmp_path):
    """`top_lessons: []` and a body with no such key are the same fact: there is no ranking to print."""
    result = _render(analytics=mode)
    assert result["analyticsGets"] == 1, "the fixture answered, so the read happened exactly once"
    assert _no_ranking_problems(result) == [], _no_ranking_problems(result)

    assert _no_ranking_problems(_render(pre_fix_client, analytics=mode)) != [], (
        "the pre-fix bytes pass this rule, so it does not test the change")

    # Red proof 2: "asked and empty" collapsed into "an empty list", which loses the sentence and leaves a
    # cap line over nothing — the silent version of the same defect.
    source = CLIENT.read_text(encoding="utf-8")
    collapsed = source.replace("setHot(ranked && ranked.length ? ranked : null);", "setHot(ranked || []);")
    assert collapsed != source, "the empty-state mutation did not take — update it with the call site"
    assert _no_ranking_problems(_mutation(tmp_path, collapsed, "collapse-" + mode, analytics=mode)) != []


def _cap_problems(result: dict) -> list[str]:
    """Rule 3: five rows, the cap printed, and the rows are the payload's own order and pairing."""
    problems: list[str] = []
    cap = 5
    if len(result["hotRows"]) != cap:
        problems.append(f"the section shows {cap} rows; it rendered {len(result['hotRows'])}")
    if str(cap) not in result["hotLimit"]:
        problems.append("the cap line does not print the cap: " + repr(result["hotLimit"]))
    template = result["hotWords"].get("limit")
    if not template or "{n}" not in template:
        problems.append("the cap line is not a template, so the printed cap and the applied cap can drift")
    for row, entry in zip(result["hotRows"], result["hotFixture"][:cap]):
        if entry["lesson_id"] not in row or str(entry["count"]) not in row:
            problems.append(f"row {row!r} does not carry the payload's own {entry!r}")
    overflow = " ".join(result["hotRows"])
    for entry in result["hotFixture"][cap:]:
        if entry["lesson_id"] in overflow:
            problems.append("a lesson past the cap reached the reader: " + entry["lesson_id"])
    return problems


def test_section_6_caps_the_list_at_five_and_prints_the_cap(pre_fix_client, tmp_path):
    """The payload returns six; the owner asked for five; a silent truncation is indistinguishable from an
    exhausted ranking, so the limit is stated in the section."""
    result = _render()
    assert len(result["hotFixture"]) > 5, "the fixture must carry more than the cap, or this proves nothing"
    assert _cap_problems(result) == [], _cap_problems(result)

    assert _cap_problems(_render(pre_fix_client)) != [], (
        "the pre-fix bytes pass this rule, so it does not test the change")

    source = CLIENT.read_text(encoding="utf-8")
    # Red proof 2: the cap is dropped and every returned row reaches the reader.
    uncapped = source.replace(".slice(0, HOT_LESSON_LIMIT)", "")
    assert uncapped != source, "the cap mutation did not take — update it with the call site"
    assert _cap_problems(_mutation(tmp_path, uncapped, "uncapped")) != []
    # Red proof 3: the cap is applied but never printed.
    silent = source.replace('T("panel.hot.limit", { n: HOT_LESSON_LIMIT })', '""')
    assert silent != source, "the cap-copy mutation did not take — update it with the call site"
    assert _cap_problems(_mutation(tmp_path, silent, "silent-cap")) != []


def _query_list_problems(source: str, result: dict) -> list[str]:
    """Rule 4: `top_searches` is unfiltered and carries no lesson link, so it is not the questions."""
    problems: list[str] = []
    rendered = " ".join([result["hotTitle"], result["hotRule"], result["hotLimit"]] + result["hotRows"])
    for query in result["searchQueries"]:
        if query in rendered:
            problems.append(f"the unfiltered query {query!r} reached section ⑥ as if it were a topic")
    if "top_searches" not in source:
        problems.append("nothing in the bundle names `top_searches`, so leaving it out is an unrecorded "
                        "decision rather than a stated one")
    if "unfiltered" not in source:
        problems.append("the bundle never says the query list is unfiltered")
    if "no lesson link" not in source:
        problems.append("the bundle never records that a query cannot be paired with the lesson that "
                        "answered it")
    return problems


def test_section_6_leaves_the_unfiltered_query_list_out(pre_fix_client, tmp_path):
    """`npm run build`, `init` and `start` are not failure topics; the section must not dress them as any."""
    result = _render()
    assert result["searchQueries"], "the fixture must carry the payload's queries, or this proves nothing"
    assert _query_list_problems(CLIENT.read_text(encoding="utf-8"), result) == [], (
        _query_list_problems(CLIENT.read_text(encoding="utf-8"), result))

    assert _query_list_problems(_pre_fix_source(), _render(pre_fix_client)) != [], (
        "the pre-fix bytes pass this rule, so it does not test the change")

    source = CLIENT.read_text(encoding="utf-8")
    # Red proof 2: the reason goes unrecorded.
    unrecorded = source.replace("unfiltered query", "query")
    assert unrecorded != source, "the comment mutation did not take — update it with the comment"
    assert _query_list_problems(unrecorded, _mutation(tmp_path, unrecorded, "unrecorded")) != []
    # Red proof 3: a raw query reaches the copy, which is what "averaging the noise in" looks like.
    leaked = source.replace('"panel.hot.rule": "Each number', '"panel.hot.rule": "npm run build — each number')
    assert leaked != source, "the query-leak mutation did not take — update it with the dictionary"
    assert _query_list_problems(leaked, _mutation(tmp_path, leaked, "query-leak")) != []


def _schedule_problems(source: str, result: dict) -> list[str]:
    """The read is scheduled (not awaited on the render path) and asked exactly once."""
    problems: list[str] = []
    if result["analyticsGets"] != 1:
        problems.append(f"expected exactly one /api/analytics request; saw {result['analyticsGets']}: "
                        + repr(result["gets"]))
    if "askedHot.current" not in source:
        problems.append("the analytics read has no once-only ref guard, so a re-running effect re-asks")
    loading = result["hotWords"].get("loading")
    if not loading:
        problems.append("no loading sentence is declared for the section")
    elif loading not in result["firstPaint"]:
        problems.append("the first paint carries no loading sentence, so the read is on the render path")
    if result["hotRule"] and result["hotRule"] in result["firstPaint"]:
        problems.append("the ranking is already in the first paint, i.e. the render awaited it")
    leaked = [entry["lesson_id"] for entry in result["hotFixture"] if entry["lesson_id"] in result["firstPaint"]]
    if leaked:
        problems.append("a ranked lesson is in the first paint: " + repr(leaked))
    return problems


def test_section_6_is_scheduled_and_asked_once(pre_fix_client, tmp_path):
    """A fetch on the render path would block the first paint, and a public endpoint asked twice for one
    answer is a defect the panel already fixed once (the 8-calls-for-4-lessons round)."""
    result = _render()
    assert _schedule_problems(CLIENT.read_text(encoding="utf-8"), result) == [], (
        _schedule_problems(CLIENT.read_text(encoding="utf-8"), result))

    assert _schedule_problems(_pre_fix_source(), _render(pre_fix_client)) != [], (
        "the pre-fix bytes pass this rule, so it does not test the change")

    # Red proof 2: drop the guard *and* let the effect re-run on a vote — the exact pair the guard exists
    # for. Either one alone is safe, which is why the mutation is both.
    source = CLIENT.read_text(encoding="utf-8")
    unguarded = source.replace("if (askedHot.current) return;\n\t\t\t\taskedHot.current = true;\n", "")
    unguarded = unguarded.replace("setHot(null); });\n\t\t\t}, []);",
                                  "setHot(null); });\n\t\t\t}, [panelVotes]);")
    assert unguarded != source, "the guard mutation did not take — update it with the effect"
    assert "askedHot.current" not in unguarded
    broken = _mutation(tmp_path, unguarded, "unguarded")
    assert broken["analyticsGets"] > 1, (
        "the mutation was supposed to make the effect re-ask; it measured " + str(broken["analyticsGets"]))
    assert _schedule_problems(unguarded, broken) != []


def test_section_6_reads_each_dictionary_in_its_own_language(pre_fix_client):
    """Both languages, and neither falls back to the other: the render *is* the dictionary's own sentence."""
    en, zh = _render(locale="en"), _render(locale="zh")
    for result in (en, zh):
        assert result["hotWords"].get("rule"), "no section ⑥ rule for locale " + result["locale"]
        assert result["hotRule"] == result["hotWords"]["rule"], result["locale"]
        assert result["hotLimit"] == result["hotWords"]["limit"].replace("{n}", "5"), result["locale"]
    assert en["hotWords"]["rule"] != zh["hotWords"]["rule"], "the two locales share one rule sentence"
    assert not re.search(r"[A-Za-z]", zh["hotRule"] + zh["hotLimit"]), (
        "English leaked into the Chinese section: " + repr(zh["hotRule"] + zh["hotLimit"]))
    assert zh["hotWords"]["retrievalUnits"] != en["hotWords"]["retrievalUnits"], (
        "the retrieval unit is not localized, so the Chinese row counts in English")
    for row in zh["hotRows"]:
        assert zh["hotWords"]["retrievalUnits"] in row, "a Chinese row does not wear the Chinese unit"
    # Red proof: the pre-fix bytes declare no section ⑥ copy in either language.
    pre = _render(pre_fix_client, locale="zh")
    assert not pre["hotWords"].get("rule") and not pre["hotWords"].get("limit")


# ── section ⑦: the coverage board, and the four ways it could lie ────────────
#
# Section ⑥ ranks what searches *brought back*. This one ranks what they could **not** find: the coverage
# board's `gaps`, ordered by `unsolved30d` (unanswered searches in the last 30 days), each row carrying the
# number of published lessons that match the topic. It is the other half of the owner's question, and the
# panel now has two rankings — so it also has to say, where the reader meets them, that they are two
# different measurements rather than one sorted twice. Four rules, each replayed against the pinned pre-fix
# bytes *and* against a mutated copy that breaks exactly that rule.

#: The pre-fix bytes for **this** section, by commit and never by branch: the `main` tip this change was cut
#: from, which already carries section ⑥ and does not carry section ⑦. That isolation is the point — the red
#: proof below shows the *new* rules failing, not the whole panel missing. `origin/main` would become the
#: fixed bytes the moment this lands, which is how a fixture on this repository went red on `main`.
COVERAGE_PRE_FIX_SHA = "babf2edf4403f7261f0a352c83d8fc35b6a384bf"

#: What section ⑦'s rule must say in each language: which measurement it is, and how it differs from the
#: ranking above. A translation may phrase these differently; it may not drop one.
CONTRAST_PHRASES = {
    "en": ("brought back", "did not find", "unanswered"),
    "zh": ("带回来了什么", "没找到什么", "没有拿到答案"),
}


def _coverage_pre_fix_source(repo: Path = REPO) -> str:
    """The coverage section's pre-fix `lib/client.js`, by commit SHA (main's fixture, own commit)."""
    showed = subprocess.run(["git", "show", f"{COVERAGE_PRE_FIX_SHA}:lib/client.js"],
                            cwd=repo, capture_output=True, text=True, timeout=60)
    if showed.returncode != 0:
        pytest.skip(
            "the pre-fix fixture did not run: this clone does not carry " + COVERAGE_PRE_FIX_SHA[:12]
            + ". Run `git fetch origin " + COVERAGE_PRE_FIX_SHA + "` (or use a full clone) to replay the "
            "red proof; the checks above it ran and are the reason this is a skip rather than a failure.")
    return showed.stdout


@pytest.fixture(scope="session")
def coverage_pre_fix_client(tmp_path_factory) -> Path:
    """The pinned pre-fix bundle on disk, once per session."""
    source = _coverage_pre_fix_source()
    assert "COVERAGE_ENDPOINT" not in source and 'T("panel.coverage")' not in source, (
        f"{COVERAGE_PRE_FIX_SHA[:12]} already contains section ⑦ or its read, so it cannot replay its "
        "absence; pick the commit before the change and update COVERAGE_PRE_FIX_SHA")
    # And the isolation the docstring promises: this fixture is *after* section ⑥, so a red proof here can
    # only be about ⑦.
    assert 'T("panel.hot")' in source, (
        f"{COVERAGE_PRE_FIX_SHA[:12]} predates section ⑥ too, so a failure below would not isolate ⑦")
    path = tmp_path_factory.mktemp("coverage-pre-fix") / "client.js"
    path.write_text(source, encoding="utf-8")
    return path


def _coverage_ranking_problems(result: dict) -> list[str]:
    """Rule 1: five rows, in the payload's order, each paired with its own two numbers."""
    problems: list[str] = []
    rows, fixture = result["coverageRows"], result["coverageFixture"]
    if not rows:
        return ["section ⑦ rendered no ranking at all, so nothing below it is being tested"]
    if len(rows) != 5:
        problems.append(f"section ⑦ shows 5 rows; it rendered {len(rows)}")
    families = [row.split("  ")[0] for row in rows]
    if families != [entry["taskFamily"] for entry in fixture[:5]]:
        problems.append("the rows are not the payload's own order: " + repr(families))
    for row, entry in zip(rows, fixture[:5]):
        for value in (entry["taskFamily"], str(entry["lessonCount"]), str(entry["unsolved30d"])):
            if value not in row:
                problems.append(f"row {row!r} does not carry the payload's own {value!r} from {entry!r}")
    for entry in fixture[5:]:
        if entry["taskFamily"] in " ".join(rows):
            problems.append("a topic past the cap reached the reader: " + entry["taskFamily"])
    published = str(result["coveragePublished"])
    if published not in result["coverageTotals"]:
        problems.append("the totals line does not carry the payload's published count: "
                        + repr(result["coverageTotals"]))
    return problems


@pytest.mark.parametrize("locale", ["en", "zh"])
def test_section_7_renders_the_coverage_boards_own_ranking(locale, coverage_pre_fix_client, tmp_path):
    """The topics the corpus cannot answer, in the endpoint's order, with the corpus size behind each."""
    result = _render(locale=locale)
    assert result["coverageGets"] == 1, "the fixture answered, so the read happened exactly once"
    assert _coverage_ranking_problems(result) == [], _coverage_ranking_problems(result)

    # Red proof 1: the pinned pre-fix bytes render no such section (they carry ⑥, not ⑦).
    assert _coverage_ranking_problems(_render(coverage_pre_fix_client, locale=locale)) != [], (
        "the pre-fix bytes pass this rule, so it does not test the change")

    # Red proof 2: the rows are re-sorted by lesson count — the one order this ranking is *not*. It is the
    # mistake a reader is most likely to make by eye, because `lessonCount` looks like a size ranking.
    source = CLIENT.read_text(encoding="utf-8")
    resort = source.replace(
        "coverage.gaps.slice(0, COVERAGE_LIMIT)",
        "coverage.gaps.slice(0, COVERAGE_LIMIT).slice().sort(function (a, b) {"
        " return b.lessonCount - a.lessonCount; })")
    assert resort != source, "the resort mutation did not take — update it with the call site"
    assert _coverage_ranking_problems(
        _mutation(tmp_path, resort, "resort-" + locale, locale=locale)) != []
    # Red proof 3: every row wears the *first* topic's name — one family's label over another's numbers.
    # (Not a slot swap: the two templates read different slots — `{count}` under en, `{n} {unit}` under zh —
    # so a mutation that broke only one of them would pass in the other language and prove nothing.)
    unpaired = source.replace('h("span", {}, gap.taskFamily)',
                              'h("span", {}, coverage.gaps[0].taskFamily)')
    assert unpaired != source, "the pairing mutation did not take — update it with the call site"
    assert _coverage_ranking_problems(
        _mutation(tmp_path, unpaired, "unpaired-" + locale, locale=locale)) != []


def _coverage_contrast_problems(result: dict, locale: str) -> list[str]:
    """Rule 2: the rule says which measurement this is and how it differs from the ranking above."""
    problems: list[str] = []
    rule = result["coverageRule"]
    if not rule:
        return ["section ⑦ declares no rule sentence, so two rankings sit unexplained side by side"]
    if rule != result["coverageWords"].get("rule"):
        problems.append("the rendered rule is not the dictionary's own sentence: " + repr(rule))
    for phrase in CONTRAST_PHRASES[locale]:
        if phrase not in rule:
            problems.append(f"section ⑦'s rule never says {phrase!r}: " + repr(rule))
    if result["coverageTitle"] == result["hotTitle"]:
        problems.append("the two rankings wear the same title: " + repr(result["coverageTitle"]))
    if rule == result["hotWords"].get("rule"):
        problems.append("section ⑦ reused section ⑥'s rule sentence, so the difference is unstated")
    return problems


@pytest.mark.parametrize("locale", ["en", "zh"])
def test_section_7_says_how_it_differs_from_the_ranking_above(locale, coverage_pre_fix_client, tmp_path):
    """Two rankings in one panel must not read as one measured twice: the rule states the difference.

    `#3357`'s section ⑥ counts retrievals ("what searches brought back"); this counts unanswered searches
    ("what they did not find"). A reader who is not told that will assume the second is a re-sort of the
    first — the exact confusion two adjacent rankings invite, which is why this is a gate and not a note.
    """
    result = _render(locale=locale)
    assert _coverage_contrast_problems(result, locale) == [], _coverage_contrast_problems(result, locale)
    # The sections are keyed apart, not merely worded apart: a shared React key is the defect underneath.
    source = CLIENT.read_text(encoding="utf-8")
    for key in ('key: "s6"', 'key: "s7"', 'key: "s6r"', 'key: "s7r"'):
        assert key in source, f"the panel lost {key}, so the two sections are not keyed apart"

    # Red proof 1: the pinned pre-fix bytes carry ⑥ and not ⑦, so there is no rule to contrast with.
    assert _coverage_contrast_problems(_render(coverage_pre_fix_client, locale=locale), locale) != [], (
        "the pre-fix bytes pass this rule, so it does not test the change")
    # Red proof 2: the contrast sentence is dropped from the rule, which is what "one sorted twice" looks
    # like — the numbers stay right and the reader is left to guess what they are.
    dropped = source.replace(*{
        "en": ("The ranking above counts what searches brought back; this one counts what they did not find. ",
               ""),
        "zh": ("上面那一节数的是检索带回来了什么；这一节数的是没找到什么。", ""),
    }[locale])
    assert dropped != source, "the contrast mutation did not take — update it with the dictionary"
    assert _coverage_contrast_problems(
        _mutation(tmp_path, dropped, "flat-" + locale, locale=locale), locale) != []


@pytest.mark.parametrize("locale", ["en", "zh"])
def test_section_7_never_reads_as_an_opinion(locale, coverage_pre_fix_client):
    """`unsolved30d` is a count of searches, so no word of this section may dress it as approval."""
    result = _render(locale=locale)
    assert result["coverageRows"], "the fixture ranks six topics, so the section must show some"
    rendered = " ".join([result["coverageTitle"], result["coverageRule"], result["coverageTotals"]]
                        + result["coverageRows"]).lower()
    for banned in OPINION_WORDS[locale]:
        assert banned not in rendered, (
            f"section ⑦ says {banned!r}, which reads a count of unanswered searches as an opinion: "
            + repr(rendered))
    # Non-vacuous in the other direction too: the pre-fix bytes have no section, so the rule above cannot
    # pass by there being nothing to scan.
    assert not _render(coverage_pre_fix_client, locale=locale)["coverageRows"], (
        "the pre-fix bytes render rows, so the scan above proves nothing about this change")


def _coverage_no_ranking_problems(result: dict) -> list[str]:
    """Rule 3: an absent or empty `gaps` is stated, never a corpus total over rows of nothing."""
    problems: list[str] = []
    none_sentence = result["coverageWords"].get("none")
    if not none_sentence:
        return ["section ⑦ declares no 'no ranking' sentence, so an empty payload has nothing to say"]
    if result["coverageEmpty"] != none_sentence:
        problems.append("an unranked payload does not render the dictionary's 'no ranking' sentence: "
                        + repr(result["coverageEmpty"]))
    if result["coverageRows"]:
        problems.append("an unranked payload still rendered rows: " + repr(result["coverageRows"]))
    if result["coverageRule"] or result["coverageTotals"]:
        problems.append("an unranked payload still described a corpus: "
                        + repr(result["coverageRule"] + " | " + result["coverageTotals"]))
    return problems


@pytest.mark.parametrize("mode", ["empty", "absent"])
def test_section_7_never_describes_a_corpus_over_no_ranking(mode, coverage_pre_fix_client):
    """`gaps: []` and a body with no such key are the same fact: there is no ranking to stand a total on."""
    result = _render(coverage=mode)
    assert result["coverageGets"] == 1, "the fixture answered, so the read happened exactly once"
    assert _coverage_no_ranking_problems(result) == [], _coverage_no_ranking_problems(result)

    assert _coverage_no_ranking_problems(_render(coverage_pre_fix_client, coverage=mode)) != [], (
        "the pre-fix bytes pass this rule, so it does not test the change")


def test_the_no_ranking_rule_can_go_red(tmp_path):
    """The one mutation of this rule that a render can see: an empty ranking collapsed into a corpus.

    Only `empty` is mutated, and that is a statement about the code rather than a shortcut. With the key
    *gone* (`absent`), `setCoverage(body)` reaches `coverage.gaps.slice` and throws inside the promise
    handler, where the effect's own `.catch` lands on the very "no ranking" sentence this rule asks for:
    the defect is real but unobservable in a render, so a red proof built on it would prove nothing. The
    `empty` half is observable — the endpoint answered, `gaps` is `[]`, and the collapsed client prints a
    corpus total above rows that do not exist.
    """
    source = CLIENT.read_text(encoding="utf-8")
    collapsed = source.replace("setCoverage(ranked && ranked.length ? body : null);", "setCoverage(body);")
    assert collapsed != source, "the empty-state mutation did not take — update it with the call site"
    broken = _mutation(tmp_path, collapsed, "collapse-cov", coverage="empty")
    assert broken["coverageTotals"], (
        "the mutation was supposed to leave the totals line standing over no rows: "
        + repr(broken["coverageTotals"]))
    assert _coverage_no_ranking_problems(broken) != []


def _coverage_schedule_problems(source: str, result: dict) -> list[str]:
    """Rule 4: the read is scheduled (not awaited) and asked exactly once."""
    problems: list[str] = []
    if result["coverageGets"] != 1:
        problems.append(f"expected exactly one coverage request; saw {result['coverageGets']}: "
                        + repr(result["gets"]))
    if "askedCoverage.current" not in source:
        problems.append("the coverage read has no once-only ref guard, so a re-running effect re-asks")
    loading = result["coverageWords"].get("loading")
    if not loading:
        problems.append("no loading sentence is declared for section ⑦")
    elif loading not in result["firstPaint"]:
        problems.append("the first paint carries no loading sentence, so the read is on the render path")
    if result["coverageRule"] and result["coverageRule"] in result["firstPaint"]:
        problems.append("the ranking is already in the first paint, i.e. the render awaited it")
    leaked = [entry["taskFamily"] for entry in result["coverageFixture"]
              if entry["taskFamily"] in result["firstPaint"]]
    if leaked:
        problems.append("a ranked topic is in the first paint: " + repr(leaked))
    return problems


def test_section_7_is_scheduled_and_asked_once(coverage_pre_fix_client, tmp_path):
    """One public GET of the coverage board per panel, after the paint — never during it."""
    result = _render()
    assert _coverage_schedule_problems(CLIENT.read_text(encoding="utf-8"), result) == [], (
        _coverage_schedule_problems(CLIENT.read_text(encoding="utf-8"), result))

    assert _coverage_schedule_problems(_coverage_pre_fix_source(), _render(coverage_pre_fix_client)) != [], (
        "the pre-fix bytes pass this rule, so it does not test the change")

    # Red proof 2: drop the guard *and* let the effect re-run on a vote — the pair the guard exists for.
    source = CLIENT.read_text(encoding="utf-8")
    unguarded = source.replace("if (askedCoverage.current) return;\n\t\t\t\taskedCoverage.current = true;\n", "")
    unguarded = unguarded.replace("setCoverage(null); });\n\t\t\t}, []);",
                                  "setCoverage(null); });\n\t\t\t}, [panelVotes]);")
    assert unguarded != source, "the guard mutation did not take — update it with the effect"
    assert "askedCoverage.current" not in unguarded
    broken = _mutation(tmp_path, unguarded, "unguarded-coverage")
    assert broken["coverageGets"] > 1, (
        "the mutation was supposed to make the effect re-ask; it measured " + str(broken["coverageGets"]))
    assert _coverage_schedule_problems(unguarded, broken) != []
