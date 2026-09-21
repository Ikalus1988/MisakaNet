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
from functools import partial
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
# 三个示例而不是一个，且都是"错误原文里的独特片段"，不是整句自然语言。
# 单一样例会把语料显得只有一个主题；而整句提问（"如何切换识图模型"）在这个按错误文本/关键词
# 建索引的语料上命中为 0 —— 规则块也是这样要求 agent 的。三个都由
# tests/test_onboarding_example.py 离线校验：新用户第一条命中必须是关于该问题的课程。
ONBOARDING_QUERIES = ["switch vision model", "context window exceeded", "tool call permission denied"]
START = "misakanet:start"
END = "misakanet:end"
HERE = Path(__file__).resolve().parent
PROMPT_FILE = HERE / "prompt.md"
HOOK_FILE = HERE / "checkpoint_reminder.py"      # the Python implementation (fallback)
HOOK_FILE_MJS = HERE / "checkpoint_reminder.mjs"  # the Node implementation (preferred)

# The agents this knows how to configure. `detect` is a path that only exists when the
# agent is actually installed here; everything else hangs off HOME.
AGENTS = ("claude", "codex", "hermes", "openclaw", "codewhale",
          "cursor", "gemini", "copilot", "opencode", "kiro", "dsh")


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


# 只读类 MCP 工具预先放行：否则用户触发的**第一次**检索会被 Claude Code 权限系统拒绝
# （"you haven't granted it yet"），整个产品的第一印象变成被拦下。2026-09-16 本机复现 +
# macOS 现场测试同样报告。write_lesson 故意不在其中：那是有 Bearer 的写入路径，
# 静默放行一个写工具与放行读工具是两种决定。
CLAUDE_ALLOWED_TOOLS = [
    "mcp__misakanet__misakanet_search",
    "mcp__misakanet__misakanet_get_lesson",
    "mcp__misakanet__misakanet_me_events",
    "mcp__misakanet__misakanet_preflight",
    "mcp__misakanet__misakanet_submit_intake",
]


def prompt_block() -> str:
    """调用规则（按顺序照做）—— 与 JS 安装包里的 PROMPT_BLOCK 同义。

    实际的块内容优先取同目录 `prompt.md`（§0 起），这份 docstring 只是速览。
    第 ② 步的示例刻意**不写死**在这里：它从 ONBOARDING_QUERIES 取，样例文本只允许有一个出处
    （tests/test_onboarding_example.py 会数重复）。
"""
    if PROMPT_FILE.exists():
        text = PROMPT_FILE.read_text(encoding="utf-8")
        # Everything after the front matter comment block; keeps rules files readable.
        marker = "## 0. 你有一个外部失败记忆库"
        if marker in text:
            return text[text.index(marker):].rstrip()
    return ("遇到报错/重复踩坑/高风险操作前先调 misakanet_search；命中用 misakanet_get_lesson 取正文；"
            "查不到用 misakanet_submit_intake(kind=\"question\")；约 20 轮或问题解决后脱敏上传 intake。")


