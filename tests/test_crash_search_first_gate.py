# SPDX-License-Identifier: MIT
"""草稿 → 课程：这条路径今天能不能走通（issue #3642）。

`lessons/drafts/README.md` 画的那条路（来源 A：崩溃 → 墓碑 → 草稿 → PR → 三种结果）
**一次都没有跑过**——隔离区里只有那份 README。所以这里把它跑一遍，离线跑：

  1. 崩溃 → 草稿（`scripts/fatal_guard_handler.py` 留下的那份）
  2. 门禁此刻拒绝它——它还不是课程，而且缺三样只有人能补的东西
  3. 人/agent 补上 Root Cause / Solution / Verification 与三个结构化字段
  4. 把它移进 `lessons/contrib/`
  5. `scripts/lesson_gate.py` 通过

第 2 步和第 5 步是这一对断言：中间那一步没做，门禁就该是红的。
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from scripts import fatal_guard_handler
from scripts.lesson_gate import parse_frontmatter, validate_file

REPO = Path(__file__).parent.parent

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

# 崩溃能给的：出了什么事。人/agent 要补的：为什么，怎么修，怎么确认。
HUMAN_ROOT_CAUSE = (
    "The process ran as a user that does not own `/etc/shadow`, so the read was denied "
    "by the kernel with EACCES before any application code could handle it."
)
HUMAN_SOLUTION = (
    "Run the workload as a user that owns the file (or grant the service account read "
    "access to the specific file), and open the file with the service's configured "
    "credential rather than the interactive user's."
)
HUMAN_VERIFICATION = (
    "Re-run the same command as the service user and confirm the read now succeeds:\n\n"
    "```bash\n"
    "node app.js; echo \"exit=$?\"\n"
    "```\n\n"
    "**Expected:** `exit=0` and the file content is read instead of an EACCES error."
)


def _make_repo(root: Path) -> Path:
    """一棵能当仓库使唤的树：课程目录 + 规范词表。"""
    repo = root / "repo"
    (repo / "lessons" / "contrib").mkdir(parents=True)
    (repo / "data").mkdir()
    shutil.copy(REPO / "data" / "domains.json", repo / "data" / "domains.json")
    return repo


def _crash_into(repo: Path) -> Path:
    """让 handler 走一遍崩溃路径，把草稿留在隔离区。"""
    fatal_guard_handler.main(
        ["--offline", json.dumps(NODE_PAYLOAD)], drafts_dir=repo / "lessons" / "drafts")
    drafts = list((repo / "lessons" / "drafts").glob("*.md"))
    assert len(drafts) == 1, "the handler did not leave exactly one draft"
    return drafts[0]


def _fill_in(draft: Path, target: Path) -> Path:
    """人/agent 补齐那三段正文 + 三个结构化字段，然后把文件移进 lessons/contrib/。"""
    frontmatter, content = parse_frontmatter(draft.read_text(encoding="utf-8"))
    frontmatter["summary_plain"] = (
        "The process was denied permission to read a file it has no rights to."
    )
    frontmatter["trigger"] = "EACCES: permission denied, open"
    frontmatter["verify"] = (
        "Re-run the command as the service user; it exits 0 and the file is read."
    )
    content = content.replace("<!-- TODO: Agent 需补全根本原因分析 -->", HUMAN_ROOT_CAUSE)
    content = content.replace("<!-- TODO: Agent 需提供修复方案 -->", HUMAN_SOLUTION)
    content = content.replace("<!-- TODO: Agent 需添加验证步骤 -->", HUMAN_VERIFICATION)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "---\n" + json.dumps(frontmatter, ensure_ascii=False, indent=2) + "\n---\n" + content,
        encoding="utf-8",
    )
    return target


def test_the_gate_rejects_the_draft_before_anybody_filled_it_in(tmp_path):
    """起点：草稿不是课程，门禁必须是红的，而且要说清缺什么。"""
    repo = _make_repo(tmp_path)
    draft = _crash_into(repo)

    errors = validate_file(draft, repo=repo)

    assert errors, "the gate accepted a raw crash draft"
    joined = "\n".join(errors)
    assert "lessons/drafts/ is not a lesson directory" in joined
    for field in ("summary_plain", "trigger", "verify"):
        assert f"missing structured field: {field}" in joined


def test_the_draft_becomes_a_lesson_after_a_human_fills_in_the_missing_parts(tmp_path):
    """终点：补上正文与结构化字段、移进 lessons/contrib/ 之后，门禁通过。"""
    repo = _make_repo(tmp_path)
    draft = _crash_into(repo)

    lesson = _fill_in(draft, repo / "lessons" / "contrib" / draft.name)
    errors = validate_file(lesson, repo=repo)

    assert errors == [], f"the filled-in draft still fails the gate: {errors}"


def test_the_filled_in_lesson_does_not_look_like_a_placeholder(tmp_path):
    """门禁放过它，是因为它真的写完了——不是留着 TODO 的空壳。"""
    repo = _make_repo(tmp_path)
    draft = _crash_into(repo)
    lesson = _fill_in(draft, repo / "lessons" / "contrib" / draft.name)

    body = lesson.read_text(encoding="utf-8")
    assert "TODO" not in body, "the lesson still carries a TODO placeholder"
    assert "EACCES" in body, "the lesson lost the error it is about"

    # 门禁对"假验证"只给 warning——所以这里自己看一眼，别拿一个空壳当课程。
    warnings = [e for e in validate_file(lesson, repo=repo) if e.startswith("[warn]")]
    assert not any("placeholder" in w for w in warnings), warnings


def test_the_draft_is_the_converter_s_own_output(tmp_path, monkeypatch):
    """草稿是冻结的转换器自己产出的那份，不是我另写的一份像它的东西。

    做法：把冻结的 `scripts/tombstone_to_draft.py` 复制到一棵临时树里，用它自己的
    CLI 跑一遍，再和 handler 留下的那份逐字节比（`created` 与 `tombstone_ref`
    是"什么时候、从哪来"，本来就该不同）。
    """
    monkeypatch.delenv("MISAKANET_OLLAMA_URL", raising=False)

    tree = tmp_path / "converter"
    (tree / "scripts").mkdir(parents=True)
    (tree / "data").mkdir()
    shutil.copy(REPO / "scripts" / "tombstone_to_draft.py", tree / "scripts")
    shutil.copy(REPO / "data" / "domains.json", tree / "data" / "domains.json")

    payload_file = tree / "payload.json"
    payload_file.write_text(json.dumps(NODE_PAYLOAD), encoding="utf-8")

    env = {k: v for k, v in os.environ.items() if k != "MISAKANET_OLLAMA_URL"}
    result = subprocess.run(
        [sys.executable, str(tree / "scripts" / "tombstone_to_draft.py"),
         "--from-file", str(payload_file), "--ai-hint"],
        capture_output=True, text=True, env=env, cwd=str(tree), timeout=60)
    assert result.returncode == 0, result.stderr

    converter_draft = next((tree / "lessons" / "drafts").glob("*.md"))
    handler_draft = _crash_into(_make_repo(tmp_path / "handler"))

    assert _normalised(converter_draft) == _normalised(handler_draft), (
        "the handler's draft is not the converter's draft")


def _normalised(path: Path) -> tuple[dict, str]:
    """草稿去掉两个"什么时候/从哪来"的字段之后的样子。"""
    frontmatter, content = parse_frontmatter(path.read_text(encoding="utf-8"))
    frontmatter.pop("created", None)
    frontmatter.pop("tombstone_ref", None)
    return frontmatter, content
