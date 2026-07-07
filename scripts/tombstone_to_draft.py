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

# 4-field tombstone protocol fields
REQUIRED_FIELDS = {"pid", "timestamp", "reason", "exit_code"}
OPTIONAL_FIELDS = {"snippet", "signal", "host", "node_id"}


def _slugify(text: str, max_len: int = 60) -> str:
    """生成文件名友好的 slug。"""
    slug = text.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug[:max_len]


def _parse_tombstone(data: dict) -> dict:
    """验证并规范化墓碑 JSON。"""
    missing = REQUIRED_FIELDS - set(data.keys())
    if missing:
        raise ValueError(f"Missing required tombstone fields: {missing}")

    return {
        "pid": int(data["pid"]),
        "timestamp": str(data["timestamp"]),
        "reason": redact_snippet(str(data["reason"])),
        "exit_code": int(data["exit_code"]),
        "snippet": redact_snippet(str(data.get("snippet", ""))[:500]),
        "signal": str(data.get("signal", "")),
        "host": str(data.get("host", "")),
        "node_id": str(data.get("node_id", "unknown")),
    }


def _infer_domain(reason: str) -> str:
    """从崩溃原因推断领域标签。"""
    reason_lower = reason.lower()
    domain_map = {
        "node": "javascript",
        "npm": "javascript",
        "vite": "devops",
        "docker": "devops",
        "pip": "python",
        "python": "python",
        "import": "python",
        "module": "python",
        "chromadb": "python",
        "openclaw": "cli",
        "e2b": "cli",
        "git": "devops",
        "permission": "security",
        "denied": "security",
        "timeout": "devops",
        "oom": "devops",
        "memory": "devops",
        "segfault": "devops",
        "signal": "devops",
    }
    for keyword, domain in domain_map.items():
        if keyword in reason_lower:
            return domain
    return "general"


def _generate_ai_hint(tombstone: dict) -> str:
    """生成 AI 诊断盲盒提示 —— 引导新手如何复现和排查。

    基于 reason + snippet 做启发式分析，不需要外部 LLM。
    如果环境变量 MISAKANET_OLLAMA_URL 存在，可调本地 Ollama 生成更丰富的提示。
    """
    reason = tombstone["reason"]
    snippet = tombstone.get("snippet", "")
    exit_code = tombstone["exit_code"]
    domain = _infer_domain(reason)

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

    # 启发式诊断（零依赖）
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
        f"- Reward: merge credit + leaderboard credit + search quota reset\n"
    )
    return guide


def _generate_draft(tombstone: dict, source_file: str = "", ai_hint: str = "") -> str:
    """从验证后的墓碑生成 draft lesson markdown。"""
    now = datetime.now(timezone.utc)
    ts = tombstone["timestamp"]
    reason = tombstone["reason"]
    exit_code = tombstone["exit_code"]
    snippet = tombstone["snippet"]
    domain = _infer_domain(reason)
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
        body += f"""### 崩溃现场（最后 4 行 stderr）

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

    # 读取输入
    raw_data = None
    source_label = ""
    if args.source_file:
        source_label = args.source_file
        with open(args.source_file, "r", encoding="utf-8", errors="replace") as f:
            raw_data = f.read()
    elif args.stdin:
        source_label = "stdin"
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
    print(f"  domain: {_infer_domain(tombstone['reason'])}")
    print(f"  reason: {tombstone['reason'][:80]}")
    print(f"  tombstone_hash: {tombstone.get('node_id', '?')}")
    print(f"  -> {output_path}")

    if args.create_issue:
        issue_meta = {
            "title": f"[zero-bounty] Complete root cause: {tombstone['reason'][:60]}",
            "draft_file": f"lessons/drafts/{filename}",
            "tombstone_hash": tombstone.get("tombstone_hash", ""),
            "reward": "merge credit + leaderboard credit",
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