# ── per-agent actions ───────────────────────────────────────────────
# The targets whose whole install is one MCP entry in one JSON file. Each entry shape is the one
# that vendor's own documentation shows, and they are **not** interchangeable: Gemini CLI's remote
# field is `httpUrl` (its `url` means SSE), OpenCode nests under `mcp` rather than `mcpServers` and
# wants `type: "remote"`, Copilot CLI wants `type: "http"`, while Cursor and Kiro take a bare `url`.
# A copied entry with the wrong key fails **silently**, so each shape is pinned by tests.
#
# None of these five has a rules block or a hook this installer can write — their rules are
# project-scoped files — so tier ① is the whole install and the output says so.
MCP_ONLY_TARGETS: dict[str, dict] = {
    "cursor": {
        "label": "Cursor",
        "detect": ".cursor",
        "config": (".cursor", "mcp.json"),
        "container": "mcpServers",
        "url_field": "url",
        "rules": ".cursor/rules/*.mdc 是项目级的，本安装器不知道你的项目在哪",
        "rule_hint": "想让 Cursor 主动去查，把 .cursor/rules/misakanet-failure-memory.mdc 放进项目",
        "manual": "重启 Cursor 后在 Settings → MCP 里确认看得见 misakanet"
                  "（本安装器只写用户级 ~/.cursor/mcp.json，项目级归你自己管）",
    },
    "gemini": {
        "label": "Gemini CLI",
        "detect": ".gemini",
        "config": (".gemini", "settings.json"),
        "container": "mcpServers",
        "url_field": "httpUrl",
        "rules": "它读 GEMINI.md（全局与项目树），本安装器不写别人的规则文件",
        "rule_hint": "想让 Gemini CLI 主动去查，把规则块加进项目的 GEMINI.md",
        "manual": "重启会话后用 /mcp 复核 misakanet 是否列出",
    },
    "copilot": {
        "label": "Copilot CLI",
        "detect": ".copilot",
        "config": (".copilot", "mcp-config.json"),
        "container": "mcpServers",
        "url_field": "url",
        "rules": "它读 .github/copilot-instructions.md 与 AGENTS.md（项目级）",
        "rule_hint": "想让 Copilot CLI 主动去查，把规则写进项目的 .github/copilot-instructions.md",
        "manual": "跑 `copilot mcp list` 复核（VS Code 里的 Copilot 是另一份配置，键名是 `servers`）",
    },
    "opencode": {
        "label": "OpenCode",
        "detect": ".config/opencode",
        "config": (".config", "opencode", "opencode.json"),
        "container": "mcp",
        "url_field": "url",
        "rules": "它读 AGENTS.md（项目根与 ~/.config/opencode/AGENTS.md）",
        "rule_hint": "想让 OpenCode 主动去查，把规则块加进项目的 AGENTS.md",
        "manual": "重启 OpenCode 后看它的 MCP 列表；若你设了 XDG_CONFIG_HOME，它读的是 "
                  "$XDG_CONFIG_HOME/opencode/opencode.json，把同样的条目贴过去即可",
        "parse_note": "opencode.jsonc 允许注释，若你用的正是它，本安装器解析不了",
    },
    "kiro": {
        "label": "Kiro",
        "detect": ".kiro",
        "config": (".kiro", "settings", "mcp.json"),
        "container": "mcpServers",
        "url_field": "url",
        "rules": "它读 .kiro/steering/*.md（steering 文件）",
        "rule_hint": "想让 Kiro 主动去查，把规则加进 .kiro/steering/",
        "manual": "重启 Kiro 后用它的 MCP 面板复核 misakanet（Kiro 还支持 disabled / autoApprove）",
    },
}


def _mcp_only_config(home: Path, agent: str) -> Path:
    return home.joinpath(*MCP_ONLY_TARGETS[agent]["config"])


# Same shape the register path and the npm installer accept. It ends up inside a TOML inline table,
# a YAML mapping and JSON, so a value that is not id-shaped is not a hint worth writing — it is noise
# that could close a quote or open a new table (#1859, and the reason the JS side has this regex).
CLIENT_ID_SHAPE = re.compile(r"^[A-Za-z0-9._-]{8,64}$")

# Node's vocabulary for the same machines, because `X-MisakaNet-Os` is one column in one table and
# the npm installer writes it as `process.platform/process.arch`. `linux/x64` and `linux/x86_64` are
# one machine spelled twice; a column with two dialects does not aggregate, and the D1 check that
# confirmed this (#1820) would have silently under-counted one of the two channels.
_OS_ALIASES = {
    "x86_64": "x64", "amd64": "x64", "aarch64": "arm64", "i386": "ia32", "i686": "ia32",
    "armv7l": "arm", "armv6l": "arm", "ppc64le": "ppc64", "ppc64": "ppc64",
}


def _os_hint() -> str:
    import platform

    system = platform.system().lower() or "unknown"
    machine = platform.machine().lower()
    return f"{system}/{_OS_ALIASES.get(machine, machine)}"[:40]


