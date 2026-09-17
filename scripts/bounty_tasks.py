#!/usr/bin/env python3
"""可复现的赏金任务集：把「真机对照测量」变成可执行、可打分、可审阅的东西（2026-09-18）。

背景（`docs/maintainer/strategic-assessment-2026-09-18.md` §3）：仓库里没有任何一项测量支持
「装了 MisakaNet 的 agent 会更少重复犯错」，而 issue #1819 要向外部征集这份数据。征集数据最容易
死在两件事上：**任务集不可复现**（每个人自己编题，结果不可比）和**判据不可核**（成功与否靠人嘴说）。
这个脚本把两者都钉死：

* `setup` 造出一个**真实会失败**的场景（离线、可重建、不需要联网）；
* `score` 用**机器判据**给结论，并把判定过程原样打印出来（这就是要贴进 issue 的 log）；
* `verify` 自己证明这套判据**两个方向都会动**：把任务解掉 → 判通过；不碰它 → 判失败。
  只会亮的灯不是灯。

用法（不需要 pytest 知识）：

    python3 scripts/bounty_tasks.py list
    python3 scripts/bounty_tasks.py setup  --task dco --dir /tmp/arm-with
    #   …在这个目录里让**装了 MisakaNet 的 agent** 去修，别自己修…
    python3 scripts/bounty_tasks.py score  --task dco --dir /tmp/arm-with | tee arm-with.log
    python3 scripts/bounty_tasks.py verify            # 判据自检（CI 里也跑）

三个任务都对应仓库里**真实修过**的失败（DCO 签核、编码导致的 UnicodeDecodeError、
Node 18 没有全局 `crypto`），所以"两臂有差别"才有机会被观测到。
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

# ── the three tasks ──────────────────────────────────────────────────────────────────────
PROMPT_DCO = """这个仓库的提交被 CI 拒绝了，报错是 DCO（每个提交必须有 Signed-off-by 行）。
请把它修好，让 CI 能过。你可以用任何你熟悉的方式。"""

PROMPT_ENCODING = """运行 `python3 report.py` 会崩。请修好它，让 `python3 report.py` 正常打印
那一行统计结果（退出码 0）。不要改动 data.txt。"""

PROMPT_CRYPTO = """这个脚本在 Node 18 上跑不起来（同事的机器上是 18.x，你的机器上是新版所以看不出来）。
请修好它，让它在 Node 18 上也能正常输出一行 id。"""

NODE18_PRELOAD = "delete globalThis.crypto;\n"


def _node_bin() -> str:
    """The Node binary to score with; `node` is required by the task itself."""
    return shutil.which("node") or "node"


def setup_dco(root: Path) -> str:
    """A git repo whose only commit is missing the DCO trailer."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "src.txt").write_text("hello\n", encoding="utf-8")
    run = lambda *a: subprocess.run(["git", *a], cwd=root, capture_output=True, text=True,
                                    check=True, env=_git_env())
    run("init", "-q", "-b", "main")
    run("add", "-A")
    run("commit", "-q", "-m", "Add src.txt")
    return PROMPT_DCO


def score_dco(root: Path) -> tuple[bool, list[str]]:
    log: list[str] = []
    proc = subprocess.run(["git", "log", "--format=%H%x00%B%x00", "main"], cwd=root,
                          capture_output=True, text=True, env=_git_env())
    log.append(f"$ git log --format=%H%x00%B%x00 main  (exit {proc.returncode})")
    if proc.returncode != 0:
        log.append(proc.stderr.strip())
        return False, log
    commits = [c for c in proc.stdout.split("\x00\x00") if c.strip()]
    log.append(f"commits on main: {len(commits)}")
    if not commits:
        return False, log + ["no commit on main"]
    bad = []
    for block in commits:
        lines = block.strip().splitlines()
        body = "\n".join(lines[1:])
        has_trailer = any(l.strip().lower().startswith("signed-off-by:") for l in body.splitlines())
        log.append(f"  {lines[0][:12]}  Signed-off-by: {'yes' if has_trailer else 'NO'}")
        if not has_trailer:
            bad.append(lines[0][:12])
    return (not bad), log + ([f"still missing on: {', '.join(bad)}"] if bad else ["every commit is signed off"])


def setup_encoding(root: Path) -> str:
    """A GBK-encoded data file and a reader that opens it as UTF-8."""
    root.mkdir(parents=True, exist_ok=True)
    # Written as GBK on purpose: the failure is a real one, not a synthetic raise.
    (root / "data.txt").write_bytes("标题,次数\n巡检,42\n报警,7\n".encode("gbk"))
    (root / "report.py").write_text(textwrap.dedent('''
        """Print the total count from data.txt."""
        with open("data.txt", encoding="utf-8") as fh:
            lines = [l for l in fh.read().splitlines() if l.strip()][1:]
        total = sum(int(l.split(",")[1]) for l in lines)
        print(f"total={total}")
    ''').lstrip(), encoding="utf-8")
    return PROMPT_ENCODING


def score_encoding(root: Path) -> tuple[bool, list[str]]:
    log = ["$ python3 report.py"]
    proc = subprocess.run([sys.executable, "report.py"], cwd=root, capture_output=True, text=True)
    log.append(f"exit={proc.returncode}")
    log.append(f"stdout={proc.stdout.strip()!r}")
    if proc.stderr.strip():
        log.append(f"stderr={proc.stderr.strip()[-300:]!r}")
    ok = proc.returncode == 0 and proc.stdout.strip() == "total=49"
    # The expected value is derived here, independently of the script under test.
    if proc.returncode == 0 and not ok:
        log.append("the number printed is not the one in the data (49 = 42 + 7)")
    # `data.txt` must be untouched: editing the input is not fixing the program.
    data = (root / "data.txt").read_bytes()
    if not any(b > 0x7f for b in data):
        log.append("data.txt no longer contains non-UTF-8 bytes — it was rewritten, not read")
        ok = False
    return ok, log


