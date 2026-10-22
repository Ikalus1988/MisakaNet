"""
misakanet.guard — Python 标准库跨语言进程崩溃 Sidecar。

纯标准库（Python 3.10+，无第三方包）。包装任何 CLI 进程，在崩溃时
自动捕获 4-field 墓碑 JSON，可选直连 tombstone_to_draft.py。

崩溃后先查 MisakaNet（#3642）：命中就把课程标题 + 链接打出来；没命中才
留草稿（并明确说"没有现成课程"）。无网络时（--offline）跳过检索，行为与
检索之前一致。

用法:
    # 基础包装
    python3 -m misakanet.guard -- your-command --with --flags

    # 崩溃后自动生成 draft lesson
    python3 -m misakanet.guard --to-draft -- your-command

    # 无网络：跳过课程检索
    python3 -m misakanet.guard --offline -- your-command

    # 指定输出墓碑路径
    python3 -m misakanet.guard --tombstone-out crash.json -- your-command

    # 设置 stderr 捕获行数
    python3 -m misakanet.guard --capture-lines 20 -- your-command

墓碑格式:
    {"pid": 12345, "timestamp": "2026-...", "reason": "exit code 1",
     "exit_code": 1, "snippet": "最后4行stderr[脱敏]", "signal": null,
     "host": "hostname", "node_id": "env:MISAKANET_NODE_ID"}
"""

import argparse
import json
import os
import platform
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from .crash_lookup import format_hit, format_no_hit, lookup_crash, strip_stack_frames

# ── 安全意识：检测到的 secret pattern 会从 snippet 中过滤 ──
_SECRET_PATTERNS = [
    # GitHub tokens (ghp_, gho_, github_pat_)
    r"(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{20,}",
    # npm tokens
    r"npm_[A-Za-z0-9_-]{20,}",
    # Generic API keys (sk-, pk-)
    r"(?:sk|pk|api[-_]?key)[-=][A-Za-z0-9_-]{20,}",
    # Bearer tokens
    r"Bearer\s+[A-Za-z0-9_\-\.]+",
    # Turnstile secrets
    r"0x4[A-Za-z0-9_-]{30,}",
    # OAuth refresh tokens
    r"1//[A-Za-z0-9_-]+",
    # Generic JWT-like tokens
    r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]+",
]
import re
_REDACT_RE = re.compile("|".join(_SECRET_PATTERNS), re.IGNORECASE)


def _redact(text: str) -> str:
    """对文本中检测到的 secret 进行脱敏处理。"""
    return _REDACT_RE.sub("[REDACTED]", text)


def _generate_tombstone(pid: int, exit_code: int, signal_num: int | None,
                        stderr_lines: list[str], start_time: float,
                        capture_lines: int) -> dict:
    """从崩溃进程元数据生成 4-field 墓碑协议 JSON。"""
    now = datetime.now(timezone.utc).isoformat()

    # 推断崩溃原因
    if signal_num is not None:
        reason = f"signal {signal_num} ({signal.Signals(signal_num).name})"
    elif exit_code == 0:
        reason = "normal exit"
    elif exit_code > 128:
        reason = f"signal {exit_code - 128} (exit code {exit_code})"
    else:
        reason = f"exit code {exit_code}"

    # 捕获最后 N 行 stderr（脱敏）
    raw_snippet = "".join(stderr_lines[-capture_lines:])
    snippet = _redact(raw_snippet)
    # 截断到 500 字符
    if len(snippet) > 500:
        snippet = snippet[-500:]

    elapsed = time.time() - start_time

    return {
        "pid": pid,
        "timestamp": now,
        "reason": reason,
        "exit_code": exit_code,
        "signal": signal_num,
        "snippet": snippet,
        "elapsed_s": round(elapsed, 3),
        "host": platform.node(),
        "node_id": os.environ.get("MISAKANET_NODE_ID", "unknown"),
    }


def _forward_signals(child_pid: int):
    """将 SIGTERM/SIGINT 转发给子进程。"""
    def handler(signum, frame):
        try:
            os.kill(child_pid, signum)
        except OSError:
            pass

    signal.signal(signal.SIGTERM, handler)
    signal.signal(signal.SIGINT, handler)


def _write_draft(tombstone: dict, drafts_dir: Path) -> Path:
    """把墓碑变成草稿文件，落在 `drafts_dir`。

    转换器（scripts/tombstone_to_draft.py）的行为是冻结的（#3645）：这里只调用，
    不改它。转换器不在 wheel 里（`packages.find` 只装 `misakanet*`），所以导入失败
    是可能的——失败由调用方显式报出来，不静默跳过。
    """
    from scripts.fatal_guard_handler import write_draft

    return write_draft(tombstone, drafts_dir)


