#!/usr/bin/env python3
"""Install MisakaNet auto-start behaviour into the coding agents found on this machine.

What "auto-start" means, concretely — three things must be true, and each maps to one
mechanism in this installer:

  1. the agent *can* call the knowledge base      → register the MCP server (or, for an
                                                     agent without an MCP client, install a
                                                     skill that calls it over curl)
  2. the agent *knows when* to call it            → inject the behavioural prompt into the
                                                     agent's own rules file (CLAUDE.md /
                                                     AGENTS.md / SOUL.md)
  3. the checkpoint *fires without the user*       → install a hook that counts turns and
                                                     injects the distillation reminder

Without (3) a "summarise every 20 turns" rule never fires: agents do not keep counters.
Without (1)/(2) the hook has nothing to call. So all three are installed together, and
what could not be installed is reported rather than assumed.

Design rules:
  * idempotent — running twice changes nothing the second time;
  * backed up — every file it rewrites is copied to <file>.misakanet.bak first;
  * marker-scoped — everything it adds sits between `misakanet:start` / `misakanet:end`
    markers, so `--uninstall` removes exactly what was added and nothing else;
  * honest — a capability the local agent does not support (e.g. Codex hooks) is printed
    as "manual step", never faked.

Usage:
  python3 install_misakanet_agent.py                     # install for every detected agent
  python3 install_misakanet_agent.py --only claude,codex # subset
  python3 install_misakanet_agent.py --dry-run            # show what would change
  python3 install_misakanet_agent.py --uninstall          # remove everything it added
  python3 install_misakanet_agent.py --home /tmp/fakehome # test against a scratch HOME
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ENDPOINT = "https://misakanet.org/mcp"
START = "misakanet:start"
END = "misakanet:end"
HERE = Path(__file__).resolve().parent
PROMPT_FILE = HERE / "prompt.md"
HOOK_FILE = HERE / "checkpoint_reminder.py"

# The agents this knows how to configure. `detect` is a path that only exists when the
# agent is actually installed here; everything else hangs off HOME.
AGENTS = ("claude", "codex", "hermes", "dsh")


def _force_utf8_io() -> None:
    """Make stdout/stderr UTF-8 regardless of the console code page.

    On Windows the default is the OEM code page (GBK on zh-CN), so printing the
    summary's tick marks raised UnicodeEncodeError and the installer died *after*
    doing its work - the worst place to fail, because the files were already
    changed. `errors="replace"` guarantees no character can ever crash output.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except Exception:
            pass


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Report:
    """Collects what happened so the summary can be honest about what did not."""

    def __init__(self) -> None:
        self.done: list[str] = []
        self.manual: list[str] = []
        self.skipped: list[str] = []

    def ok(self, msg: str) -> None:
        self.done.append(msg)

    def needs_manual(self, msg: str) -> None:
        self.manual.append(msg)

    def skip(self, msg: str) -> None:
        self.skipped.append(msg)

    def render(self) -> str:
        lines = []
        for title, items, mark in (
            ("已配置", self.done, "✓"),
            ("需要你手动一步", self.manual, "!"),
            ("跳过", self.skipped, "·"),
        ):
            if items:
                lines.append(f"\n{title}（{len(items)}）:")
                lines += [f"  {mark} {i}" for i in items]
        return "\n".join(lines)


def backup(path: Path, dry: bool) -> None:
    if dry or not path.exists():
        return
    shutil.copy2(path, path.with_suffix(path.suffix + ".misakanet.bak"))