def _declared_client_id(home: Path) -> str:
    """The stable pseudonym to declare, or '' when this machine has not said."""
    path = _state_dir(home) / "client_id"
    try:
        found = path.read_text(encoding="utf-8").strip() if path.exists() else ""
    except OSError:
        return ""
    return found if CLIENT_ID_SHAPE.match(found) else ""


def _installer_version() -> str:
    """The version of the checkout this script ran from, or '' when it is not running from one.

    The bootstrap route (`curl … bootstrap.sh | bash`) downloads this file into
    `~/.misakanet-agent` and fetches everything from `main`, so there is no version to report — and
    inventing one would put a number in the analytics row that nothing maintains, which is exactly
    the defect #1820 was about. A clone has `pyproject.toml` two directories up; the mtime of a
    downloaded file is not a version either, so it is not used.
    """
    try:
        text = (HERE.parent.parent / "pyproject.toml").read_text(encoding="utf-8")
    except OSError:
        return ""
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.M)
    return match.group(1) if match else ""


# Same shape the server accepts for a referral code, and the same rule the client writes with
# (`scripts/referral.py`). A file another process wrote decides what leaves this machine, so it is
# checked here rather than trusted (#1996).
REFERRAL_SHAPE = re.compile(r"^[A-Za-z0-9]{4,16}$")


def _declared_referral(home: Path) -> str:
    """The code of the node that invited this one, or '' when this machine has not said.

    Recorded by `python3 scripts/referral.py --apply=CODE` into `~/.misakanet-agent/referral_code`,
    which every client on the machine can read. It is sent once, at registration: the server counts a
    new node against that code, so the invitation finally exists somewhere other than the inviting
    machine's git history (#1996) — and renewing the same node never counts twice.
    """
    path = _state_dir(home) / "referral_code"
    try:
        found = path.read_text(encoding="utf-8").strip() if path.exists() else ""
    except OSError:
        return ""
    return found if REFERRAL_SHAPE.match(found) else ""


def _context_headers(agent: str, home: Path) -> dict:
    """The self-declared hint headers that accompany the credential on every MCP entry we write.

    `Authorization` is a credential; these are hints the service records on its analytics row
    (`agent`, `os`, `client_version`, and a stable pseudonym), never identity — AGENTS.md §3.3 is
    why writing them automatically is acceptable at all. The npm installer has written them since
    0.5.6 (#1859); this one did not, so every user who arrived through the bootstrap route — the
    route for machines where npm is not an option — was invisible in the client statistics that
    decide which clients get worked on next.

    Same four names as the JS side, because both feed the same worker fields: `workers/*.js` reads
    `X-MisakaNet-Agent` / `-Os` / `-Version` (truncating each to 40) and `X-MisakaNet-Client`.
    """
    headers = {"X-MisakaNet-Agent": agent, "X-MisakaNet-Os": _os_hint()}
    client_id = _declared_client_id(home)
    if client_id:
        headers["X-MisakaNet-Client"] = client_id
    version = _installer_version()
    if version:
        headers["X-MisakaNet-Version"] = version
    return headers


def _mcp_only_entry(agent: str, token: str, home: Path) -> dict:
    """The vendor's own remote shape, plus the Bearer header when there is a token."""
    entry: dict = {}
    if agent == "gemini":
        entry["httpUrl"] = ENDPOINT
    elif agent == "copilot":
        entry["type"] = "http"
        entry["url"] = ENDPOINT
    elif agent == "opencode":
        entry["type"] = "remote"
        entry["url"] = ENDPOINT
        entry["enabled"] = True
    else:                                    # cursor, kiro
        entry["url"] = ENDPOINT
    headers = _context_headers(agent, home)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    entry["headers"] = headers
    return entry


