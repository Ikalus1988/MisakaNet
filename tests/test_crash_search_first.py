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
import re
import subprocess
import sys
from pathlib import Path

import pytest

from misakanet import guard
from misakanet.crash_lookup import (
    CORPUS_TIMEOUT_S,
    format_hit,
    lookup_crash,
    search_lessons,
    strip_stack_frames,
)
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


def test_a_hit_without_a_title_or_a_link_still_says_something_usable():
    """命中也给得出能看的东西：没有标题就说没有标题，没有链接就按 id 拼一个。"""
    line = format_hit({"id": "abc-123"})

    assert "(untitled lesson)" in line
    assert "https://misakanet.org/lessons/abc-123/" in line


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


def test_a_payload_that_is_not_an_object_is_an_explicit_error(capsys):
    """载荷必须是一个对象。不是对象就明说，不要崩在半路。"""
    code = fatal_guard_handler.main([json.dumps(["not", "an", "object"])])

    assert code == 2
    assert "no crash payload" in capsys.readouterr().err


@pytest.mark.parametrize("crash", [
    # Python 3.11 的脱字符行：   ~^^^^^^^^^^^^
    "  File \"/app/main.py\", line 12, in <module>\n"
    "    data = open('/etc/shadow')\n"
    "    ~~~~~~~~^^^^^^\n"
    "PermissionError: [Errno 13] Permission denied: '/etc/shadow'",
    # Python 3.13 的帧条 + 脱字符：   |   ^^^^^^
    "  File \"/app/main.py\", line 12, in <module>\n"
    "    |   data = open('/etc/shadow')\n"
    "    |   ^^^^^^^^^^^^^^^^^^^^^\n"
    "PermissionError: [Errno 13] Permission denied: '/etc/shadow'",
    # 链式异常的两句
    "During handling of the above exception, another exception occurred:\n"
    "\n"
    "The above exception was the direct cause of the following exception:\n"
    "\n"
    "Traceback (most recent call last):\n"
    "  File \"/app/main.py\", line 20, in <module>\n"
    "    run()\n"
    "RuntimeError: boom",
])
def test_the_python_markers_are_dropped_from_the_search_text(crash):
    """定位条、脱字符、链式异常的头——它们都是帧，不是失败本身。"""
    text = strip_stack_frames(crash)

    assert "~" not in text, "the 3.11 caret line survived"
    assert "^" not in text, "the caret line survived"
    assert "During handling of the above exception" not in text
    assert "The above exception was the direct cause" not in text
    # 失败本身必须还在
    assert "PermissionError" in text or "RuntimeError" in text


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
    assert lookup.searched is True, "a hit means the search ran"
    assert seen["error"] == "EACCES: permission denied"
    assert seen["auto_intake"] is False, "a crash handler must never submit an intake"
    assert seen["offline"] is False, (
        "the crash path must let the hit decision look at the corpus")
    assert seen["sim_threshold"] == intake_bot.DEFAULT_HIT_SIM, (
        "the crash path must use the calibrated bar, not a number of its own")
    assert seen["source"] == "fatal-guard"


def test_a_miss_decision_means_the_search_ran_and_found_nothing(monkeypatch):
    """"查了没有"和"没查成"必须能分开。

    intake_bot 说 miss 的时候，检索是**跑成了**的——那比"没查成"要好，
    但那也不是"命中"。混成一句话，人就不知道该去查还是该等着。
    """
    from scripts import intake_bot

    def fake_decide(error, **kwargs):
        return {"decision": "miss", "lesson": None}

    monkeypatch.setattr(intake_bot, "decide", fake_decide)

    assert search_lessons("a crash nobody has written about", corpus=[{"id": "x"}]) is None

    lookup = lookup_crash("a crash nobody has written about", search=lambda text: None)
    assert lookup.hit is False
    assert lookup.searched is True, "a search that ran and found nothing is not a skipped search"
    assert lookup.skipped_reason is None, "a search that ran must not be reported as skipped"


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


