#!/usr/bin/env python3
"""FATAL_HANDLER 入口：崩溃后先查 MisakaNet，查不到才留草稿（issue #3642）。

fatal-guard 把崩溃载荷交给 `FATAL_HANDLER`（#3645）：载荷里带的是**真的错误文本**，
所以这个 handler 可以先问一句 MisakaNet 有没有现成课程，再决定要不要写东西。

    FATAL_HANDLER="python3 /path/to/MisakaNet/scripts/fatal_guard_handler.py" \
        npx @misaka-net/fatal-guard -- node app.js

载荷有三个来路，三个都读（fatal-guard 的 POSIX 路径把载荷放在 argv 最后一项，
Windows 路径放在 `FATAL_PAYLOAD`，并把文件路径放在 `FATAL_PAYLOAD_FILE`）：

  * argv 最后一项        —— packages/fatal-guard/index.js 与 bin/fatal-guard.js
  * `FATAL_PAYLOAD`      —— 同上（Windows）
  * `FATAL_PAYLOAD_FILE` —— 同上（Windows，值是文件路径）

行为：

  * 命中   → 打印课程标题 + 链接，**不**写草稿（已有课程就别再造一门重复的）
  * 未命中 → 写草稿，并明确说"没有现成课程，已留草稿"
  * 无网络 → 跳过检索（`--offline`），行为与本 issue 之前一致

退出码：0 = 处理完（命中，或草稿已留）；2 = 载荷读不到；3 = 草稿写不下去。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Mapping, Sequence

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from misakanet.crash_lookup import (  # noqa: E402
    SearchFn,
    format_hit,
    format_no_hit,
    lookup_crash,
    strip_stack_frames,
)

#: 草稿默认落在本仓的隔离区。
DEFAULT_DRAFTS_DIR = REPO / "lessons" / "drafts"


class PayloadError(Exception):
    """载荷读不到：没有它，handler 无从知道崩了什么。"""


def parse_payload(raw: str) -> dict | None:
    """把一段文本解析成载荷对象；不是对象就返回 None。"""
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    return data if isinstance(data, dict) else None


def read_payload(argv: Sequence[str], env: Mapping[str, str]) -> dict:
    """从 fatal-guard 用的任何一个通道里取载荷。

    三个通道都读，顺序是 argv → `FATAL_PAYLOAD` → `FATAL_PAYLOAD_FILE`：
    POSIX 路径只给 argv，Windows 路径只给环境变量，用哪个由 fatal-guard 决定。
    """
    candidates: list[str] = []
    if argv:
        candidates.append(argv[-1])

    raw_env = env.get("FATAL_PAYLOAD")
    if raw_env:
        candidates.append(raw_env)

    path = env.get("FATAL_PAYLOAD_FILE")
    if path:
        try:
            candidates.append(Path(path).read_text(encoding="utf-8", errors="replace"))
        except OSError as exc:
            raise PayloadError(f"cannot read FATAL_PAYLOAD_FILE ({path}): {exc}") from exc

    for candidate in candidates:
        payload = parse_payload(candidate)
        if payload is not None:
            return payload

    raise PayloadError(
        "no crash payload found (expected the payload as the last argv entry, "
        "in FATAL_PAYLOAD, or in the file FATAL_PAYLOAD_FILE points at)"
    )


def parse_tombstone(payload: Mapping) -> dict:
    """规范化后的墓碑——用冻结的转换器自己的解析器，不另写一套。"""
    from scripts.tombstone_to_draft import _parse_tombstone

    return _parse_tombstone(dict(payload))


def write_draft(tombstone: Mapping, drafts_dir: Path) -> Path:
    """把草稿留在 `drafts_dir`。

    正文由 `scripts/tombstone_to_draft.py` 自己生成（就是它 CLI 调用的那几个函数），
    所以写出来的文件与 `python3 scripts/tombstone_to_draft.py --from-file …` 的产物
    逐字节一致——那个脚本的行为是冻结的（#3645），这里只调用、不修改。
    """
    from scripts.tombstone_to_draft import _generate_ai_hint, _generate_draft

    drafts_dir = Path(drafts_dir)
    ai_hint = _generate_ai_hint(dict(tombstone))
    filename, body = _generate_draft(dict(tombstone), "", ai_hint)
    drafts_dir.mkdir(parents=True, exist_ok=True)
    path = drafts_dir / filename
    path.write_text(body, encoding="utf-8")
    return path


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="fatal-guard handler: crash → search MisakaNet first, draft only if no hit"
    )
    parser.add_argument("payload", nargs="?",
                        help="崩溃载荷（fatal-guard 放在 argv 最后一项）")
    parser.add_argument("--drafts-dir", metavar="PATH",
                        help=f"草稿写到哪（默认 {DEFAULT_DRAFTS_DIR}）")
    parser.add_argument("--offline", action="store_true",
                        help="跳过检索（无网络），行为与本 issue 之前一致")
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Sequence[str] | None = None, *, search: SearchFn | None = None,
         drafts_dir: Path | None = None) -> int:
    args = parse_args(argv)

    try:
        payload = read_payload([args.payload] if args.payload else [], os.environ)
    except PayloadError as exc:
        print(f"fatal-guard handler: {exc}", file=sys.stderr)
        return 2

    try:
        tombstone = parse_tombstone(payload)
    except ValueError as exc:
        print(f"fatal-guard handler: unusable crash payload: {exc}", file=sys.stderr)
        return 2

    # 检索用的就是草稿里那段错误文本（同一个墓碑、同一个 snippet），
    # 只去掉堆栈帧——帧是证据但不是失败本身。
    lookup = lookup_crash(strip_stack_frames(tombstone["snippet"]),
                           search=search, offline=args.offline)

    if lookup.hit:
        print(format_hit(lookup.lesson))
        return 0

    target_dir = Path(args.drafts_dir) if args.drafts_dir else (drafts_dir or DEFAULT_DRAFTS_DIR)
    try:
        draft = write_draft(tombstone, target_dir)
    except OSError as exc:
        print(f"fatal-guard handler: cannot write the draft: {exc}", file=sys.stderr)
        return 3

    print(format_no_hit(draft, search_note=lookup.skipped_reason))
    return 0


if __name__ == "__main__":
    sys.exit(main())