def install_mcp_only(home: Path, dry: bool, rep: Report, agent: str) -> None:
    """Install one MCP-only target: merge our entry under the vendor's key path, write, say what it is not."""
    spec = MCP_ONLY_TARGETS[agent]
    cfg = _mcp_only_config(home, agent)
    data: dict = {}
    if cfg.exists():
        try:
            data = json.loads(cfg.read_text(encoding="utf-8"))
        except Exception:
            note = f"（{spec['parse_note']}）" if spec.get("parse_note") else ""
            rep.needs_manual(f"{spec['label']}: {cfg} 不是合法 JSON{note} → "
                             f"手动加入 {spec['container']}.misakanet")
            return
    container = data.setdefault(spec["container"], {})
    entry = _mcp_only_entry(agent, _read_token(home), home)
    if container.get("misakanet") == entry:
        rep.ok(f"{spec['label']}: MCP 已注册（无改动）")
    else:
        container["misakanet"] = entry
        backup(cfg, dry)
        write_text(cfg, json.dumps(data, indent=2, ensure_ascii=False) + "\n", dry)
        rep.ok(f"{spec['label']}: {'会写入 MCP 条目' if dry else '注册 MCP（streamable-http）'} → {cfg}")
    rep.skip(f"{spec['label']}: 没有规则块与钩子（{spec['rules']}）→ {spec['rule_hint']}")
    rep.needs_manual(f"{spec['label']}: {spec['manual']}")


def detect(home: Path, agent: str) -> bool:
    checks = {
        # cc-haha / claude-haha is a Claude Code fork that reads ~/.claude (its adapters
        # README points at ~/.claude/adapters.json and it honours CLAUDE_CONFIG_DIR), so a
        # ~/cc-haha checkout counts as evidence that the claude target applies to it too.
        "claude": [home / ".claude", home / ".claude.json", home / "cc-haha"],
        "codex": [home / ".codex"],
        "hermes": [home / ".hermes"],
        "openclaw": [home / ".openclaw"],
        "codewhale": [home / ".codewhale"],
        **{a: [home / s["detect"]] for a, s in MCP_ONLY_TARGETS.items()},
        "dsh": [home / ".dsh", home / ".agents"],
    }
    return any(p.exists() for p in checks[agent])


def mcp_server_entry(token: str = "", home: Path | None = None) -> dict:
    """Claude Code / generic JSON shape for a streamable-HTTP MCP server.

    With a token the entry also carries the credential, which is what unlocks the write tools.
    Reads stopped being metered on 2026-09-18 (anonymous reads are unlimited; only a burst guard
    remains), so a token is no longer the difference between "works" and "quota exceeded" — the
    text here said "5/day/IP" until 2026-09-20, two days after the policy changed in AGENTS.md.
    """
    entry: dict = {"type": "http", "url": ENDPOINT}
    headers = _context_headers("claude-code", home or Path.home())
    if token:
        headers["Authorization"] = f"Bearer {token}"
    entry["headers"] = headers
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
    entry = mcp_server_entry(_read_token(home), home)
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
    permissions = settings.setdefault("permissions", {})
    allow = permissions.get("allow")
    if not isinstance(allow, list):
        # A hand-written settings.json can hold `"allow": "all"` (or any non-list). `.append` on
        # that raised AttributeError *after* the MCP entry had already been written, leaving a
        # half-configured install; the JS installer already guards with Array.isArray, so this is
        # the Python half of the same guard. The odd value is preserved as an entry rather than
        # dropped, so nothing the user wrote disappears (open-code-review finding 22).
        allow = [allow] if isinstance(allow, str) and allow else []
        permissions["allow"] = allow
    for tool in CLAUDE_ALLOWED_TOOLS:
        if tool not in allow:
            allow.append(tool)
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