def _fatal_guard_handler_budget_ms() -> int:
    """fatal-guard 杀 handler 的时限——从它的源码里读，不在这里抄一份数字。"""
    source = (REPO / "packages" / "fatal-guard" / "src" / "lib" / "spawn-command.js").read_text(
        encoding="utf-8")
    match = re.search(r"HANDLER_TIMEOUT_MS\s*=\s*(\d+)", source)
    assert match, "fatal-guard no longer declares HANDLER_TIMEOUT_MS"
    return int(match.group(1))


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
    assert CORPUS_TIMEOUT_S == 3, (
        "the corpus budget is a measured number (cold fetch of 516 lessons: 0.96s) — "
        "re-measure before changing it")
    assert seen["timeout"] < _fatal_guard_handler_budget_ms() / 1000, (
        "the corpus fetch must fit inside fatal-guard's handler budget")


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


# ── Python 边车（misakanet.guard）───────────────────────────────────

def _crashing_command() -> list[str]:
    return [sys.executable, "-c",
            "import sys; sys.stderr.write('Error: EACCES: permission denied\\n'); sys.exit(3)"]


def test_the_sidecar_runs_the_command_after_the_separator(tmp_path):
    """`--` 之前 argparse.REMAINDER 会把它一起收进来，不摘掉就执行一个叫 "--" 的程序。"""
    with pytest.raises(SystemExit) as exc:
        guard.main(["--offline", "--", * _crashing_command()])

    assert exc.value.code == 3, "the child's exit code is not passed through"


def test_the_sidecar_keeps_its_exit_code_and_its_tombstone(tmp_path, capfd):
    """退出码与墓碑字段是现有 CLI 语义，不能被这次改动动到。"""
    with pytest.raises(SystemExit) as exc:
        guard.main(["--offline", "--", *_crashing_command()])

    assert exc.value.code == 3
    tombstone = json.loads(capfd.readouterr().out)
    for field in ("pid", "timestamp", "reason", "exit_code", "signal", "snippet", "host", "node_id"):
        assert field in tombstone, f"the tombstone lost the field {field}"
    assert tombstone["exit_code"] == 3


def test_the_sidecar_prints_the_lesson_on_a_hit(tmp_path, capfd):
    """边车也走同一条路：命中 → 标题 + 链接。"""
    search = _search_returning(KNOWN_LESSON)

    with pytest.raises(SystemExit):
        guard.main(["--", *_crashing_command()], search=search)

    err = capfd.readouterr().err
    assert KNOWN_LESSON["title"] in err
    assert KNOWN_LESSON["url"] in err


def test_the_sidecar_leaves_a_draft_when_nothing_answers(tmp_path, capfd):
    """边车的 --to-draft 今天是不工作的（--create-bounty 不是合法参数），现在它工作。"""
    search = _search_returning(None)

    with pytest.raises(SystemExit):
        guard.main(["--to-draft", "--drafts-dir", str(tmp_path), "--", *_crashing_command()],
                   search=search)

    err = capfd.readouterr().err
    assert "没有现成课程" in err
    assert "已留草稿" in err
    drafts = list(tmp_path.glob("*.md"))
    assert len(drafts) == 1, "the sidecar did not leave a draft"
    assert "EACCES: permission denied" in drafts[0].read_text(encoding="utf-8")


def test_the_sidecar_does_not_claim_a_draft_it_did_not_write(tmp_path, capfd):
    """没写成就别说写了——旧实现无条件打印"draft lesson 已生成"。"""
    search = _search_returning(None)
    # 一个写不下去的目录：它是普通文件下面的子路径，mkdir 必然失败。
    blocker = tmp_path / "a-file"
    blocker.write_text("not a directory", encoding="utf-8")

    with pytest.raises(SystemExit):
        guard.main(["--to-draft", "--drafts-dir", str(blocker / "drafts"),
                    "--", *_crashing_command()], search=search)

    err = capfd.readouterr().err
    assert "已留草稿" not in err, "the sidecar claimed a draft it could not write"
    assert "未留草稿" in err, "the sidecar did not say that there is no draft"
    assert "生成失败" in err, "the failure was not reported"