def setup_crypto(root: Path) -> str:
    """A script that relies on the global Web Crypto object, which Node 18 does not have."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "id.mjs").write_text(
        "console.log(`id=${crypto.randomUUID()}`);\n", encoding="utf-8")
    (root / "package.json").write_text('{"type":"module","engines":{"node":">=18"}}\n', encoding="utf-8")
    (root / "node18-preload.mjs").write_text(NODE18_PRELOAD, encoding="utf-8")
    return PROMPT_CRYPTO


def score_crypto(root: Path) -> tuple[bool, list[str]]:
    preload = root / "node18-preload.mjs"
    if not preload.exists():                       # the preload is the fixture's, not the solver's
        return False, ["node18-preload.mjs is missing — it is part of the fixture, not the task"]
    log = [f"$ node --import ./node18-preload.mjs id.mjs   (deletes globalThis.crypto first)"]
    proc = subprocess.run([_node_bin(), "--import", preload.resolve().as_uri(), "id.mjs"],
                          cwd=root, capture_output=True, text=True)
    log.append(f"exit={proc.returncode}")
    log.append(f"stdout={proc.stdout.strip()!r}")
    if proc.stderr.strip():
        # The *error*, not the last line: Node ends its crash output with `Node.js v22.22.3`, so a
        # `[-1]` tail would hand a reviewer a version banner instead of `crypto is not defined`.
        # (Caught by tests/test_bounty_tasks.py, which asserts the real message is in the log.)
        log.append("stderr:")
        for line in proc.stderr.strip().splitlines()[-8:]:
            log.append(f"  | {line[:300]}")
    ok = proc.returncode == 0 and proc.stdout.strip().startswith("id=")
    return ok, log


TASKS = {
    "dco": (setup_dco, score_dco, "一个提交缺 Signed-off-by（DCO 门禁会红）"),
    "encoding": (setup_encoding, score_encoding, "GBK 数据被按 UTF-8 读，UnicodeDecodeError"),
    "node-crypto": (setup_crypto, score_crypto, "Node 18 没有全局 crypto，脚本跑不起来"),
}


def _git_env() -> dict:
    """A deterministic committer, so the fixture does not depend on the solver's git config."""
    import os
    env = dict(os.environ)
    env.update({
        "GIT_AUTHOR_NAME": "bounty", "GIT_AUTHOR_EMAIL": "bounty@example.invalid",
        "GIT_COMMITTER_NAME": "bounty", "GIT_COMMITTER_EMAIL": "bounty@example.invalid",
        "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null",
    })
    return env


# ── the guard: prove both directions of every scorer ─────────────────────────────────────
def _solve(task: str, root: Path) -> None:
    """The minimal honest fix, used only by `verify` to show the scorer can go green."""
    if task == "dco":
        subprocess.run(["git", "commit", "--amend", "--no-edit", "--signoff"], cwd=root,
                       capture_output=True, check=True, env=_git_env())
    elif task == "encoding":
        path = root / "report.py"
        path.write_text(path.read_text(encoding="utf-8").replace('encoding="utf-8"', 'encoding="gbk"'),
                        encoding="utf-8")
    elif task == "node-crypto":
        (root / "id.mjs").write_text(
            "import { randomUUID } from 'node:crypto';\nconsole.log(`id=${randomUUID()}`);\n",
            encoding="utf-8")


def cmd_verify() -> int:
    """Every scorer must say 'unsolved' before the fix and 'solved' after it."""
    import tempfile
    failures = []
    for name, (setup, score, _desc) in TASKS.items():
        with tempfile.TemporaryDirectory(prefix=f"bounty-{name}-") as tmp:
            root = Path(tmp) / "task"
            setup(root)
            before, _ = score(root)
            if before:
                failures.append(f"{name}: the untouched fixture already scores as solved")
                continue
            _solve(name, root)
            after, log = score(root)
            print(f"--- {name}: untouched={before} solved={after}")
            for line in log:
                print(f"    {line}")
            if not after:
                failures.append(f"{name}: the scored fix did not pass")
    if failures:
        print("\nFIXTURE PROBLEM — a scorer that cannot move is not a scorer:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"\nok: all {len(TASKS)} fixtures fail before the fix and pass after it")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="bounty task fixtures and scorers (issue #1819)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="print the tasks")
    for name in ("setup", "score"):
        p = sub.add_parser(name)
        p.add_argument("--task", required=True, choices=sorted(TASKS))
        p.add_argument("--dir", required=True, type=Path)
    sub.add_parser("verify", help="self-check: both directions of every scorer")
    args = ap.parse_args()

    if args.cmd == "list":
        for name, (_s, _sc, desc) in sorted(TASKS.items()):
            print(f"{name:12} {desc}")
        return 0
    if args.cmd == "verify":
        return cmd_verify()

    setup, score, _desc = TASKS[args.task]
    if args.cmd == "setup":
        root = args.dir
        if root.exists() and any(root.iterdir()):
            print(f"{root} is not empty — refusing to build a fixture on top of it", file=sys.stderr)
            return 2
        prompt = setup(root)
        print(f"fixture: {args.task} → {root}")
        print("把这个交给你的 agent（不要自己修，这一臂要测的是它）：")
        print(f"  {prompt}")
        print(f"跑完之后： python3 scripts/bounty_tasks.py score --task {args.task} --dir {root}")
        return 0

    ok, log = score(args.dir)
    print(f"# score --task {args.task} --dir {args.dir}")
    for line in log:
        print(line)
    print(f"# RESULT: {'SOLVED' if ok else 'NOT SOLVED'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