def codex_table(token: str = "", home: Path | None = None) -> str:
    """Codex MCP table. Token goes in `http_headers` rather than `bearer_token_env_var`:
    an env var has to be exported by the user's shell (which this user will not do), while
    the header is written once and used by Codex itself.

    The hint headers ride in the same inline table. Every value is shape-checked before it is
    written (`_context_headers` only emits a `client_id` that matches `CLIENT_ID_SHAPE`), because a
    TOML inline table closed early by a quote takes the whole file with it — the npm installer hit
    exactly that with a corrupt `client_id` file (#1859).
    """
    headers = _context_headers("codex", home or Path.home())
    if token:
        headers["Authorization"] = f"Bearer {token}"
    pairs = ", ".join(f'{key} = "{value}"' for key, value in headers.items())
    lines = [
        "[mcp_servers.misakanet]",
        'type = "streamable-http"',
        f'url = "{ENDPOINT}"',
        f"http_headers = {{ {pairs} }}",
    ]
    if not token:
        lines.append("# 上面只有自报的上下文提示头（agent/os/版本），不含凭据：读不需要 token"
                     "（2026-09-18 起匿名读不限次数），拿到 token 后可回填 Authorization。")
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
    table_block = f"# {START}\n{codex_table(_read_token(home), home)}# {END}\n"
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
    # Verified on codex-cli 0.154.0 (2026-09-15) — see the JS installer for the same
    # note: `codex mcp list` shows misakanet enabled with the Bearer token, `codex
    # doctor` reports config.toml parse ok + 1 streamable_http server + 0 disabled, and
    # `codex debug prompt-input` renders a `# AGENTS.md instructions` item carrying this
    # rule block. The part that stays open is the hook: 0.154.0's lifecycle hooks are
    # admin-managed (requirements.toml), so the checkpoint is rule-driven.
    rep.ok("Codex: 注册已核对（`codex mcp list` / `codex doctor` / `codex debug prompt-input`）")
    rep.needs_manual(
        "Codex: 没有用户级 lifecycle hook → 检查点靠规则块里的「约 20 轮」自律触发；"
        "要硬保证就配外层 wrapper 在每轮后跑 checkpoint_reminder.py")


def codewhale_projects(home: Path) -> list[Path]:
    """Trusted project directories, read from codewhale's own config.toml.

    codewhale reads a workspace ``AGENTS.md`` only for a *trusted* project, and it has no
    user-level rules file we could confirm on 0.9.7 — so the block goes into the directories
    the user actually works in. The parse is deliberately tiny: ``[projects."<dir>"]``
    followed by ``trust_level = "trusted"``.
    """
    cfg = home / ".codewhale" / "config.toml"
    try:
        text = cfg.read_text(encoding="utf-8")
    except OSError:
        return []
    out: list[Path] = []
    current = None
    for line in text.splitlines():
        header = re.match(r'^\s*\[projects\.(.+?)\]\s*$', line)
        if header:
            current = header.group(1).strip().strip('"')
            continue
        if re.match(r'^\s*\[', line):
            current = None
            continue
        if current and re.match(r'^\s*trust_level\s*=\s*"trusted"', line):
            out.append(Path(current))
    return out


def install_codewhale(home: Path, dry: bool, rep: Report) -> None:
    """codewhale: MCP in `~/.codewhale/mcp.json`, rules in its trusted project dirs.

    Written file-to-file like the other targets (no subprocess), and the token is the one
    thing codewhale will not take inline: ``bearer_token_env_var`` names an environment
    variable, so this target ends with one action for the user rather than pretending to be
    fully automatic.
    """
    cfg = home / ".codewhale" / "mcp.json"
    try:
        data = json.loads(cfg.read_text(encoding="utf-8"))
    except Exception:
        data = {"timeouts": {"connect_timeout": 10, "execute_timeout": 60, "read_timeout": 120},
                "servers": {}}
    servers = data.setdefault("servers", {})
    entry = {
        "command": None, "args": [], "env": {}, "url": ENDPOINT,
        "connect_timeout": None, "execute_timeout": None, "read_timeout": None,
        "disabled": False, "enabled": True, "required": False,
        "enabled_tools": [], "disabled_tools": [],
        "bearer_token_env_var": "MISAKANET_TOKEN",
    }
    if servers.get("misakanet") == entry:
        rep.ok("codewhale: MCP 已注册（无改动）")
    else:
        servers["misakanet"] = entry
        backup(cfg, dry)
        write_text(cfg, json.dumps(data, indent=2, ensure_ascii=False) + "\n", dry)
        rep.ok(f"codewhale: {'会写入 MCP 条目' if dry else '注册 MCP（streamable-http）'} → {cfg}")

    projects = [d for d in codewhale_projects(home) if d.is_dir()]
    for project in projects:
        status = inject_block(project / "AGENTS.md", prompt_block(), dry)
        rep.ok(f"codewhale: 规则块 {status} → {project / 'AGENTS.md'}")
    if not projects:
        rep.needs_manual("codewhale: 没有受信任的项目目录（config.toml 里没有 trust_level = \"trusted\"）"
                         "→ 先在 codewhale 里打开并信任一次你的项目，再运行本命令")
    rep.needs_manual("codewhale: token 只能通过环境变量给 → 在 shell 配置里加 "
                     "`export MISAKANET_TOKEN=<你的 token>`，否则工具会连不上")


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