def test_the_sidecar_searches_without_the_stack_frames(tmp_path, capfd):
    """边车拿到的现场可能带帧（子进程打印的 traceback）；检索时那些帧要去掉。"""
    search = _search_returning(KNOWN_LESSON)
    traceback_cmd = [sys.executable, "-c",
                     "import sys; sys.stderr.write('Traceback (most recent call last):\\n"
                     "  File \"x.py\", line 1\\nPermissionError: [Errno 13]\\n'); sys.exit(3)"]

    with pytest.raises(SystemExit):
        guard.main(["--", *traceback_cmd], search=search)

    assert search.asked, "the sidecar never searched"
    assert 'File "x.py"' not in search.asked[0], "the stack frames reached the search"
    assert "PermissionError" in search.asked[0], "the failure itself must stay"


def test_the_sidecar_writes_no_draft_when_it_was_not_asked_to(tmp_path, capfd):
    """没有 --to-draft 就不写草稿，也不能说写了。

    旧实现只认 `--to-draft` 这个开关；现在检索成了默认动作，别把"检索"和"写草稿"
    混成一件事——没要草稿就不该有草稿。
    """
    with pytest.raises(SystemExit):
        guard.main(["--offline", "--drafts-dir", str(tmp_path), "--", *_crashing_command()])

    err = capfd.readouterr().err
    assert "已留草稿" not in err, "the sidecar claimed a draft it was not asked to write"
    assert "未留草稿" in err
    assert list(tmp_path.glob("*.md")) == [], "a draft was written without --to-draft"


def test_the_sidecar_without_a_command_prints_help_and_exits(capfd):
    """没有命令就没有东西可包装：说清楚，而不是把空列表丢给 Popen。"""
    with pytest.raises(SystemExit) as exc:
        guard.main([])

    assert exc.value.code == 1
    assert "usage" in capfd.readouterr().err.lower()


# ── 作为进程跑（fatal-guard 真正会做的事）────────────────────────────

def test_the_handler_runs_as_a_process(tmp_path):
    """FATAL_HANDLER 就是一个进程：载荷在 argv 最后一项，输出在 stdout。"""
    env = {k: v for k, v in os.environ.items() if k != "MISAKANET_OLLAMA_URL"}
    result = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "fatal_guard_handler.py"),
         "--offline", "--drafts-dir", str(tmp_path), json.dumps(NODE_PAYLOAD)],
        capture_output=True, text=True, env=env, cwd=str(REPO), timeout=60)

    assert result.returncode == 0, result.stderr
    assert "检索未完成" in result.stdout
    assert "已留草稿" in result.stdout
    assert len(list(tmp_path.glob("*.md"))) == 1


# ── 结论文件：Node 路径上那一行没人看得见，所以要落到文件里 ────────────────────────────


def test_the_resolution_is_written_next_to_the_crash_file(tmp_path, monkeypatch):
    """fatal-guard 把 handler 的 stdout 丢掉了（`stdio: 'ignore'`）。

    所以"命中时输出课程标题 + 链接"在 Node 路径上必须还有一个落盘的地方：崩溃文件旁边。
    `FATAL_CRASH_OUT` 是 fatal-guard 自己那个环境变量，handler 是它的子进程，拿得到同一个值。
    """
    crash_file = tmp_path / "last-crash.json"
    monkeypatch.setenv("FATAL_CRASH_OUT", str(crash_file))
    search = _search_returning(KNOWN_LESSON)

    code = fatal_guard_handler.main(
        [json.dumps(NODE_PAYLOAD)], search=search, drafts_dir=tmp_path / "drafts")

    assert code == 0
    resolution = tmp_path / "last-crash.json.resolution.md"
    assert resolution.exists(), "the resolution was not written next to the crash file"
    text = resolution.read_text(encoding="utf-8")
    assert KNOWN_LESSON["title"] in text, "the lesson title is not in the resolution"
    assert KNOWN_LESSON["url"] in text, "the lesson link is not in the resolution"