def main(argv: list[str] | None = None, *, search=None):
    parser = argparse.ArgumentParser(
        description="misakanet.guard — 跨语言进程崩溃 Sidecar（纯标准库）",
        epilog="示例: python3 -m misakanet.guard --to-draft -- node app.js",
    )
    parser.add_argument("--to-draft", action="store_true",
                        help="崩溃后自动调用 tombstone_to_draft.py 生成 draft lesson")
    parser.add_argument("--tombstone-out", metavar="PATH",
                        help="墓碑 JSON 输出路径（默认 stdout）")
    parser.add_argument("--capture-lines", type=int, default=4,
                        help="捕获 stderr 最后 N 行（默认 4）")
    parser.add_argument("--drafts-dir", metavar="PATH",
                        help="草稿写到哪（默认 <本仓>/lessons/drafts）")
    parser.add_argument("--offline", action="store_true",
                        help="崩溃后跳过课程检索（无网络），行为与检索之前一致")
    parser.add_argument("cmd", nargs=argparse.REMAINDER, help="要包装的命令")
    args = parser.parse_args(argv)

    # argparse.REMAINDER 把 '--' 一起收进 cmd（它不是分隔符，是第一个元素）。
    # 不摘掉的话 Popen 会去执行一个叫 "--" 的程序，报"权限不足: --"、退出码 126。
    cmd = args.cmd[1:] if args.cmd and args.cmd[0] == "--" else args.cmd
    if not cmd:
        parser.print_help(file=sys.stderr)
        sys.exit(1)

    # 启动子进程
    start_time = time.time()
    stderr_lines: list[str] = []

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=sys.stdout,
            stderr=subprocess.PIPE,
            text=True,
            errors="replace",
        )
    except FileNotFoundError:
        print(f"misakanet.guard: 命令未找到: {cmd[0]}", file=sys.stderr)
        sys.exit(127)
    except PermissionError:
        print(f"misakanet.guard: 权限不足: {cmd[0]}", file=sys.stderr)
        sys.exit(126)

    # 转发信号
    _forward_signals(proc.pid)

    # 使用 communicate() 确保完整读取 stderr
    _, stderr_output = proc.communicate()
    exit_code = proc.returncode

    # 处理 stderr 行
    if stderr_output:
        for line in stderr_output.splitlines(keepends=True):
            stderr_lines.append(line)
            # 透传 stderr 到父进程（脱敏后输出）
            sys.stderr.write(_redact(line))
            sys.stderr.flush()
            if len(stderr_lines) > args.capture_lines + 100:
                stderr_lines.pop(0)

    # 生成墓碑
    signal_num = None
    if exit_code < 0:
        signal_num = -exit_code

    tombstone = _generate_tombstone(
        proc.pid, exit_code if exit_code >= 0 else 1,
        signal_num, stderr_lines, start_time, args.capture_lines
    )

    # 输出墓碑
    tombstone_json = json.dumps(tombstone, ensure_ascii=False, indent=2)

    if args.tombstone_out:
        Path(args.tombstone_out).write_text(tombstone_json + "\n", encoding="utf-8")
        print(f"\n[misakanet.guard] 墓碑已保存: {args.tombstone_out}", file=sys.stderr)
    else:
        print(tombstone_json)

    # 崩溃后先查 MisakaNet（#3642）：命中 → 把课程标题 + 链接打出来（当场可用）；
    # 没命中 → 才留草稿，并明确说"没有现成课程"。检索失败/无网络 → 跳过检索，
    # 行为与检索之前一致。
    if exit_code != 0:
        repo = Path(__file__).resolve().parent.parent
        drafts_dir = Path(args.drafts_dir) if args.drafts_dir else repo / "lessons" / "drafts"
        lookup = lookup_crash(strip_stack_frames(tombstone["snippet"]),
                               search=search, offline=args.offline)
        if lookup.hit:
            print(format_hit(lookup.lesson), file=sys.stderr)
        else:
            draft = None
            failure = None
            if args.to_draft:
                try:
                    draft = _write_draft(tombstone, drafts_dir)
                except (OSError, ImportError, ValueError) as exc:
                    failure = f"{type(exc).__name__}: {exc}"
            print(format_no_hit(draft, search_note=lookup.skipped_reason), file=sys.stderr)
            if failure:
                print(f"[misakanet.guard] draft lesson 生成失败: {failure}", file=sys.stderr)

    # 透传退出码
    sys.exit(exit_code if exit_code >= 0 else 1)


if __name__ == "__main__":
    main()