def _mcp_request(endpoint: str, method: str, params: dict, token: str = "",
                 timeout: float = 6.0) -> dict:
    """One MCP request over streamable HTTP. Returns {} on any failure (offline is fine).

    Three response shapes are in play: `structuredContent` (this worker's tools/call),
    `content[0].text` (the MCP spec's text block), and plain fields (initialize, tools/list).
    The first version assumed the second and raised on the third, and the blanket `except`
    turned that into `{}` — a working endpoint reported as unreachable (fixed 2026-09-15,
    same defect the JS installer had).
    """
    endpoint, token = _trusted_target(endpoint, token)
    import urllib.error
    import urllib.request

    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode("utf-8")
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
        if "structuredContent" in result:
            return result["structuredContent"]
        content = result.get("content")
        if isinstance(content, list) and content and isinstance(content[0], dict) \
                and isinstance(content[0].get("text"), str):
            try:
                return json.loads(content[0]["text"])
            except ValueError:
                return result
        return result
    except Exception:
        return {}


def _post(endpoint: str, tool: str, arguments: dict, token: str = "", timeout: float = 6.0) -> dict:
    """One tools/call (registration is the only one this installer makes; it is not a read)."""
    return _mcp_request(endpoint, "tools/call", {"name": tool, "arguments": arguments},
                        token=token, timeout=timeout)


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

    payload = {"agent_type": "setup", "client_id": client_id}
    referral = _declared_referral(home)
    if referral:
        payload["referral_code"] = referral
    result = _post(endpoint, "misakanet_register", payload)
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
    # Handshake, not a search: `tools/list` proves the endpoint speaks MCP and answers, and it
    # spends none of the anonymous read quota. The search used to be the probe, which cost one of
    # the five free reads per run and — because the endpoint answers a spent quota with HTTP 200
    # and an error *inside* the result — made a working install look broken (2026-09-15).
    probe = _mcp_request(endpoint, "tools/list", {}, timeout=6.0)
    tools = probe.get("tools") if isinstance(probe, dict) else None
    if isinstance(tools, list) and tools:
        rep.ok(f"端点可达：{endpoint}（MCP 握手成功，{len(tools)} 个工具）")
    elif probe:
        ok = False
        rep.needs_manual(f"端点可达但握手异常：{json.dumps(probe, ensure_ascii=False)[:120]}")
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
        if agent in MCP_ONLY_TARGETS:
            # The MCP-only targets are one JSON file each, reported only when the user has them.
            # Whether the client has *loaded* that file is not knowable from here, and the line says
            # so instead of implying it.
            spec = MCP_ONLY_TARGETS[agent]
            cfg = _mcp_only_config(home, agent)
            data = {}
            if cfg.exists():
                try:
                    data = json.loads(cfg.read_text(encoding="utf-8"))
                except Exception:
                    data = {}
            entry = (data.get(spec["container"]) or {}).get("misakanet")
            ok &= bool(entry)
            (rep.ok if entry else rep.needs_manual)(
                f"{spec['label']}: MCP 注册 {'✓' if entry else '✗ 缺失'}（{cfg}）")
        rules = {"codex": home / ".codex" / "AGENTS.md", "hermes": home / ".hermes" / "SOUL.md",
                 "dsh": home / ".agents" / "skills" / "misakanet" / "SKILL.md"}.get(agent)
        if agent == "codewhale":
            whale_dirs = [d for d in codewhale_projects(home) if d.is_dir()]
            rules = (whale_dirs[0] / "AGENTS.md") if whale_dirs else None
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


