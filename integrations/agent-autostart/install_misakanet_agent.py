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
# The question the onboarding text tells a user to ask. See the JS installer for why this is a
# constant, and why it is not "docker exit code 137": tests/test_onboarding_example.py checks
# offline that the corpus answers it with a lesson about that very failure.
ONBOARDING_QUERY = "pip install timeout"
START = "misakanet:start"
END = "misakanet:end"
HERE = Path(__file__).resolve().parent
PROMPT_FILE = HERE / "prompt.md"
HOOK_FILE = HERE / "checkpoint_reminder.py"      # the Python implementation (fallback)
HOOK_FILE_MJS = HERE / "checkpoint_reminder.mjs"  # the Node implementation (preferred)

# The agents this knows how to configure. `detect` is a path that only exists when the
# agent is actually installed here; everything else hangs off HOME.
AGENTS = ("claude", "codex", "hermes", "openclaw", "dsh")


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


def hook_command(mode: str) -> str:
    """Command line for the checkpoint hook, using the runtime that certainly exists.

    Claude Code and Codex *are* Node programs, so `node` is present wherever they run;
    Python is not. A hook whose command cannot be found fails silently - the reminder just
    never appears, with no error anywhere - so this picks Node when available and falls
    back to the Python implementation only when it is not.
    """
    if HOOK_FILE_MJS.exists():
        node = shutil.which("node")
        if node:
            return f'"{node}" "{HOOK_FILE_MJS}" {mode}'
    interpreter = shutil.which("python3") or shutil.which("python") or sys.executable
    return f'"{interpreter}" "{HOOK_FILE}" {mode}'


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


RAW_BASE_DEFAULT = "https://raw.githubusercontent.com/Ikalus1988/MisakaNet/main"
# raw.githubusercontent stalls on blocked networks; these two answered instantly from the
# same box where raw hung (jsDelivr 1.6s, ghproxy 1.0s). Keep the order: primary first.
MIRRORS = {
    "jsdelivr": "https://cdn.jsdelivr.net/gh/Ikalus1988/MisakaNet@main",
    "ghproxy": "https://ghproxy.net/https://raw.githubusercontent.com/Ikalus1988/MisakaNet/main",
}


def _fetch_raw(rel_path: str, timeout: float = 10.0) -> str:
    """Fetch a repo file over HTTP. Returns "" when offline.

    Needed when the installer runs outside a clone (the one-line bootstrap), where
    `skills/misakanet/SKILL.md` is not on disk. MISAKANET_RAW_BASE makes this testable
    (point it at a file:// or localhost URL).
    """
    import urllib.request

    primary = os.environ.get("MISAKANET_RAW_BASE", RAW_BASE_DEFAULT).rstrip("/")
    bases = [primary]
    if not os.environ.get("MISAKANET_RAW_ONLY"):
        bases += [MIRRORS["jsdelivr"], MIRRORS["ghproxy"]]
    for base in bases:
        try:
            with urllib.request.urlopen(f"{base}/{rel_path}", timeout=timeout) as response:
                return response.read().decode("utf-8")
        except Exception:
            continue
    return ""


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
        # cc-haha / claude-haha is a Claude Code fork that reads ~/.claude (its adapters
        # README points at ~/.claude/adapters.json and it honours CLAUDE_CONFIG_DIR), so a
        # ~/cc-haha checkout counts as evidence that the claude target applies to it too.
        "claude": [home / ".claude", home / ".claude.json", home / "cc-haha"],
        "codex": [home / ".codex"],
        "hermes": [home / ".hermes"],
        "openclaw": [home / ".openclaw"],
        "dsh": [home / ".dsh", home / ".agents"],
    }
    return any(p.exists() for p in checks[agent])


def mcp_server_entry(token: str = "") -> dict:
    """Claude Code / generic JSON shape for a streamable-HTTP MCP server.

    With a token the reads are no longer metered (5/day/IP anonymised), which matters for
    exactly the user who will never run `misakanet_register` by hand: without this they hit
    "quota exceeded" on their first busy day and conclude the thing is broken.
    """
    entry: dict = {"type": "http", "url": ENDPOINT}
    if token:
        entry["headers"] = {"Authorization": f"Bearer {token}"}
    return entry


def _read_token(home: Path) -> str:
    path = _state_dir(home) / "token"
    try:
        return path.read_text(encoding="utf-8").strip() if path.exists() else ""
    except Exception:
        return ""