def write_text(path: Path, text: str, dry: bool) -> None:
    if dry:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def inject_block(path: Path, block: str, dry: bool) -> str:
    """Put `block` between markers in `path`. Returns a status word."""
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    pattern = re.compile(rf"[ \t]*<!--\s*{START}\s*-->.*?<!--\s*{END}\s*-->\n?", re.S)
    new_body = f"<!-- {START} -->\n{block.strip()}\n<!-- {END} -->\n"
    if pattern.search(existing):
        # lambda, not a bare replacement string: re.sub() interprets backslash escapes
        # in the replacement, and this block legitimately contains literal \n and \"
        # (it documents the intake call). A bare string silently rewrote them into real
        # newlines on every run — which broke idempotency (found by the installer test).
        updated = pattern.sub(lambda _m: new_body, existing, count=1)
        if updated == existing:
            return "unchanged"
        backup(path, dry)
        write_text(path, updated, dry)
        return "updated"
    backup(path, dry)
    separator = "" if not existing or existing.endswith("\n\n") else ("\n" if existing.endswith("\n") else "\n\n")
    write_text(path, existing + separator + new_body, dry)
    return "added"


def strip_block(path: Path, dry: bool) -> bool:
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(rf"[ \t]*<!--\s*{START}\s*-->.*?<!--\s*{END}\s*-->\n?", re.S)
    if not pattern.search(text):
        return False
    backup(path, dry)
    write_text(path, pattern.sub("", text, count=1), dry)
    return True


def marker_pattern(start: str, end: str) -> re.Pattern:
    """Line-anchored marker pattern for TOML comments.

    Anchoring matters: with a prefix-matching marker (`misakanet:end` inside
    `misakanet-top:end`) a non-anchored `.*?` happily spans from one block into the
    other and eats it. Cost of learning this: the first version of this installer
    deleted its own top-level block on install (caught by the TOML parse test).
    """
    return re.compile(rf"(?m)^[ \t]*#\s*{re.escape(start)}\s*$\n?.*?^[ \t]*#\s*{re.escape(end)}\s*$\n?", re.S)


def prompt_block() -> str:
    """The behavioural contract, trimmed to the parts that must live in a rules file."""
    if PROMPT_FILE.exists():
        text = PROMPT_FILE.read_text(encoding="utf-8")
        # Everything after the front matter comment block; keeps rules files readable.
        marker = "## 0. 你有一个外部失败记忆库"
        if marker in text:
            return text[text.index(marker):].rstrip()
    return ("遇到报错/重复踩坑/高风险操作前先调 misakanet_search；命中用 misakanet_get_lesson 取正文；"
            "查不到用 misakanet_submit_intake(kind=\"question\")；约 20 轮或问题解决后脱敏上传 intake。")


# ── per-agent actions ───────────────────────────────────────────────
def detect(home: Path, agent: str) -> bool:
    checks = {
        "claude": [home / ".claude", home / ".claude.json"],
        "codex": [home / ".codex"],
        "hermes": [home / ".hermes"],
        "dsh": [home / ".dsh", home / ".agents"],
    }
    return any(p.exists() for p in checks[agent])


def mcp_server_entry() -> dict:
    """Claude Code / generic JSON shape for a streamable-HTTP MCP server."""
    return {"type": "http", "url": ENDPOINT}


def install_claude(home: Path, dry: bool, rep: Report) -> None:
    cfg = home / ".claude.json"
    data: dict = {}
    if cfg.exists():
        try:
            data = json.loads(cfg.read_text(encoding="utf-8"))
        except Exception as exc:
            rep.needs_manual(f"{cfg} 不是合法 JSON（{exc}）→ 请手动加入 mcpServers.misakanet")
            data = {}
    servers = data.setdefault("mcpServers", {})
    if servers.get("misakanet") == mcp_server_entry():
        rep.ok("Claude Code: MCP 已注册（无改动）")
    else:
        servers["misakanet"] = mcp_server_entry()
        backup(cfg, dry)
        write_text(cfg, json.dumps(data, indent=2, ensure_ascii=False) + "\n", dry)
        rep.ok(f"Claude Code: 注册 MCP `misakanet` → {cfg}")

    rules = home / ".claude" / "CLAUDE.md"
    status = inject_block(rules, prompt_block(), dry)
    rep.ok(f"Claude Code: 规则块 {status} → {rules}")

    settings_path = home / ".claude" / "settings.json"
    settings: dict = {}
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
        except Exception as exc:
            rep.needs_manual(f"{settings_path} 不是合法 JSON（{exc}）→ hooks 未安装")
            settings = {}
    hooks = settings.setdefault("hooks", {})
    # sys.executable, not "python3": on Windows the interpreter is `python`/`py`, and a
    # hook whose command does not exist fails silently (the session just never gets the
    # reminder, with no error anywhere).
    interpreter = sys.executable or "python3"
    hook_cmd = {"type": "command", "command": f'"{interpreter}" "{HOOK_FILE}" prompt'}
    fail_cmd = {"type": "command", "command": f'"{interpreter}" "{HOOK_FILE}" failure'}
    changed = False
    for event, entry in (("UserPromptSubmit", hook_cmd), ("PostToolUseFailure", fail_cmd)):
        bucket = hooks.setdefault(event, [])
        flat = json.dumps(bucket)
        if "checkpoint_reminder" in flat:
            continue
        bucket.append({"hooks": [entry]})
        changed = True
    if changed:
        backup(settings_path, dry)
        write_text(settings_path, json.dumps(settings, indent=2, ensure_ascii=False) + "\n", dry)
        rep.ok(f"Claude Code: 钩子 UserPromptSubmit + PostToolUseFailure → {settings_path}")
    else:
        rep.ok("Claude Code: 钩子已存在（无改动）")