def openclaw_workspaces(home: Path) -> list[Path]:
    """Where OpenClaw keeps its rules file — decided by its own config, not by a path we assumed.

    `~/.openclaw/workspace` is only right when nothing else is configured: the real answer is
    `agents.defaults.workspace` in ~/.openclaw/openclaw.json. Writing to the guessed path still
    looked like success while the agent never read it: the tools were registered and nothing told
    the model to use them (measured on this machine 2026-09-15, issue #1719). Both candidates are
    returned, configured first, so install writes where the agent reads and uninstall can take
    back a block written by either version.
    """
    paths: list[Path] = []
    cfg = home / ".openclaw" / "openclaw.json"
    try:
        configured = (json.loads(cfg.read_text(encoding="utf-8"))
                      .get("agents", {}).get("defaults", {}).get("workspace"))
    except Exception:
        configured = None
    if isinstance(configured, str) and configured.strip():
        candidate = Path(configured.strip())
        if candidate.is_dir():
            paths.append(candidate)
    paths.append(home / ".openclaw" / "workspace")
    return paths


def install_openclaw(home: Path, dry: bool, rep: Report) -> None:
    """OpenClaw: rules in the workspace its config names, MCP servers in `mcp.servers`.

    Written file-to-file rather than through `openclaw mcp add`: the CLI puts the token in argv,
    which every process on the machine can read (the shape the plugin scanner reports as shell
    injection), and it needs its own database writable. The manual CLI line is still printed for
    whoever prefers it — as text, never executed.
    """
    workspace = openclaw_workspaces(home)[0]
    rules = workspace / "AGENTS.md"
    if not workspace.is_dir():
        rep.needs_manual(f"OpenClaw: 找不到 workspace（{workspace}）→ 先运行一次 openclaw 生成它")
    else:
        status = inject_block(rules, prompt_block(), dry)
        rep.ok(f"OpenClaw: 规则块 {status} → {rules}")

    cfg = home / ".openclaw" / "openclaw.json"
    try:
        data = json.loads(cfg.read_text(encoding="utf-8"))
        servers = data.setdefault("mcp", {}).setdefault("servers", {})
    except Exception:
        rep.needs_manual(f"OpenClaw: 读不到或解析不了 {cfg} → 先运行一次 openclaw 生成配置，"
                         f"或手动执行 `openclaw mcp add misakanet --url {ENDPOINT} "
                         "--transport streamable-http`")
        return

    token = _read_token(home)
    headers = _context_headers("openclaw", home)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    entry: dict = {"url": ENDPOINT, "transport": "streamable-http", "headers": headers}
    if servers.get("misakanet") == entry:
        rep.ok("OpenClaw: MCP 已注册（无改动）")
        return
    servers["misakanet"] = entry
    backup(cfg, dry)
    write_text(cfg, json.dumps(data, indent=2, ensure_ascii=False) + "\n", dry)
    rep.ok(f"OpenClaw: {'会写入 MCP 条目' if dry else '注册 MCP（streamable-http）'} → {cfg}")


INSTALLERS = {
    "claude": install_claude,
    "codex": install_codex,
    "hermes": install_hermes,
    "openclaw": install_openclaw,
    "codewhale": install_codewhale,
    **{a: partial(install_mcp_only, agent=a) for a in MCP_ONLY_TARGETS},
    "dsh": install_dsh,
}


