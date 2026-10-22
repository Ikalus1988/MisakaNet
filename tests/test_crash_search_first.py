# SPDX-License-Identifier: MIT
"""崩溃后先查课程，无命中才留草稿（issue #3642）。

这条链子有三段，各自有各的失败方式，所以三条分支都要能离线测出来：

* **命中** → 打印课程标题 + 链接，当场可用；**不留草稿**（已经有课程了，别再造一门）。
* **未命中** → 明确说"没有现成课程，已留草稿"，草稿落在 `lessons/drafts/`。
* **无网络** → 跳过检索，行为与检索之前一致（还是留草稿）。

检索用的是 `scripts/intake_bot.py` 里那一个已经校准好的命中判定，不是第二把尺子。
所以这里没有网络：`search` 是注入进来的（`lookup_crash` 的接缝），语料也不需要。
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from misakanet.crash_lookup import CORPUS_TIMEOUT_S, lookup_crash, strip_stack_frames
from scripts import fatal_guard_handler

REPO = Path(__file__).parent.parent

# fatal-guard 的 Node 包装器写的载荷：错误正文在 `message`，崩溃现场在 `stackSnippet`（#3645）。
NODE_PAYLOAD = {
    "schemaVersion": 1,
    "reason": "uncaught_exception",
    "timestamp": "2026-10-21T12:00:05.000Z",
    "pid": 4243,
    "errorName": "Error",
    "message": "EACCES: permission denied, open '/etc/shadow'",
    "stackSnippet": "Error: EACCES: permission denied, open '/etc/shadow'\n    at app.js:1:20",
    "exit_code": 1,
}

# 一门已经存在的课程（形状与 intake_bot 的命中输出一致）。
KNOWN_LESSON = {
    "id": "permission-denied-fix",
    "title": "Permission Denied / WSL NTFS 跨文件系统PermissionFix",
    "url": "https://misakanet.org/lessons/permission-denied-fix/",
    "sim": 0.67,
    "sim_norm": 0.335,
    "sim_scale": 2.0,
}


def _search_returning(lesson):
    """一个注入的检索函数：记录被问到的文本，返回固定的课程（或 None）。"""
    asked = []

    def search(error_text):
        asked.append(error_text)
        return lesson

    search.asked = asked
    return search


# ── 命中 ──────────────────────────────────────────────────────────────

def test_a_hit_prints_the_lesson_title_and_link(tmp_path, capsys):
    """命中时给的是当场能用的东西：标题 + 链接。"""
    search = _search_returning(KNOWN_LESSON)

    code = fatal_guard_handler.main(
        [json.dumps(NODE_PAYLOAD)], search=search, drafts_dir=tmp_path)

    out = capsys.readouterr().out
    assert code == 0
    assert KNOWN_LESSON["title"] in out, "the lesson title is not in the output"
    assert KNOWN_LESSON["url"] in out, "the lesson link is not in the output"


def test_a_hit_leaves_no_draft(tmp_path):
    """已经有课程了就不留草稿——否则同一件事会有两门课。"""
    search = _search_returning(KNOWN_LESSON)

    fatal_guard_handler.main([json.dumps(NODE_PAYLOAD)], search=search, drafts_dir=tmp_path)

    assert list(tmp_path.iterdir()) == [], "a hit must not leave a draft behind"


def test_the_search_is_asked_with_the_crash_error_text(tmp_path):
    """检索用的就是崩溃自己的错误文本（去掉堆栈帧），不是墓碑的元信息。"""
    search = _search_returning(KNOWN_LESSON)

    fatal_guard_handler.main([json.dumps(NODE_PAYLOAD)], search=search, drafts_dir=tmp_path)

    assert search.asked, "the search was never asked"
    asked = search.asked[0]
    assert "EACCES: permission denied" in asked
    # 堆栈帧是证据、但不是失败本身：留着它会把命中判定要找的主体词挤掉。
    assert "at app.js" not in asked


# ── 未命中 ────────────────────────────────────────────────────────────

def test_no_hit_says_there_is_no_lesson_and_leaves_a_draft(tmp_path, capsys):
    """没命中：说清楚"没有现成课程，已留草稿"，并且草稿真的在那儿。"""
    search = _search_returning(None)

    code = fatal_guard_handler.main(
        [json.dumps(NODE_PAYLOAD)], search=search, drafts_dir=tmp_path)

    out = capsys.readouterr().out
    assert code == 0
    assert "没有现成课程" in out
    assert "已留草稿" in out

    drafts = list(tmp_path.glob("*.md"))
    assert len(drafts) == 1, "the draft was not left behind"
    body = drafts[0].read_text(encoding="utf-8")
    assert "EACCES: permission denied" in body, "the draft lost the error text"
    for section in ("## Problem", "## Root Cause", "## Solution", "## Verification"):
        assert section in body


def test_the_draft_carries_the_fields_the_lesson_gate_asks_for(tmp_path):
    """草稿要能被读：规范 domain、evidence_level、status。"""
    search = _search_returning(None)

    fatal_guard_handler.main([json.dumps(NODE_PAYLOAD)], search=search, drafts_dir=tmp_path)

    draft = next(tmp_path.glob("*.md"))
    frontmatter = json.loads(draft.read_text(encoding="utf-8").split("---")[1])
    assert frontmatter["evidence_level"] == "E0"
    assert frontmatter["status"] == "draft"
    assert frontmatter["source"] == "fatal-guard"


# ── 无网络 ────────────────────────────────────────────────────────────

def test_without_a_network_the_search_is_skipped_and_the_draft_is_still_left(tmp_path, capsys):
    """无网络：跳过检索，行为与检索之前一致——还是留草稿。

    但它**不能说**"没有现成课程"：根本没查，就不能说没有。
    """
    search = _search_returning(KNOWN_LESSON)  # 命中也不该被问到

    code = fatal_guard_handler.main(
        ["--offline", json.dumps(NODE_PAYLOAD)], search=search, drafts_dir=tmp_path)

    out = capsys.readouterr().out
    assert code == 0
    assert search.asked == [], "the search ran even though the run was offline"
    assert "检索未完成" in out, "the skipped search was not reported"
    assert "没有现成课程" not in out, "the crash path claimed there is no lesson without looking"
    assert "已留草稿" in out
    assert len(list(tmp_path.glob("*.md"))) == 1, "the draft was not left behind"


def test_a_failed_search_is_skipped_instead_of_fatal(tmp_path, capsys):
    """检索失败可以跳过（issue 的原话），但不能静默：要说出来。"""
    def exploding_search(error_text):
        raise OSError("network is unreachable")

    code = fatal_guard_handler.main(
        [json.dumps(NODE_PAYLOAD)], search=exploding_search, drafts_dir=tmp_path)

    out = capsys.readouterr().out
    assert code == 0
    assert "检索未完成" in out
    assert "network is unreachable" in out, "the failed search was not reported"
    assert "没有现成课程" not in out, "a failed search was reported as 'no lesson exists'"
    assert len(list(tmp_path.glob("*.md"))) == 1, "the draft was not left behind"


# ── 载荷的三个来路 ────────────────────────────────────────────────────

def test_the_payload_is_read_from_the_last_argv_entry(tmp_path):
    search = _search_returning(KNOWN_LESSON)

    fatal_guard_handler.main([json.dumps(NODE_PAYLOAD)], search=search, drafts_dir=tmp_path)

    assert search.asked, "the argv channel was not read"


def test_the_payload_is_read_from_the_fatal_payload_variable(tmp_path, monkeypatch):
    """Windows 路径把载荷放在环境变量里，argv 里没有。"""
    monkeypatch.setenv("FATAL_PAYLOAD", json.dumps(NODE_PAYLOAD))
    search = _search_returning(KNOWN_LESSON)

    fatal_guard_handler.main([], search=search, drafts_dir=tmp_path)

    assert search.asked, "the FATAL_PAYLOAD channel was not read"


def test_the_payload_is_read_from_the_fatal_payload_file(tmp_path, monkeypatch):
    """Windows 路径还会把载荷写成文件。"""
    payload_file = tmp_path / "payload.json"
    payload_file.write_text(json.dumps(NODE_PAYLOAD), encoding="utf-8")
    monkeypatch.setenv("FATAL_PAYLOAD_FILE", str(payload_file))
    search = _search_returning(KNOWN_LESSON)

    fatal_guard_handler.main([], search=search, drafts_dir=tmp_path)

    assert search.asked, "the FATAL_PAYLOAD_FILE channel was not read"


def test_a_missing_payload_is_an_explicit_error(capsys):
    """读不到载荷就明说，别装作处理过了。"""
    code = fatal_guard_handler.main([])

    assert code == 2
    assert "no crash payload" in capsys.readouterr().err


# ── 复用的是那把已经校准好的尺子 ──────────────────────────────────────

def test_the_default_search_reuses_the_calibrated_hit_decision(monkeypatch):
    """默认检索走的是 intake_bot 的命中判定，且**从不**提交 intake。"""
    from scripts import intake_bot

    seen = {}

    def fake_decide(error, **kwargs):
        seen.update(kwargs)
        seen["error"] = error
        return {"decision": "hit", "lesson": KNOWN_LESSON}

    monkeypatch.setattr(intake_bot, "decide", fake_decide)

    lookup = lookup_crash("EACCES: permission denied")

    assert lookup.hit, "the hit decision was not used"
    assert seen["error"] == "EACCES: permission denied"
    assert seen["auto_intake"] is False, "a crash handler must never submit an intake"
    assert seen["sim_threshold"] == intake_bot.DEFAULT_HIT_SIM, (
        "the crash path must use the calibrated bar, not a number of its own")
    assert seen["source"] == "fatal-guard"


def test_a_local_similarity_measure_is_not_used(monkeypatch):
    """命中判定只有一把尺子：检索 API 的 BM25 score 是另一个量，混用会得到噪音命中。"""
    from scripts import intake_bot

    def fake_decide(error, **kwargs):
        return {"decision": "hit", "lesson": KNOWN_LESSON}

    monkeypatch.setattr(intake_bot, "decide", fake_decide)
    monkeypatch.setattr(
        intake_bot, "precheck",
        lambda *a, **k: pytest.fail("the crash path must not score the corpus itself"))

    lookup = lookup_crash("EACCES: permission denied")

    assert lookup.hit


def test_an_unreachable_corpus_is_reported_as_a_skipped_search(monkeypatch):
    """语料拉不到 = 检索没跑成，不是"没有现成课程"。

    没有网络时最容易犯的错就是把两者混成一句话，让人以为已经查过了。
    """
    from scripts import intake_bot

    monkeypatch.setattr(intake_bot, "_load_corpus", lambda timeout=60: [])

    lookup = lookup_crash("EACCES: permission denied")

    assert lookup.hit is False
    assert lookup.searched is False, "a search that could not run is not a search that found nothing"
    assert lookup.skipped_reason and "corpus" in lookup.skipped_reason


def test_the_corpus_fetch_is_bounded_by_the_handler_budget(monkeypatch):
    """fatal-guard 5 秒后杀掉 handler，所以拉语料必须有更短的预算。"""
    from scripts import intake_bot

    seen = {}

    def fake_load_corpus(timeout=60):
        seen["timeout"] = timeout
        return []

    monkeypatch.setattr(intake_bot, "_load_corpus", fake_load_corpus)

    lookup_crash("EACCES: permission denied")

    assert seen["timeout"] == CORPUS_TIMEOUT_S
    assert seen["timeout"] < 5, "the corpus fetch must fit inside fatal-guard's 5s handler budget"


# ── 检索文本：同一段错误，去掉堆栈帧 ──────────────────────────────────

@pytest.mark.parametrize("crash", [
    "Error: EACCES: permission denied, open '/etc/shadow'\n    at openSync (node:fs:498:26)",
    "Traceback (most recent call last):\n  File \"/app/main.py\", line 12, in <module>\n"
    "    data = open('/etc/shadow')\nPermissionError: [Errno 13] Permission denied: '/etc/shadow'",
])
def test_the_stack_frames_are_dropped_from_the_search_text(crash):
    """帧里是函数名和文件名，不是失败本身——留着会把主体词挤掉。"""
    text = strip_stack_frames(crash)

    assert "at openSync" not in text
    assert 'File "/app/main.py"' not in text
    assert "Traceback (most recent call last):" not in text
    # 失败本身必须还在
    assert "permission denied" in text.lower()