CODEX_TABLE = f"""[mcp_servers.misakanet]
type = "streamable-http"
url = "{ENDPOINT}"
# 写入类工具（write_lesson/preflight）需要 token；把它放进环境变量而不是写进本文件
bearer_token_env_var = "MISAKANET_TOKEN"
"""


TOP_START = "misakanet-top:start"
TOP_END = "misakanet-top:end"


def _has_top_level_key(text: str, key: str) -> bool:
    """True when `key = ...` appears outside any [table] section."""
    in_table = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            in_table = True
            continue
        if not in_table and re.match(rf"^{re.escape(key)}\s*=", stripped):
            return True
    return False


def _insert_before_first_table(text: str, block: str) -> str:
    """Top-level keys must precede the first [table], or TOML scopes them to it."""
    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if line.lstrip().startswith("["):
            return "".join(lines[:index]) + block + "".join(lines[index:])
    separator = "" if not text or text.endswith("\n") else "\n"
    return text + separator + block


def install_codex(home: Path, dry: bool, rep: Report) -> None:
    cfg = home / ".codex" / "config.toml"
    existing = cfg.read_text(encoding="utf-8") if cfg.exists() else ""
    table_block = f"# {START}\n{CODEX_TABLE}# {END}\n"
    top_block = (f"# {TOP_START}\n"
                 "# streamable-http MCP 需要这一行（顶级），否则 Codex 不会用 rmcp client\n"
                 "experimental_use_rmcp_client = true\n"
                 f"# {TOP_END}\n")
    changed = False

    # 1. the top-level switch (only when the file does not already set it)
    top_pattern = marker_pattern(TOP_START, TOP_END)
    if top_pattern.search(existing):
        updated = top_pattern.sub(lambda _m: top_block, existing, count=1)
        if updated != existing:
            existing, changed = updated, True
    elif not _has_top_level_key(existing, "experimental_use_rmcp_client"):
        existing = _insert_before_first_table(existing, top_block)
        changed = True

    # 2. the server table (appended at the end — it *is* a table)
    pattern = marker_pattern(START, END)
    if pattern.search(existing):
        updated = pattern.sub(lambda _m: table_block, existing, count=1)
        if updated != existing:
            existing, changed = updated, True
    else:
        separator = "\n" if existing and not existing.endswith("\n") else ""
        existing, changed = existing + separator + table_block, True

    if changed:
        backup(cfg, dry)
        write_text(cfg, existing, dry)
        rep.ok(f"Codex: 注册 MCP `misakanet`（streamable-http）→ {cfg}")
        rep.needs_manual(
            "Codex: 已写入 experimental_use_rmcp_client = true（顶级，位置在第一个 [table] 之前）"
            "—— 若你的版本已默认启用则无害；若报未知键，删掉 marked 区块即可")
    else:
        rep.ok("Codex: MCP 已注册（无改动）")

    rules = home / ".codex" / "AGENTS.md"
    status = inject_block(rules, prompt_block(), dry)
    rep.ok(f"Codex: 规则块 {status} → {rules}")
    rep.needs_manual(
        "Codex: 没有可用的用户级钩子配置（本次核对的是 config.toml 的 lifecycle hooks，"
        "用户层写法未确认）→ 检查点靠规则块里的「约 20 轮」自律触发；要硬保证就用 "
        "MISAKANET_HOOK_FETCH=1 配外层 wrapper 在每轮后跑 checkpoint_reminder.py")