def uninstall(home: Path, dry: bool, rep: Report) -> None:
    targets = [
        *[d / "AGENTS.md" for d in codewhale_projects(home) if d.is_dir()],
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
    whale_cfg = home / ".codewhale" / "mcp.json"
    if whale_cfg.exists():
        try:
            whale = json.loads(whale_cfg.read_text(encoding="utf-8"))
            if whale.get("servers", {}).pop("misakanet", None) is not None:
                backup(whale_cfg, dry)
                write_text(whale_cfg, json.dumps(whale, indent=2, ensure_ascii=False) + "\n", dry)
                rep.ok(f"移除 MCP 注册 → {whale_cfg}")
        except Exception:
            rep.needs_manual(f"{whale_cfg} 解析失败 → 手动删除 servers.misakanet")
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
    for agent, spec in MCP_ONLY_TARGETS.items():
        cfg = _mcp_only_config(home, agent)
        if not cfg.exists():
            continue
        try:
            data = json.loads(cfg.read_text(encoding="utf-8"))
            if (data.get(spec["container"]) or {}).pop("misakanet", None) is not None:
                backup(cfg, dry)
                write_text(cfg, json.dumps(data, indent=2, ensure_ascii=False) + "\n", dry)
                rep.ok(f"移除 MCP 注册 → {cfg}")
        except Exception:
            rep.needs_manual(f"{cfg} 解析失败 → 手动删除 {spec['container']}.misakanet")
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
            # Give back the read-tool grants too, so uninstall leaves the file as it was (the JS
            # installer does the same; a parity test asserts both directions).
            permissions = settings.get("permissions") or {}
            allow = permissions.get("allow")
            if isinstance(allow, list):
                pruned = [tool for tool in allow if tool not in CLAUDE_ALLOWED_TOOLS]
                if len(pruned) != len(allow):
                    permissions["allow"] = pruned
                    settings["permissions"] = permissions
                    changed = True
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
    # OpenClaw: the rules may sit in the workspace its config names, and the MCP entry is one we
    # wrote ourselves, so both can be taken back (issue #1719).
    for workspace in openclaw_workspaces(home):
        rules = workspace / "AGENTS.md"
        if strip_block(rules, dry):
            rep.ok(f"移除规则块 → {rules}")
        # Same rule as the targets above: a file that existed only for our block should go.
        if rules.exists() and not rules.read_text(encoding="utf-8").strip():
            if not dry:
                rules.unlink()
            rep.ok(f"删除只剩空白的规则文件 → {rules}")
    oc_cfg = home / ".openclaw" / "openclaw.json"
    if oc_cfg.exists():
        try:
            data = json.loads(oc_cfg.read_text(encoding="utf-8"))
            servers = data.get("mcp", {}).get("servers", {}) or {}
            if servers.pop("misakanet", None) is not None:
                backup(oc_cfg, dry)
                write_text(oc_cfg, json.dumps(data, indent=2, ensure_ascii=False) + "\n", dry)
                rep.ok(f"移除 MCP 注册 → {oc_cfg}")
        except Exception:
            rep.needs_manual(f"{oc_cfg} 解析失败 → 手动删除 mcp.servers.misakanet")
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
        print("\n结论：" + (f"READY —— 直接开一个新会话测试即可（问它 {ONBOARDING_QUERIES[0]}）"
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
        f"  「{ONBOARDING_QUERIES[0]}」/「{ONBOARDING_QUERIES[1]}」/「{ONBOARDING_QUERIES[2]}」→ 看它是否调用 misakanet_search\n"
        f"  手动跑一次检查点：echo '{{\"session_id\":\"t\"}}' | python3 \"{HOOK_FILE}\" prompt\n"
        f"  手动跑一次失败提醒：echo '{{\"error\":\"exit code 137\"}}' | python3 \"{HOOK_FILE}\" failure\n"
        "回滚：python3 install_misakanet_agent.py --uninstall（或从 *.misakanet.bak 恢复）"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
