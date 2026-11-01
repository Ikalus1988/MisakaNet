#!/usr/bin/env python3
"""
Tombstone -> Draft Lesson converter

Converts fatal-guard 4-field JSON tombstones into MisakaNet draft lessons.

Input: fatal-guard tombstone JSON (stdin or file)
Output: lessons/drafts/<slug>.md

Usage:
    # From file
    python3 scripts/tombstone_to_draft.py --from-file tombstone.json

    # From stdin (pipe from fatal-guard)
    fatal-guard -- node app.js 2>&1 | python3 scripts/tombstone_to_draft.py --stdin

    # Preview mode (no file written)
    python3 scripts/tombstone_to_draft.py --from-file tombstone.json --dry-run
"""

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def redact_snippet(text: str) -> str:
    """Redact sensitive information from crash snippets.

    Removes: tokens, emails, absolute paths, internal IPs.
    Stdlib only — no external dependencies.
    """
    if not text:
        return text

    # GitHub PATs and API keys (ghp_, sk-, gho_, ghu_, ghs_, ghr_)
    text = re.sub(r'ghp_[A-Za-z0-9]{36}', '[REDACTED_GITHUB_TOKEN]', text)
    text = re.sub(r'sk-[A-Za-z0-9]{20,}', '[REDACTED_API_KEY]', text)
    text = re.sub(r'gh[a-z]_[A-Za-z0-9]{30,}', '[REDACTED_GITHUB_TOKEN]', text)

    # Bearer tokens
    text = re.sub(r'Bearer\s+[A-Za-z0-9_\-\.]{20,}', 'Bearer [REDACTED]', text)
    text = re.sub(r'Authorization:\s*[A-Za-z0-9_\-\.]{20,}', 'Authorization: [REDACTED]', text)

    # Generic long hex/base64 tokens (40+ chars, likely tokens)
    text = re.sub(r'\b[A-Fa-f0-9]{40,}\b', '[REDACTED_HEX]', text)

    # Email addresses
    text = re.sub(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', '[REDACTED_EMAIL]', text)

    # Absolute Windows paths (C:\, D:\, etc.)
    text = re.sub(r'[A-Za-z]:\\[^\s"\'<>|]+', '[REDACTED_PATH]', text)

    # Absolute Linux/macOS paths (/home/, /Users/, /root/, /etc/, /var/, /tmp/)
    text = re.sub(r'/(?:home|Users|root|etc|var|tmp|opt)/[^\s"\'<>|]+', '[REDACTED_PATH]', text)

    # Internal/private IP addresses
    text = re.sub(r'\b192\.168\.\d{1,3}\.\d{1,3}\b', '[REDACTED_IP]', text)
    text = re.sub(r'\b10\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', '[REDACTED_IP]', text)
    text = re.sub(r'\b172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}\b', '[REDACTED_IP]', text)

    return text
DRAFTS_DIR = REPO / "lessons" / "drafts"

# Tombstone protocol fields.
#
# The producers do not agree on one name for the error text: the Python
# sidecar writes `snippet`, the Node fatal-guard payload writes `stackSnippet`
# and `message` (#3645). Both are read, oldest name first, so the error text
# survives the trip into the draft instead of being dropped at the last step.
#
# `exit_code` is optional: the in-process payload reports the error before the
# process has exited, so there is no exit code to report yet.
REQUIRED_FIELDS = {"pid", "timestamp", "reason"}
OPTIONAL_FIELDS = {
    "snippet", "stackSnippet", "message", "signal", "host", "node_id",
    "exit_code", "exitCode", "errorName", "schemaVersion",
}

# Lesson `domain` must come from the canonical vocabulary (data/domains.json) —
# `scripts/lesson_gate.py` rejects anything else, so the old "general" fallback
# made every auto-generated draft fail the gate for a reason that had nothing to
# do with the crash (#3645). First match wins, most specific keyword first.
DOMAIN_RULES: tuple[tuple[str, str], ...] = (
    ("eacces", "security"),
    ("eperm", "security"),
    ("permission denied", "security"),
    ("permission", "security"),
    ("denied", "security"),
    ("forbidden", "security"),
    ("unauthorized", "security"),
    ("certificate", "security"),
    ("wsl", "wsl"),
    ("/mnt/c", "wsl"),
    ("crossmnt", "wsl"),
    ("ntfs", "wsl"),
    ("cannot find module", "nodejs"),
    ("node_modules", "nodejs"),
    ("npm ", "nodejs"),
    ("npx ", "nodejs"),
    ("node:", "nodejs"),
    ("modulenotfounderror", "python"),
    ("importerror", "python"),
    ("syntaxerror", "python"),
    ("traceback", "python"),
    ("django", "python"),
    ("flask", "python"),
    ("pip install", "python"),
    ("docker", "docker"),
    ("kubernetes", "kubernetes"),
    ("k8s", "kubernetes"),
    ("econnrefused", "network"),
    ("connection refused", "network"),
    ("enotfound", "network"),
    ("getaddrinfo", "network"),
    ("dns", "network"),
    ("out of memory", "devops"),
    ("heap out of memory", "devops"),
    ("sigsegv", "devops"),
    ("segfault", "devops"),
    ("timeout", "devops"),
    ("timed out", "devops"),
    ("mcp", "mcp"),
    ("ollama", "llm"),
    ("sqlite", "database"),
    ("cloudflare", "cloudflare-worker"),
    ("pytest", "testing"),
    ("openclaw", "openclaw"),
    ("github", "github"),
    ("git ", "git"),
    ("windows", "windows"),
    ("win32", "windows"),
    ("python", "python"),
)
# A crash nobody can classify is still a runtime problem, and "devops" is a
# canonical topic.
DEFAULT_DOMAIN = "devops"


def _slugify(text: str, max_len: int = 60) -> str:
    """生成文件名友好的 slug。"""
    slug = text.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug[:max_len]


def _canonical_domains() -> frozenset:
    """课程 frontmatter `domain` 的规范词表 (data/domains.json)。"""
    path = REPO / "data" / "domains.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"无法读取规范领域词表 {path}: {exc}") from exc
    return frozenset(str(domain).lower() for domain in data["canonical"])


def _first_text(data: dict, *keys: str) -> str:
    """按顺序取第一个非空字符串字段。"""
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def _error_text(data: dict) -> str:
    """墓碑里的错误正文。

    `snippet` 是 Python sidecar 写的完整片段；Node 载荷把它拆成 `message`
    （错误正文）和 `stackSnippet`（调用栈），两个都读，正文在前 (#3645)。
    """
    snippet = _first_text(data, "snippet")
    if snippet:
        return snippet
    parts = [
        text for text in (_first_text(data, "message"), _first_text(data, "stackSnippet"))
        if text
    ]
    return "\n".join(parts)


def _resolve_exit_code(data: dict) -> int:
    """墓碑里的退出码。

    `exit_code` (Python sidecar) 和 `exitCode` 都认；都没有时用信号推出的
    128+N；再没有就按崩溃处理记 1 —— in-process 载荷是在进程退出前发出的，
    那时还没有退出码。
    """
    for key in ("exit_code", "exitCode"):
        value = data.get(key)
        if value is None or value == "":
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    signal = data.get("signal")
    if signal not in (None, ""):
        try:
            return 128 + int(signal)
        except (TypeError, ValueError):
            pass
    return 1


def _parse_tombstone(data: dict) -> dict:
    """验证并规范化墓碑 JSON。"""
    if not isinstance(data, dict):
        raise ValueError("Tombstone JSON 必须是对象 (dict)")
    missing = REQUIRED_FIELDS - set(data.keys())
    if missing:
        raise ValueError(f"Missing required tombstone fields: {missing}")

    snippet = _error_text(data)
    return {
        "pid": int(data["pid"]),
        "timestamp": str(data["timestamp"]),
        "reason": redact_snippet(str(data["reason"])),
        "exit_code": _resolve_exit_code(data),
        "snippet": redact_snippet(snippet[:500]),
        "signal": str(data.get("signal", "")),
        "host": str(data.get("host", "")),
        "node_id": str(data.get("node_id", "unknown")),
    }


def _infer_domain(reason: str, snippet: str = "") -> str:
    """从崩溃原因和错误正文推断领域标签。

    只返回 data/domains.json 规范词表里的值 —— 课程门禁只认这些 (#3645)。
    """
    haystack = f"{reason}\n{snippet}".lower()
    canonical = _canonical_domains()
    for keyword, domain in DOMAIN_RULES:
        if keyword in haystack:
            return domain if domain in canonical else DEFAULT_DOMAIN
    return DEFAULT_DOMAIN


def _generate_ai_hint(tombstone: dict) -> str:
    """生成 AI 诊断盲盒提示 —— 引导新手如何复现和排查。

    基于 reason + snippet 做启发式分析，不需要外部 LLM。
    如果环境变量 MISAKANET_OLLAMA_URL 存在，可调本地 Ollama 生成更丰富的提示。
    """
    reason = tombstone["reason"]
    snippet = tombstone.get("snippet", "")
    exit_code = tombstone["exit_code"]
    domain = _infer_domain(reason, snippet)

    # 尝试 Ollama（极低成本本地调用）
    ollama_url = os.environ.get("MISAKANET_OLLAMA_URL", "")
    if ollama_url:
        try:
            import urllib.request as _req
            prompt = (
                f"你是 MisakaNet 的崩溃诊断助手。以下是一个进程崩溃的墓碑数据，"
                f"请用 1-2 句简洁中文描述可能的根因和复现建议，"
                f"让新手能理解如何参与修复这个 agent task：\n"
                f"reason: {reason}\n"
                f"exit_code: {exit_code}\n"
                f"snippet: {snippet[:300]}\n"
                f"domain: {domain}"
            )
            payload = json.dumps({
                "model": "llama3.2",
                "prompt": prompt,
                "stream": False,
                "options": {"num_predict": 100, "temperature": 0.3},
            }).encode()
            req = _req.Request(
                f"{ollama_url}/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with _req.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read())
                ollama_hint = result.get("response", "").strip()
                if ollama_hint:
                    return ollama_hint
        except Exception:
            pass  # 回退到启发式

    # 启发式诊断（纯标准库）
    hints = []

    # Exit code 常见含义
    exit_hints = {
        1: "通用错误（退出码 1）—— 可能是参数错误、文件不存在、或权限不足",
        2: "语法错误或配置错误（退出码 2）—— 检查配置文件格式",
        126: "命令无法执行（退出码 126）—— 检查文件权限是否为可执行",
        127: "命令未找到（退出码 127）—— 依赖未安装或 PATH 配置有误",
        128: "无效退出参数（退出码 128）",
        130: "被 Ctrl+C 中断（退出码 130）",
        137: "被 SIGKILL 强制终止（退出码 137）—— 可能是 OOM Killer 触发，检查内存使用",
        139: "段错误 SIGSEGV（退出码 139）—— 内存访问越界，检查 native 模块兼容性",
        143: "被 SIGTERM 优雅终止（退出码 143）",
    }
    if exit_code in exit_hints:
        hints.append(exit_hints[exit_code])
    elif exit_code > 128:
        hints.append(f"被信号 {exit_code - 128} 终止 —— 进程异常中断，查看最后几行 stderr 定位")

    # Reason 模式匹配
    reason_lower = reason.lower()
    if "oom" in reason_lower or "memory" in reason_lower or "heap" in reason_lower:
        hints.append("内存溢出（OOM）—— 尝试限制容器内存 或 增大 Node.js --max-old-space-size")
    if "timeout" in reason_lower:
        hints.append("超时类崩溃 —— 可能是网络延迟或死锁，检查上游服务可达性")
    if "permission" in reason_lower or "denied" in reason_lower or "eacces" in reason_lower:
        hints.append("权限不足 —— 检查文件/目录所有权 和 umask 设置")
    if "import" in reason_lower or "module" in reason_lower:
        hints.append("模块导入失败 —— 检查依赖是否安装（pip install / npm install）")
    if "npm" in reason_lower:
        hints.append("npm 相关 —— 尝试清除 node_modules 和 lock 文件后重新安装")
    if "docker" in reason_lower or "container" in reason_lower:
        hints.append("Docker 环境 —— 检查镜像版本、挂载卷权限、和 --init 参数")
    if "wsl" in reason_lower:
        hints.append("WSL 环境 —— 跨文件系统操作时建议将数据放在 ext4 分区而非 NTFS /mnt/c")
    if "chromadb" in reason_lower:
        hints.append("ChromaDB 相关问题 —— 常见于 WSL NTFS 挂载的持久化目录，将 DB 移入 ext4 路径可避免 SQLite 锁冲突")
    if "vite" in reason_lower:
        hints.append("Vite 开发服务器崩溃 —— 检查端口占用 或 node_modules/.vite 缓存目录")
    if "segfault" in reason_lower or "sigsegv" in reason_lower:
        hints.append("段错误 —— 极可能是 native 模块（.node / .so）与当前平台不兼容，检查 node-gyp 编译")

    # Snippet 启发式
    if snippet:
        if "cannot find module" in snippet.lower() or "modulenotfound" in snippet.lower():
            hints.append("缺少依赖模块 —— npm install 或 pip install 对应的包")
        if "eaddrinuse" in snippet.lower():
            hints.append("端口占用 —— 该端口已被其他进程使用，换一个端口或 kill 占用进程")
        if "enospc" in snippet.lower():
            hints.append("磁盘空间不足 —— 清理 /tmp 或 docker system prune")
        if "connection refused" in snippet.lower() or "econnrefused" in snippet.lower():
            hints.append("网络连接被拒绝 —— 目标服务未启动或防火墙拦截")

    if not hints:
        hints.append(f"未知崩溃（{domain} 领域）—— 复现环境后观察 stderr 最后几行，尝试缩小问题范围")

    # 组装为新手指南
    guide = (
        f"🔍 **AI 诊断盲盒提示**\n\n"
        f"| 项目 | 值 |\n|------|-----|\n"
        f"| 退出码 | {exit_code} |\n"
        f"| 推断领域 | {domain} |\n\n"
        f"**复现建议：**\n"
    )
    for i, hint in enumerate(hints, 1):
        guide += f"{i}. {hint}\n"
    guide += (
        f"\n---\n"
        f"💡 **How to contribute:**\n"
        f"- Reproduce: trigger this crash in the same ({domain}) environment\n"
        f"- Write Verification: add an executable `verify_cmd` that confirms the fix\n"
        f"- Credit: merge credit + leaderboard credit + search quota reset\n"
    )
    return guide


def _generate_draft(tombstone: dict, source_file: str = "", ai_hint: str = "") -> str:
    """从验证后的墓碑生成 draft lesson markdown。"""
    now = datetime.now(timezone.utc)
    ts = tombstone["timestamp"]
    reason = tombstone["reason"]
    exit_code = tombstone["exit_code"]
    snippet = tombstone["snippet"]
    domain = _infer_domain(reason, snippet)
    node = tombstone.get("node_id", "unknown")

    # 生成唯一标识
    tombstone_json = json.dumps(tombstone, sort_keys=True, default=str)
    tombstone_hash = hashlib.sha256(tombstone_json.encode()).hexdigest()[:12]

    # 文件名
    slug = _slugify(f"draft-{reason[:40]}-{tombstone_hash}")
    filename = f"{slug}.md"

    # 标题
    title = f"Fix: {reason[:80]}"

    # Frontmatter
    frontmatter = {
        "title": title,
        "domain": domain,
        "tags": ["draft", "auto-generated", "agent-task", f"exit-code-{exit_code}"],
        "status": "draft",
        # A crash report is a report, not a verified fix: E0 says exactly that.
        # The field is required by the lesson gate, and without it every
        # auto-generated draft failed the gate before it was even read (#3645).
        "evidence_level": "E0",
        "source": "fatal-guard",
        "node_id": node,
        "tombstone_hash": tombstone_hash,
        "tombstone_ref": source_file if source_file else f"tombstone:{tombstone_hash}",
        "created": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "crash_timestamp": ts,
    }

    body = f"""---
{json.dumps(frontmatter, ensure_ascii=False, indent=2)}
---

"""
    # AI 诊断盲盒提示（可选）
    if ai_hint:
        body += f"{ai_hint}\n\n---\n\n"

    body += f"""## Problem

进程崩溃，退出码 {exit_code}。

```
{ts} | pid={tombstone['pid']} | reason={reason} | exit_code={exit_code}
```

"""
    if snippet:
        body += f"""### 崩溃现场（错误正文）

```text
{snippet}
```

"""
    body += f"""## Root Cause

<!-- TODO: Agent 需补全根本原因分析 -->
<!-- 原始墓碑数据: {tombstone_json} -->

## Solution

<!-- TODO: Agent 需提供修复方案 -->

## Verification

<!-- TODO: Agent 需添加验证步骤 -->

## Notes

- 由 fatal-guard 自动捕获
- 节点: {node}
- 墓碑哈希: `{tombstone_hash}`
"""

    return filename, body


def main():
    parser = argparse.ArgumentParser(
        description="Tombstone → Draft Lesson 转换器"
    )
    parser.add_argument("--from-file", dest="source_file", help="墓碑 JSON 文件路径")
    parser.add_argument("--stdin", action="store_true", help="从 stdin 读取墓碑 JSON")
    parser.add_argument("--dry-run", action="store_true", help="预览模式，不写文件")
    parser.add_argument("--create-issue", action="store_true",
                        help="Generate issue metadata for this crash")
    parser.add_argument("--ai-hint", action="store_true",
                        help="Generate AI diagnostic hint to guide contributors")
    args = parser.parse_args()

    # 读取输入（来源路径由 `args.source_file` 直接传给 `_generate_draft`，
    # 不再维护一份只写不读的 `source_label`）
    raw_data = None
    if args.source_file:
        with open(args.source_file, "r", encoding="utf-8", errors="replace") as f:
            raw_data = f.read()
    elif args.stdin:
        raw_data = sys.stdin.read()
    else:
        print("错误: 需要 --from-file 或 --stdin", file=sys.stderr)
        sys.exit(1)

    if not raw_data.strip():
        print("错误: 输入为空", file=sys.stderr)
        sys.exit(1)

    # 解析 JSON
    try:
        data = json.loads(raw_data)
    except json.JSONDecodeError:
        # 尝试从混合文本中提取 JSON
        json_match = re.search(r'\{[^{}]*"pid"[^{}]*\}', raw_data)
        if json_match:
            try:
                data = json.loads(json_match.group(0))
            except json.JSONDecodeError:
                print("错误: 无法解析输入为 JSON，也找不到墓碑对象", file=sys.stderr)
                sys.exit(1)
        else:
            print("错误: 无法解析输入为 JSON", file=sys.stderr)
            sys.exit(1)

    # 验证墓碑
    try:
        tombstone = _parse_tombstone(data)
    except ValueError as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)

    # 生成 AI 诊断提示（可选）
    ai_hint = ""
    if args.ai_hint:
        print("  🧠 生成 AI 诊断盲盒提示...", file=sys.stderr)
        ai_hint = _generate_ai_hint(tombstone)
        if ai_hint:
            print(f"  ✅ 提示已生成 ({len(ai_hint)} chars)", file=sys.stderr)

    # 生成 draft
    filename, body = _generate_draft(tombstone, args.source_file, ai_hint)

    if args.dry_run:
        print(f"[DRY RUN] 将生成: {filename}")
        print("=" * 60)
        print(body)
        print("=" * 60)
        return

    # 写入文件
    DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = DRAFTS_DIR / filename
    output_path.write_text(body, encoding="utf-8")
    print(f"draft lesson: {filename}")
    print(f"  domain: {_infer_domain(tombstone['reason'], tombstone['snippet'])}")
    print(f"  reason: {tombstone['reason'][:80]}")
    print(f"  tombstone_hash: {tombstone.get('node_id', '?')}")
    print(f"  -> {output_path}")

    if args.create_issue:
        issue_meta = {
            "title": f"[zero-bounty] Complete root cause: {tombstone['reason'][:60]}",
            "draft_file": f"lessons/drafts/{filename}",
            "tombstone_hash": tombstone.get("tombstone_hash", ""),
            "credit": "merge credit + leaderboard credit",
            "status": "open",
        }
        issue_path = DRAFTS_DIR / f"{Path(filename).stem}.issue.json"
        issue_path.write_text(
            json.dumps(issue_meta, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"  issue: {issue_path}")

    # Next steps
    print()
    print("  Next steps:")
    print(f"  1. Review draft: cat lessons/drafts/{filename}")
    print(f"  2. Fill in Root Cause + Solution + Verification")
    print(f"  3. Submit PR: git add lessons/drafts/ && git commit -s && git push")


if __name__ == "__main__":
    main()