def test_the_resolution_says_where_the_draft_is(tmp_path, monkeypatch):
    """未命中时结论里要写清楚"没有现成课程"和草稿在哪——那一行在 Node 路径上也是看不见的。"""
    crash_file = tmp_path / "last-crash.json"
    monkeypatch.setenv("FATAL_CRASH_OUT", str(crash_file))
    drafts = tmp_path / "drafts"

    fatal_guard_handler.main(
        [json.dumps(NODE_PAYLOAD)], search=_search_returning(None), drafts_dir=drafts)

    text = (tmp_path / "last-crash.json.resolution.md").read_text(encoding="utf-8")
    assert "没有现成课程" in text, "the resolution does not say that there is no lesson"
    assert "draft" in text, f"the resolution does not point at the draft: {text}"


def test_no_resolution_is_written_without_a_crash_file(tmp_path, monkeypatch):
    """没有崩溃文件就没什么"旁边"，也就不该凭空造一个文件。

    `chdir` 到 tmp_path：一份"写在当前目录"的实现也跑不掉——它会落在 tmp_path 里。
    """
    monkeypatch.delenv("FATAL_CRASH_OUT", raising=False)
    monkeypatch.chdir(tmp_path)

    code = fatal_guard_handler.main(
        [json.dumps(NODE_PAYLOAD)], search=_search_returning(KNOWN_LESSON),
        drafts_dir=tmp_path / "drafts")

    assert code == 0
    assert list(tmp_path.iterdir()) == [], "a resolution appeared without a crash file"


def test_an_empty_crash_file_setting_writes_no_resolution(tmp_path, monkeypatch):
    """`FATAL_CRASH_OUT=''` 是 fatal-guard 那边"关掉崩溃文件"的说法，这时也不该写结论。"""
    monkeypatch.setenv("FATAL_CRASH_OUT", "")

    fatal_guard_handler.main(
        [json.dumps(NODE_PAYLOAD)], search=_search_returning(KNOWN_LESSON),
        drafts_dir=tmp_path / "drafts")

    assert list(tmp_path.iterdir()) == [], "a resolution appeared although the crash file is off"


def test_the_resolution_next_to_a_markdown_crash_file_uses_the_stem(tmp_path, monkeypatch):
    """崩溃文件也可能是 .md；那时结论文件是 <stem>.resolution.md，不是 <name>.resolution.md。"""
    crash_file = tmp_path / "last-crash.md"
    monkeypatch.setenv("FATAL_CRASH_OUT", str(crash_file))
    search = _search_returning(KNOWN_LESSON)

    fatal_guard_handler.main(
        [json.dumps(NODE_PAYLOAD)], search=search, drafts_dir=tmp_path / "drafts")

    resolution = tmp_path / "last-crash.resolution.md"
    assert resolution.exists(), (
        f"the resolution was not written: {sorted(p.name for p in tmp_path.iterdir())}")
    assert KNOWN_LESSON["url"] in resolution.read_text(encoding="utf-8")


def test_a_resolution_that_cannot_be_written_does_not_break_the_crash_path(tmp_path, monkeypatch):
    """结论文件是额外的一份，不是流程的一环：写不下去也要照常处理崩溃。"""
    blocker = tmp_path / "a-file"
    blocker.write_text("not a directory", encoding="utf-8")
    monkeypatch.setenv("FATAL_CRASH_OUT", str(blocker / "crash.json"))
    search = _search_returning(KNOWN_LESSON)

    code = fatal_guard_handler.main(
        [json.dumps(NODE_PAYLOAD)], search=search, drafts_dir=tmp_path / "drafts")

    assert code == 0, "the crash path failed because the resolution could not be written"


def test_a_draft_that_cannot_be_written_is_reported_as_such(tmp_path, capsys):
    """草稿写不下去：明说，退出码也说清楚（3 = 草稿写不下去）。"""
    blocker = tmp_path / "a-file"
    blocker.write_text("not a directory", encoding="utf-8")

    code = fatal_guard_handler.main(
        ["--offline", "--drafts-dir", str(blocker / "drafts"), json.dumps(NODE_PAYLOAD)])

    assert code == 3
    assert "cannot write the draft" in capsys.readouterr().err