def install_claude(home: Path, dry: bool, rep: Report) -> None:
    cfg = home / ".claude.json"
    data: dict = {}
    if cfg.exists():
        try:
            data = json.loads(cfg.read_text(encoding="utf-8"))
        except Exception as exc:
            rep.needs_manual(f"{cfg} 不是合法 JSON（{exc}）→ 请手动加入 mcpServers.misakanet")
            data = {}
    entry = mcp_server_entry(_read_token(home))
    servers = data.setdefault("mcpServers", {})
    if servers.get("misakanet") == entry:
        rep.ok("Claude Code: MCP 已注册（无改动）")
    else:
        servers["misakanet"] = entry
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
    hook_cmd = {"type": "command", "command": hook_command("prompt")}
    fail_cmd = {"type": "command", "command": hook_command("failure")}
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


def codex_table(token: str = "") -> str:
    """Codex MCP table. Token goes in `http_headers` rather than `bearer_token_env_var`:
    an env var has to be exported by the user's shell (which this user will not do), while
    the header is written once and used by Codex itself."""
    lines = [
        "[mcp_servers.misakanet]",
        'type = "streamable-http"',
        f'url = "{ENDPOINT}"',
    ]
    if token:
        lines.append('http_headers = { Authorization = "Bearer ' + token + '" }')
    else:
        lines.append('# 没有 token：读走匿名通道（5/天/IP）。注册后可写入此文件的 http_headers。')
    return "\n".join(lines) + "\n"


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
    table_block = f"# {START}\n{codex_table(_read_token(home))}# {END}\n"
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
        cli = shutil.which("hermes")
        if "misakanet" in text:
            rep.ok("Hermes: 配置里已有 misakanet（无改动）")
        elif cli and not dry:
            rc, out = _run_cli([cli, "mcp", "add", "misakanet", "--url", ENDPOINT])
            if rc == 0:
                rep.ok("Hermes: 已注册 MCP `misakanet`（hermes mcp add）")
            else:
                rep.needs_manual(f"Hermes: `hermes mcp add` 失败：{out.strip()[:200]}")
        elif cli and dry:
            rep.ok(f"Hermes: 会执行 `hermes mcp add misakanet --url {ENDPOINT}`")
        else:
            rep.needs_manual(f"Hermes: 没找到 hermes CLI → 手动执行 "
                             f"`hermes mcp add misakanet --url {ENDPOINT}`")
    rules = home / ".hermes" / "SOUL.md"
    status = inject_block(rules, prompt_block(), dry)
    rep.ok(f"Hermes: 规则块 {status} → {rules}")
    rep.needs_manual(
        "Hermes: 钩子需要它自己的 consent/allowlist，脚本不代写。想启用「首轮自报 + 检查点沉淀」，"
        f"把这段加到 ~/.hermes/config.yaml（事件名取自 hermes 的 VALID_HOOKS）：\n"
        "      hooks:\n"
        f"        on_session_start:\n          - command: \"node {HOOK_FILE_MJS} prompt\"\n"
        f"        post_tool_call:\n          - command: \"node {HOOK_FILE_MJS} failure\"\n"
        f"        on_session_end:\n          - command: \"node {HOOK_FILE_MJS} prompt\"\n"
        "      然后 `hermes hooks doctor` 验证（首次会要求同意；hermes 的 payload 形状与 CC 不同，"
        "若钩子收不到 session_id，可用 MISAKANET_HOOK_DEBUG=1 看实际输入再适配）")


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
        downloaded = _fetch_raw("skills/misakanet/SKILL.md")
        if downloaded:
            if not dry:
                skill_dst_dir.mkdir(parents=True, exist_ok=True)
                skill_dst.write_text(downloaded + f"\n\n---\n\n{prompt_block()}\n", encoding="utf-8")
            rep.ok(f"DSH: 从远端取回 skill 并安装 → {skill_dst}")
        else:
            rep.needs_manual("DSH: 既不在仓库内、也取不回 skill 源 → 手动复制 skills/misakanet/")
    rep.needs_manual(
        "DSH: 没有 MCP 客户端 → 让 agent 用 shell 调 curl 访问 "
        f"{ENDPOINT}（prompt.md §0 有可直接粘的命令）")


STATE_DIR = Path.home() / ".misakanet-agent"


def _state_dir(home: Path) -> Path:
    """Where identity/token live. `home` is honoured so tests never touch the real one."""
    return home / ".misakanet-agent"