def install_hermes(home: Path, dry: bool, rep: Report) -> None:
    cfg = home / ".hermes" / "config.yaml"
    if not cfg.exists():
        rep.needs_manual("Hermes: 找不到 ~/.hermes/config.yaml → 先运行一次 `hermes` 生成配置，"
                         f"再执行 `hermes mcp add misakanet --url {ENDPOINT}`")
    else:
        text = cfg.read_text(encoding="utf-8")
        if "misakanet" in text:
            rep.ok("Hermes: 配置里已有 misakanet（无改动）")
        else:
            rep.needs_manual(f"Hermes: 请执行 `hermes mcp add misakanet --url {ENDPOINT}`"
                             "（Hermes 自己管理 YAML 与首次使用同意，脚本不代写）")
    rules = home / ".hermes" / "SOUL.md"
    status = inject_block(rules, prompt_block(), dry)
    rep.ok(f"Hermes: 规则块 {status} → {rules}")
    rep.needs_manual(
        "Hermes: 钩子写在 ~/.hermes/config.yaml 且需要首次同意（allowlist）→ 想启用检查点，"
        f"把命令 `python3 {HOOK_FILE} prompt` 加到它的 prompt 钩子，再跑 `hermes hooks doctor` 确认")


def install_dsh(home: Path, dry: bool, rep: Report) -> None:
    # DSH has no MCP client in its CLI (verified 2026-09-13: no `mcp` subcommand), so the
    # portable path is a skill + the HTTP endpoint over curl.
    skill_src = HERE.parent.parent / "skills" / "misakanet" / "SKILL.md"
    skill_dst_dir = home / ".agents" / "skills" / "misakanet"
    skill_dst = skill_dst_dir / "SKILL.md"
    if not dry:
        skill_dst_dir.mkdir(parents=True, exist_ok=True)
    if skill_src.exists():
        if dry:
            rep.ok(f"DSH: 会安装 skill → {skill_dst}（源 {skill_src}）")
        else:
            writable = skill_src.read_text(encoding="utf-8") + (
                f"\n\n---\n\n## 自启动规则（由 install_misakanet_agent.py 追加）\n\n{prompt_block()}\n"
            )
            current = skill_dst.read_text(encoding="utf-8") if skill_dst.exists() else ""
            if current == writable:
                rep.ok(f"DSH: skill 已是目标内容（无改动）→ {skill_dst}")
            else:
                backup(skill_dst, dry)
                skill_dst.write_text(writable, encoding="utf-8")
                rep.ok(f"DSH: 安装 skill（含自启动规则）→ {skill_dst}")
    else:
        rep.needs_manual(f"DSH: 找不到仓库内的 skill 源（{skill_src}）→ 手动复制 skills/misakanet/")
    rep.needs_manual(
        "DSH: 没有 MCP 客户端 → 让 agent 用 shell 调 curl 访问 "
        f"{ENDPOINT}（prompt.md §0 有可直接粘的命令）")


INSTALLERS = {
    "claude": install_claude,
    "codex": install_codex,
    "hermes": install_hermes,
    "dsh": install_dsh,
}


