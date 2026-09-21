#!/usr/bin/env python3
"""The reference client enforced a quota the service had already retired (#1986).

On 2026-09-21 the documented local path failed on its sixth run:

    $ python3 search_knowledge.py "GITHUB_TOKEN push does not trigger workflow"
    [MisakaNet] 搜索额度已用尽 (5/5)。
        贡献 1 条 lesson 即可恢复额度：
        python3 scripts/queue_lesson.py -t '标题' -d <domain> '...'

`misakanet/.quota.json` read `{"search_count": 5, "quota_max": 5}` — git-ignored, so every fresh
clone starts with five local searches. Two things were wrong with that:

* **It metered something with no cost.** Local search is BM25 over a corpus already on disk; nothing
  on the project's side is consumed. "Invite a contribution" had been built as a hard `sys.exit(1)`
  on the reference client — a behavioural nudge delivered as a functional failure.
* **It enforced a policy that no longer exists**, with a reason that is now false. Anonymous reads
  became unlimited on 2026-09-18 (only a per-address burst guard remains). Worse, `--remote` *skipped*
  the quota, so the local path the docs teach was strictly worse than the remote one, and the user was
  sent to `queue_lesson.py` to fix a problem that was not theirs.

These are the two halves that keep it retired: a behavioural test that the real command works with an
exhausted quota file, and a rule over the shipped source that the gate cannot come back.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
CLI = REPO / "search_knowledge.py"
PROFILE = REPO / "misakanet" / "profile.py"
QUOTA_FILE = REPO / "misakanet" / ".quota.json"
# `increment_search()` writes the node profile on every successful local search, and that file is
# tracked (it holds a referral code — see the issue this test opens). The behavioural test below runs
# the real command, so it must put both files back or it leaves the working tree dirty for whatever
# runs next.
PROFILE_STATE = REPO / "misakanet" / "profile.json"
LESSONS = REPO / "data" / "lessons.json"

# The retired machinery, by name. Any of these in executable code is the gate coming back.
RETIRED_NAMES = ("check_quota", "consume_quota", "reset_quota", "FREE_SEARCH_QUOTA", "_load_quota",
                 "_save_quota", "_QUOTA_PATH")
# And the sentences that made a local computation sound like an exhausted resource.
RETIRED_SENTENCES = ("额度已用尽", "即可恢复额度", "额度剩余", "搜索额度已重置")


def code_only(text: str) -> str:
    """The file's code, without comments or docstrings.

    `profile.py` still *quotes* the message it stopped printing ("搜索额度已重置（感谢贡献！）") in the
    comment explaining why it is gone — a rule that reads raw text is satisfied by the prose describing
    the bug, which is how this repository has tripped its own gates four times.
    """
    lines, in_doc = [], False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.count('"""') % 2 == 1:
            in_doc = not in_doc
            continue
        if in_doc or stripped.startswith("#"):
            continue
        lines.append(line.split("  #")[0] if "  #" in line else line)
    return "\n".join(lines)


def quota_gate_problems(cli_text: str, profile_text: str) -> list[str]:
    problems = []
    for name, text in (("search_knowledge.py", cli_text), ("misakanet/profile.py", profile_text)):
        code = code_only(text)
        for token in RETIRED_NAMES:
            if re.search(rf"\b{re.escape(token)}\b", code):
                problems.append(f"{name}: `{token}` is back in executable code")
        for sentence in RETIRED_SENTENCES:
            if sentence in code:
                problems.append(f"{name}: the retired message {sentence!r} is emitted again")
    return problems


def test_the_retired_quota_gate_is_gone_from_the_shipped_code():
    problems = quota_gate_problems(CLI.read_text(encoding="utf-8"), PROFILE.read_text(encoding="utf-8"))
    assert not problems, "; ".join(problems)


def test_reinstating_the_gate_is_caught():
    """Mutation: put the removed block back and the rule must notice."""
    old_block = """
    # ── 轻量配额检查 ──
    if not remote:
        from misakanet.profile import check_quota as _check_quota
        allowed, quota_msg = _check_quota()
        if not allowed:
            print("额度已用尽 (5/5)", file=sys.stderr)
            sys.exit(1)
"""
    problems = quota_gate_problems(
        CLI.read_text(encoding="utf-8") + old_block, PROFILE.read_text(encoding="utf-8"))
    assert any("check_quota" in p for p in problems), problems
    assert any("额度已用尽" in p for p in problems), problems


def test_the_explanation_of_the_removal_is_not_itself_flagged():
    """The prose that quotes the old message must not satisfy the rule (see `code_only`)."""
    assert quota_gate_problems(CLI.read_text(encoding="utf-8"),
                               PROFILE.read_text(encoding="utf-8")) == []
    assert "搜索额度已重置" in PROFILE.read_text(encoding="utf-8"), (
        "the comment explaining why the message is gone must stay in the file")


@pytest.mark.skipif(not LESSONS.exists(), reason="needs data/lessons.json (the local corpus)")
def test_the_documented_local_command_works_with_an_exhausted_quota_file():
    """End-to-end: the command a new user types, with the file that used to block it."""
    original = QUOTA_FILE.read_text(encoding="utf-8") if QUOTA_FILE.exists() else None
    profile_before = PROFILE_STATE.read_text(encoding="utf-8") if PROFILE_STATE.exists() else None
    QUOTA_FILE.write_text(json.dumps({"search_count": 999, "quota_max": 5}), encoding="utf-8")
    try:
        result = subprocess.run(
            [sys.executable, str(CLI), "context window exceeded", "--json"],
            cwd=REPO, capture_output=True, text=True, timeout=180)
        assert result.returncode == 0, (
            f"the local search must not be gated by a quota file:\n{result.stdout}\n{result.stderr}")
        hits = json.loads(result.stdout)
        assert hits, "and it must return the hits it would have returned before the file existed"
        assert "额度" not in result.stdout + result.stderr
    finally:
        if original is None:
            QUOTA_FILE.unlink(missing_ok=True)
        else:
            QUOTA_FILE.write_text(original, encoding="utf-8")
        if profile_before is not None:
            PROFILE_STATE.write_text(profile_before, encoding="utf-8")


def test_the_contribution_path_no_longer_claims_to_reset_a_quota():
    """Contributing a lesson still deserves thanks — the false sentence does not."""
    code = code_only(PROFILE.read_text(encoding="utf-8"))
    assert "reset_quota" not in code
    assert "感谢贡献" in code, "the thank-you should survive the removal of the claim it was attached to"