CANONICAL_ENDPOINT = "https://misakanet.org/mcp"


def _trusted_target(endpoint: str, token: str) -> tuple[str, str]:
    """(url, token) under the same policy as the hooks: a token that came from a file is a
    machine-local secret and only goes to the canonical origin; an exported MISAKANET_TOKEN
    is the user's explicit intent and is honoured against a custom endpoint.

    Without this, one environment variable would be enough to redirect a local secret.
    """
    import urllib.parse

    env_token = os.environ.get("MISAKANET_TOKEN", "").strip()
    if env_token or not token:
        return endpoint, env_token or token
    try:
        if urllib.parse.urlparse(endpoint).netloc != urllib.parse.urlparse(CANONICAL_ENDPOINT).netloc:
            return endpoint, ""
    except Exception:
        return endpoint, ""
    return CANONICAL_ENDPOINT, token


def _post(endpoint: str, tool: str, arguments: dict, token: str = "", timeout: float = 6.0) -> dict:
    """One MCP tools/call over streamable HTTP. Returns {} on any failure (offline is fine)."""
    endpoint, token = _trusted_target(endpoint, token)
    import urllib.error
    import urllib.request

    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                       "params": {"name": tool, "arguments": arguments}}).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "MCP-Protocol-Version": "2025-06-18",
        "Origin": "https://misakanet.org",
        "User-Agent": "misakanet-setup/1.0",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        with urllib.request.urlopen(
            urllib.request.Request(endpoint, data=body, headers=headers), timeout=timeout
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
        result = payload.get("result", {})
        return result.get("structuredContent") or json.loads(result["content"][0]["text"])
    except Exception:
        return {}


def ensure_identity(home: Path, endpoint: str, dry: bool, rep: Report) -> None:
    """Register an anonymous node once and store its token, so write tools need no setup.

    A new user should not have to discover `misakanet_register`, copy a token and export a
    variable before the write path works - that is the step that turns "installed" into
    "never used". The client_id is generated locally and stored, so re-running returns the
    same node (identity drift was the defect fixed in e41e469eb).
    """
    token_path = _state_dir(home) / "token"
    client_path = _state_dir(home) / "client_id"
    if token_path.exists() and token_path.read_text(encoding="utf-8").strip():
        rep.ok(f"匿名身份：已有 token（{token_path}）")
        return
    if dry:
        rep.ok(f"匿名身份：会注册并把 token 写入 {token_path}")
        return

    client_id = ""
    if client_path.exists():
        client_id = client_path.read_text(encoding="utf-8").strip()
    if not client_id:
        import uuid
        client_id = f"setup-{uuid.uuid4()}"
        client_path.parent.mkdir(parents=True, exist_ok=True)
        client_path.write_text(client_id, encoding="utf-8")

    result = _post(endpoint, "misakanet_register", {"agent_type": "setup", "client_id": client_id})
    token = str(result.get("token") or "")
    if not token:
        rep.needs_manual(
            "匿名身份：注册没成功（可能离线/被限流）→ 读课程不受影响；要用写入类工具时手动执行 "
            "misakanet_register，并把 token 写入 " + str(token_path))
        return
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(token, encoding="utf-8")
    try:
        token_path.chmod(0o600)
    except Exception:
        pass
    rep.ok(f"匿名身份：node {result.get('node_id', '?')} → token 已存 {token_path}（0600，未写入任何 agent 配置）")


def verify(home: Path, endpoint: str, rep: Report) -> bool:
    """Post-install self-check: the difference between "installed" and "known to work"."""
    ok = True
    identity = _post(endpoint, "misakanet_search", {"query": ONBOARDING_QUERY, "top": 1},
                     token=os.environ.get("MISAKANET_TOKEN", "") or "")
    if identity:
        rep.ok(f"端点可达：{endpoint} 返回了检索结果")
    else:
        ok = False
        rep.needs_manual(f"端点不可达或无响应：{endpoint}（网络/代理问题？读课程会静默失败）")

    token_file = _state_dir(home) / "token"
    if token_file.exists() and token_file.read_text(encoding="utf-8").strip():
        rep.ok("写入通道：token 已就绪（write_lesson / preflight 可用）")
    else:
        rep.skip("写入通道：无 token（只读也完全可用）")

    for agent in AGENTS:
        if not detect(home, agent):
            continue
        if agent == "claude":
            cfg = home / ".claude.json"
            data = {}
            if cfg.exists():
                try:
                    data = json.loads(cfg.read_text(encoding="utf-8"))
                except Exception:
                    data = {}
            has_mcp = "misakanet" in (data.get("mcpServers") or {})
            ok &= has_mcp
            (rep.ok if has_mcp else rep.needs_manual)(
                f"{agent}: MCP 注册 {'✓' if has_mcp else '✗ 缺失'} （{cfg}）")
            settings = home / ".claude" / "settings.json"
            # Parse the JSON - a regex cannot see `\"` inside the command string, which is
            # how the first version of this check reported a working hook as missing.
            commands: list[str] = []
            if settings.exists():
                try:
                    data = json.loads(settings.read_text(encoding="utf-8"))
                    for entries in (data.get("hooks") or {}).values():
                        for entry in entries:
                            for hook in (entry or {}).get("hooks", []):
                                cmd = hook.get("command", "")
                                if "checkpoint_reminder" in cmd:
                                    commands.append(cmd)
                except Exception:
                    commands = []
            hooks_ok = bool(commands)
            interpreter_ok = True
            if commands:
                exe = commands[0].split('"')[1] if commands[0].startswith('"') else commands[0].split()[0]
                interpreter_ok = bool(shutil.which(exe) or Path(exe).exists())
            ok &= hooks_ok and interpreter_ok
            if hooks_ok and interpreter_ok:
                rep.ok(f"{agent}: 检查点钩子 ✓（{commands[0][:60]}…）")
            elif hooks_ok and not interpreter_ok:
                rep.needs_manual(
                    f"{agent}: 钩子命令里的解释器不存在 → 钩子会静默不触发，重跑安装器即可修（{commands[0]}）")
            else:
                rep.needs_manual(f"{agent}: 检查点钩子 ✗ 缺失")
        rules = {"codex": home / ".codex" / "AGENTS.md", "hermes": home / ".hermes" / "SOUL.md",
                 "dsh": home / ".agents" / "skills" / "misakanet" / "SKILL.md"}.get(agent)
        if rules is not None:
            present = rules.exists() and "misakanet" in rules.read_text(encoding="utf-8")
            ok &= present
            (rep.ok if present else rep.needs_manual)(
                f"{agent}: 规则/skill {'✓' if present else '✗ 缺失'}（{rules}）")
    return ok


def report_url(home: Path, note: str) -> str:
    """A prefilled issue URL — the only support channel for an anonymous installer."""
    import platform
    import urllib.parse

    detected = ",".join(a for a in AGENTS if detect(home, a)) or "none"
    # No hostname, no username, no paths in the payload: this goes to a public tracker.
    body = "\n".join([
        "### 安装器自检",
        "",
        f"- OS: {platform.platform()}",
        f"- Python: {platform.python_version()}",
        f"- 检测到的 agent: {detected}",
        f"- 备注: {note}",
    ])
    return ("https://github.com/Ikalus1988/MisakaNet/issues/new"
            "?title=" + urllib.parse.quote("[setup] 安装器问题") +
            "&body=" + urllib.parse.quote(body))


def _run_cli(cmd: list[str], timeout: float = 60.0) -> tuple[int, str]:
    """Run an agent's own CLI. Returns (returncode, combined output)."""
    import subprocess

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except FileNotFoundError:
        return 127, f"{cmd[0]}: not found"
    except Exception as exc:                                  # pragma: no cover - env specific
        return 1, str(exc)


def install_openclaw(home: Path, dry: bool, rep: Report) -> None:
    """OpenClaw: rules live in ~/.openclaw/workspace, MCP servers in `openclaw mcp.servers`.

    It has its own MCP client (`openclaw mcp add`), so unlike DSH it can call MisakaNet
    natively. The CLI keeps its own cache under $XDG_CACHE_HOME, which may be read-only in
    sandboxes - that surfaces as "Could not start the CLI", hence the env hint below.
    """
    rules = home / ".openclaw" / "workspace" / "AGENTS.md"
    if not rules.parent.is_dir():
        rep.needs_manual(f"OpenClaw: 找不到 {rules.parent} → 先运行一次 openclaw 生成 workspace")
    else:
        status = inject_block(rules, prompt_block(), dry)
        rep.ok(f"OpenClaw: 规则块 {status} → {rules}")

    cli = shutil.which("openclaw")
    if not cli:
        rep.needs_manual("OpenClaw: 没找到 openclaw CLI → 手动执行 "
                         f"`openclaw mcp add misakanet --url {ENDPOINT} --transport streamable-http`")
        return
    if dry:
        rep.ok(f"OpenClaw: 会执行 `openclaw mcp add misakanet --url {ENDPOINT} "
               "--transport streamable-http --no-probe`")
        return

    token = _read_token(home)
    cmd = [cli, "mcp", "add", "misakanet", "--url", ENDPOINT,
           "--transport", "streamable-http", "--no-probe"]
    if token:
        cmd += ["--header", f"Authorization=Bearer {token}"]
    rc, out = _run_cli(cmd)
    if rc == 0:
        rep.ok("OpenClaw: 已注册 MCP `misakanet`（openclaw mcp add）")
        return
    if "Could not start the CLI" in out:
        rep.needs_manual(
            "OpenClaw: CLI 起不动（缓存目录不可写）→ 设 XDG_CACHE_HOME 到可写目录后重跑，"
            f"或手动执行：openclaw mcp add misakanet --url {ENDPOINT} --transport streamable-http")
    else:
        rep.needs_manual(f"OpenClaw: `openclaw mcp add` 失败：{out.strip()[:200]}")


INSTALLERS = {
    "claude": install_claude,
    "codex": install_codex,
    "hermes": install_hermes,
    "openclaw": install_openclaw,
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
    parser.add_argument("--verify", action="store_true",
                        help="self-check: endpoint, MCP registration, hooks, token")
    parser.add_argument("--no-register", action="store_true",
                        help="do not provision an anonymous token (read-only usage)")
    parser.add_argument("--report", metavar="NOTE", default="",
                        help="print a prefilled issue URL with this note")
    args = parser.parse_args(argv)

    home = Path(args.home).expanduser()
    rep = Report()
    print(f"MisakaNet 自启动安装器 — HOME={home}{'（dry-run）' if args.dry_run else ''} "
          f"@ {_stamp()}")

    endpoint = os.environ.get("MISAKANET_ENDPOINT", ENDPOINT)

    if args.report:
        print(report_url(home, args.report))
        return 0

    if args.verify:
        ok = verify(home, endpoint, rep)
        print(rep.render())
        print("\n结论：" + (f"READY —— 直接开一个新会话测试即可（问它 {ONBOARDING_QUERY}）"
                          if ok else "NOT READY —— 上面每一条 ✗ 都给了修复动作"))
        return 0 if ok else 1

    if args.uninstall:
        uninstall(home, args.dry_run, rep)
        print(rep.render())
        return 0

    wanted = [a.strip() for a in args.only.split(",") if a.strip()] or list(AGENTS)
    targets: list[str] = []
    for agent in wanted:
        if agent not in INSTALLERS:
            rep.skip(f"未知 agent: {agent}")
        elif not detect(home, agent):
            rep.skip(f"{agent}: 本机未检测到（{home}/.{agent}* 不存在）")
        else:
            targets.append(agent)

    # Identity FIRST, then the agents: the token has to exist before the MCP entries are
    # written, or the config lands without the Authorization header and the user hits the
    # anonymous 5-reads/day wall on their first busy day. A HOME with no agents gets no
    # identity at all (an installer that litters is worse than one that does nothing).
    if args.no_register:
        rep.skip("匿名身份：--no-register，跳过（只读使用不需要）")
    elif not targets:
        rep.skip("匿名身份：未配置任何 agent，跳过")
    else:
        ensure_identity(home, endpoint, args.dry_run, rep)

    for agent in targets:
        INSTALLERS[agent](home, args.dry_run, rep)

    print(rep.render())
    print("\n自检：python3 install_misakanet_agent.py --verify（一条命令告诉你到底通不通）")
    print(
        "\n验证（对新开的会话说一句即可）：\n"
        f"  「{ONBOARDING_QUERY} 是什么原因」→ 看它是否调用 misakanet_search\n"
        f"  手动跑一次检查点：echo '{{\"session_id\":\"t\"}}' | python3 \"{HOOK_FILE}\" prompt\n"
        f"  手动跑一次失败提醒：echo '{{\"error\":\"exit code 137\"}}' | python3 \"{HOOK_FILE}\" failure\n"
        "回滚：python3 install_misakanet_agent.py --uninstall（或从 *.misakanet.bak 恢复）"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
