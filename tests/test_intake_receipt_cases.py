#!/usr/bin/env python3
"""Case harness for the intake → lesson receipt loop (#1528).

#1528's own acceptance rule, written by the maintainer on 2026-09-12, is:

    「验收要可判定：贴出"跑什么命令、看什么输出"的端到端演示（提交 intake → 合入 → 回执送达来源线程），
      而不是"文件多/CI 绿"」

The cases in `tests/intake_receipt_cases/` are that demo, and they are **real conversions from this
repository's history** — not invented fixtures. Each one records an intake, who reported it, and the
receipt it must produce. Run them with:

    pytest tests/test_intake_receipt_cases.py -v
    python3 scripts/intake_receipt.py --list-cases
    python3 scripts/intake_receipt.py --intake 1472

Why cases rather than unit tests of the helpers: the thing that has actually been failing is not the
string formatting, it is the *loop* — a lesson merges and the intake stays open saying nothing. Four
intakes were in exactly that state on 2026-09-21 (#1472/#1473/#1635/#1574, lessons merged days
earlier, no receipt), which is the defect this issue exists to kill. A case asserts the outcome a
reporter would see, including the two that must **not** produce a receipt.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from scripts.intake_receipt import (  # noqa: E402
    CASES_DIR,
    compose,
    lessons_citing,
    load_cases,
    main,
    render,
)

CASES = load_cases()
POSITIVE = [c for c in CASES if c["expected"]["emitted"]]
NEGATIVE = [c for c in CASES if not c["expected"]["emitted"]]


def test_the_harness_has_cases_at_all():
    """A harness with no cases passes silently — which is the failure mode it exists to prevent."""
    assert len(CASES) >= 5, f"expected the real conversions as cases, found {len(CASES)}"
    assert POSITIVE and NEGATIVE, "the suite must cover both 'receipt sent' and 'nothing to send'"


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_case_produces_the_receipt_it_records(case):
    receipt = compose(case["intake"], case["source"])
    expected = case["expected"]

    assert receipt["emitted"] is expected["emitted"], (
        f"{case['id']}: {case.get('why', '')}\n"
        f"got emitted={receipt['emitted']} reason={receipt.get('reason', '')}"
    )
    if not expected["emitted"]:
        assert expected["reason_contains"] in receipt["reason"]
        assert receipt["lessons"] == []
        return

    assert [l["path"] for l in receipt["lessons"]] == expected["lessons"], (
        f"{case['id']}: the receipt must name exactly the lessons that answer this intake"
    )
    assert receipt["evidence_level"] == expected["evidence_level"], (
        "AC3: the source is meant to see the quality outcome, so the level is part of the payload"
    )
    assert receipt["channels"] == expected["channels"]


def test_positive_cases_are_still_grounded_in_the_corpus():
    """Guard against fixture rot: if a lesson is renamed, fail loudly instead of passing quietly."""
    for case in POSITIVE:
        for path in case["expected"]["lessons"]:
            assert (REPO / path).is_file(), (
                f"{case['id']} expects {path}, which no longer exists — update the case or the lesson"
            )


def test_the_receipt_is_usable_by_the_reporter_without_cloning_anything():
    """AC2: it has to point at the lesson *and* let the reporter verify it themselves."""
    receipt = compose(1472, "antigravity")
    text = render(receipt)
    lesson = receipt["lessons"][0]

    assert lesson["path"] in text, "the lesson must be named by path"
    assert lesson["id"] in text, "and by id, so it can be fetched with misakanet_get_lesson"
    assert receipt["evidence_level"] in text, "AC3: the quality outcome belongs in the prose too"
    assert lesson["url"].startswith("https://github.com/Ikalus1988/MisakaNet/blob/main/")
    assert "```bash" in text and "search_knowledge.py" in text, (
        "a receipt the reporter cannot act on is a receipt they will not trust"
    )


def test_the_anonymous_channel_carries_the_answer_a_resubmission_needs():
    """#1605's story: an anonymous MCP reporter has no thread, so the receipt must travel on MCP.

    The channel they already use is re-submitting the same problem text — which today already
    returns the maintainer's answer for questions. This is the same shape for conversions.
    """
    payload = compose(1472, "antigravity")["mcp"]
    assert payload["resolved"] is True
    assert payload["issue"] == "#1472"
    assert payload["lesson"] == "vertex-gemini-model-id-naming"
    assert payload["evidence_level"] == "E3"
    assert payload["lesson_path"] in render(compose(1472, "antigravity"))


def test_a_number_mentioned_in_the_body_is_not_a_citation(tmp_path):
    """No false positives: a lesson that merely *mentions* an issue has not converted it.

    Without this rule the composer would happily claim any number that appears anywhere in the
    corpus, and every receipt would be a guess.
    """
    lesson = tmp_path / "mentions-only.md"
    lesson.write_text(
        "---\ntitle: something else\ndomain: devops\nstatus: published\nevidence_level: E1\n"
        "source: \"somewhere\"\n---\n\nRelated: this resembles #4242 and #9999.\n",
        encoding="utf-8",
    )
    assert lessons_citing(4242, tmp_path) == []
    assert lessons_citing(9999, tmp_path) == []


def test_a_lesson_merged_minutes_ago_is_found(tmp_path):
    """Read the lesson files, not the generated snapshot.

    `data/lessons.json` is regenerated by a daily job, so it lags a merge by up to a day. Trusting it
    is precisely how four intakes ended up with merged lessons and no receipt on 2026-09-21.
    """
    lesson = tmp_path / "just-merged.md"
    lesson.write_text(
        "---\ntitle: just merged\ndomain: devops\nstatus: published\nevidence_level: E2\n"
        "source: \"intake-7777\"\nprovenance:\n  issue: \"#7777\"\n---\n\n## Problem\n\nx\n",
        encoding="utf-8",
    )
    found = lessons_citing(7777, tmp_path)
    assert [l["path"] for l in found] == ["just-merged.md"]
    assert found[0]["evidence_level"] == "E2"


def test_nothing_to_receipt_is_not_a_success(capsys):
    """Exit 2, not 0: a caller that treats 'nothing found' as success posts an empty receipt."""
    assert main(["--intake", "4242"]) == 2
    out = capsys.readouterr().out
    assert "不发送回执" in out and "no lesson cites" in out


def test_render_never_names_a_lesson_that_does_not_exist():
    text = render(compose(4242, "unknown"))
    assert "lessons/" not in text, "a refusal must not leak a plausible-looking path"


def test_the_cli_lists_the_cases_with_their_verdicts(capsys):
    assert main(["--list-cases"]) == 0
    out = capsys.readouterr().out
    for case in CASES:
        assert case["id"] in out


def test_every_case_file_is_well_formed():
    for path in sorted(CASES_DIR.glob("*.json")):
        case = json.loads(path.read_text(encoding="utf-8"))
        assert set(case) >= {"id", "why", "intake", "source", "expected"}, path.name
        assert isinstance(case["intake"], int) and case["intake"] > 0
        assert case["why"].strip(), f"{path.name}: a case without a reason is a fixture, not evidence"