def uninstall(home: Path, dry: bool, rep: Report) -> None:
    targets = [
        home / ".claude" / "CLAUDE.md",
        home / ".codex" / "AGENTS.md",
        home / ".hermes" / "SOUL.md",
        home / ".agents" / "skills" / "misakanet" / "SKILL.md",
    ]
    for path in targets:
        if strip_block(path, dry):
            rep.ok(f"移除规则块 → {path}")
        # A file we created purely for our block should not survive as an empty file.
        if path.exists() and not path.read_text(encoding="utf-8").strip():
            if not dry:
                path.unlink()
            rep.ok(f"删除只剩空白的规则文件 → {path}")
    cfg = home / ".claude.json"
    if cfg.exists():
        try:
            data = json.loads(cfg.read_text(encoding="utf-8"))
            if data.get("mcpServers", {}).pop("misakanet", None) is not None:
                backup(cfg, dry)
                write_text(cfg, json.dumps(data, indent=2, ensure_ascii=False) + "\n", dry)
                rep.ok(f"移除 MCP 注册 → {cfg}")
        except Exception:
            rep.needs_manual(f"{cfg} 解析失败 → 手动删除 mcpServers.misakanet")
    settings_path = home / ".claude" / "settings.json"
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
            hooks = settings.get("hooks", {})
            changed = False
            for event in list(hooks):
                kept = [b for b in hooks[event] if "checkpoint_reminder" not in json.dumps(b)]
                if len(kept) != len(hooks[event]):
                    changed = True
                    if kept:
                        hooks[event] = kept
                    else:
                        del hooks[event]      # do not leave an empty event behind
            if changed:
                backup(settings_path, dry)
                write_text(settings_path, json.dumps(settings, indent=2, ensure_ascii=False) + "\n", dry)
                rep.ok(f"移除钩子 → {settings_path}")
        except Exception:
            rep.needs_manual(f"{settings_path} 解析失败 → 手动删除 checkpoint_reminder 钩子")
    toml = home / ".codex" / "config.toml"
    if toml.exists():
        text = toml.read_text(encoding="utf-8")
        stripped = text
        for start, end in ((START, END), (TOP_START, TOP_END)):
            stripped = marker_pattern(start, end).sub("", stripped)
        if stripped != text:
            backup(toml, dry)
            write_text(toml, stripped, dry)
            rep.ok(f"移除 MCP 表与顶级开关 → {toml}")
    rep.needs_manual("Hermes 的 MCP 条目由它自己管理 → 需要时执行 `hermes mcp remove misakanet`")


def main(argv: list[str] | None = None) -> int:
    _force_utf8_io()
    parser = argparse.ArgumentParser(description="Install MisakaNet auto-start behaviour")
    parser.add_argument("--home", default=str(Path.home()), help="target HOME (for tests)")
    parser.add_argument("--only", default="", help=f"comma list of {','.join(AGENTS)}")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--uninstall", action="store_true")
    args = parser.parse_args(argv)

    home = Path(args.home).expanduser()
    rep = Report()
    print(f"MisakaNet 自启动安装器 — HOME={home}{'（dry-run）' if args.dry_run else ''} "
          f"@ {_stamp()}")

    if args.uninstall:
        uninstall(home, args.dry_run, rep)
        print(rep.render())
        return 0

    wanted = [a.strip() for a in args.only.split(",") if a.strip()] or list(AGENTS)
    for agent in wanted:
        if agent not in INSTALLERS:
            rep.skip(f"未知 agent: {agent}")
            continue
        if not detect(home, agent):
            rep.skip(f"{agent}: 本机未检测到（{home}/.{agent}* 不存在）")
            continue
        INSTALLERS[agent](home, args.dry_run, rep)

    print(rep.render())
    print(
        "\n验证（对新开的会话说一句即可）：\n"
        "  「docker exit code 137 是什么原因」→ 看它是否调用 misakanet_search\n"
        f"  手动跑一次检查点：echo '{{\"session_id\":\"t\"}}' | python3 \"{HOOK_FILE}\" prompt\n"
        f"  手动跑一次失败提醒：echo '{{\"error\":\"exit code 137\"}}' | python3 \"{HOOK_FILE}\" failure\n"
        "回滚：python3 install_misakanet_agent.py --uninstall（或从 *.misakanet.bak 恢复）"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
