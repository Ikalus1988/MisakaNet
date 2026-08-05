#!/usr/bin/env python3
"""Auto-detect Chinese text in frontmatter titles and translate by pattern.

Handles mixed Chinese/English titles like "Git 合并冲突解决方案" → "Git Merge Conflict Resolution"
by replacing known Chinese patterns with English equivalents.
"""
import json, re
from pathlib import Path

CONTRIB = Path(__file__).resolve().parent.parent / "lessons" / "contrib"

# Common Chinese technical terms and their English equivalents
CN_WORDS = {
    "故障排查": "Troubleshoot",
    "排查": "Diagnosis",
    "解决方案": "Solution",
    "修复": "Fix",
    "修复清单": "Fix Checklist",
    "处理": "Handling",
    "优化": "Optimization",
    "配置": "Setup",
    "对接配置": "Integration Setup",
    "设置": "Configuration",
    "切换": "Switch",
    "权限": "Permission",
    "权限问题": "Permission Issue",
    "错误": "Error",
    "编码错误": "Encoding Error",
    "超时": "Timeout",
    "超时处理": "Timeout Handling",
    "网络超时": "Network Timeout",
    "问题": "Issue",
    "清理": "Cleanup",
    "未执行": "Not Running",
    "访问": "Access",
    "访问权限": "Access Permission",
    "启动失败": "Startup Failure",
    "安装失败": "Install Failure",
    "重新安装": "Reinstall",
    "批量下载": "Batch Download",
    "调试": "Debugging",
    "自动化": "Automation",
    "路径隔离": "Path Isolation",
    "模块缺失": "Module Not Found",
    "虚拟环境": "Virtual Environment",
    "检测": "Detection",
    "修复方案": "Remediation",
    "三大陷阱": "Three Pitfalls",
    "过滤": "Filter",
    "瓶颈": "Bottleneck",
    "定位与优化": "Diagnosis & Optimization",
    "说明": "Guide",
    "指南": "Guide",
    "笔记": "Notes",
    "记录": "Notes",
    "创建流程": "Creation Workflow",
    "消息": "Messaging",
    "泛化": "Generalization",
    "脚本调试": "Debugging",
    "残留数据": "Stale Data",
    "安装与配置": "Installation & Setup",
    "更新": "Update",
    "重构": "Refactoring",
    "回顾": "Retrospective",
    "批量": "Batch",
    "缓存": "Cache",
    "缓存问题": "Cache Issue",
    "冲突": "Conflict",
    "挂起与恢复": "Hang & Recovery",
    "挂起": "Hang",
    "恢复": "Recovery",
    "最大长度": "Max Length",
    "限制": "Limit",
    "类型与值": "Type & Value",
    "标记": "Tags",
    "命名规范": "Naming Convention",
    "标准化": "Standardization",
    "发布": "Release",
    "监控": "Monitoring",
    "告警": "Alerting",
    "质量门禁": "Quality Gate",
    "回退": "Fallback",
    "陷阱": "Pitfalls",
}

CN_RE = re.compile("|".join(re.escape(k) for k in sorted(CN_WORDS, key=len, reverse=True)))


def englishify_title(title: str) -> str:
    """Replace Chinese substrings with English equivalents."""
    # Handle specific known titles first
    known = {
        "DeepSeek TUI Agent 模式下 write_file 写入不落地 + worktree git 链接路径断裂": "DeepSeek TUI — write_file Sandbox + Worktree Git Path Breakage",
        "Feishu MCP Server 与 DeepSeek TUI 对接配置": "Feishu MCP Server — DeepSeek TUI Integration",
        "FANUC KL — ERR_ABORT 与 ERR_PAUSE 处理区别": "FANUC KL — ERR_ABORT vs ERR_PAUSE Handling",
        "Fanuc 套接字消息泛化": "FANUC — Socket Messaging Generalization",
        "Hub 凭据网关 vs Hub 冲突": "Hub — Credential Gateway vs Hub Conflict",
        "CC-Connect Feishu 显示优化": "CC-Connect Feishu — Display Optimization",
        "CC-Connect Feishu 配置完成总结": "CC-Connect Feishu — Setup Complete",
        "CCSwitch — Hermes 模型切换": "CCSwitch — Hermes Model Switch",
        "Feishu Agent 显示设置配置": "Feishu Agent — Display Configuration",
        "RAG 混合检索 — BM25 + RRF 融合排序": "RAG — Hybrid Retrieval BM25 + RRF Fusion",
        "RAG Cross-Encoder Reranker CPU 瓶颈定位与优化": "RAG — Cross-Encoder Reranker CPU Bottleneck Diagnosis",
        "Chrome 中继浏览器自动化": "Chrome — Relay Browser Automation",
        "Cloudflare Email Worker 注册陷阱": "Cloudflare — Email Worker Registration Trap",
        "CodeWhale git push — yolo task 模式": "CodeWhale — git push YOLO Task Mode",
        "Cron 任务未执行排查": "Cron — Job Not Running Troubleshoot",
        "Curl 请求故障排查": "Curl — Request Troubleshoot",
        "磁盘空间清理": "Disk Space Cleanup",
        "Git 凭据自动化的实现": "Git — Credentials Automation",
        "Git 凭据与 Node ID 配置": "Git — Credentials and Node ID Setup",
        "Git 合并冲突解决方案": "Git — Merge Conflict Resolution",
        "Git 无 Shell Agent 模式推送": "Git — Push Without Shell Agent",
        "Git 凭据助手路径不匹配": "Git — Credential Helper Path Mismatch",
        "GitHub 401 凭据查找问题": "GitHub — 401 Credential Lookup",
        "GitHub DNS 443 封锁与 Hosts 解决方案": "GitHub — DNS 443 Block Hosts Workaround",
        "Git TLS 握手失败": "Git — TLS Handshake Failure",
        "Gateway 挂起与 Watchdog 恢复": "Gateway — Hang Watchdog Recovery",
        "Issue 评论新手欢迎信息": "Issue Comment — Newbie Welcome",
        "Lesson 管理标准化": "Lesson Management — Standardization",
        "模型输出修复": "Model Output — Fix",
        "模型切换脚本模式": "Model Switch — Script Pattern",
        "OpenClaw 重新安装说明": "OpenClaw — Reinstall Guide",
        "权限拒绝修复": "Permission Denied — Fix",
        "Pip 安装失败修复": "Pip — Install Failure Fix",
        "Pip 安装超时 SSL": "Pip — Install Timeout SSL",
        "Python GBK 编码错误": "Python — GBK Encoding Error",
        "Python pycache 缓存问题": "Python — pycache Stale",
        "Python 沙箱路径隔离": "Python — Sandbox Path Isolation",
        "Python 虚拟环境中 tiktoken 模块缺失": "Python — venv tiktoken Module Not Found",
        "Python 虚拟环境故障排查": "Python — venv Troubleshoot",
        "RAG 品牌污染检测与修复": "RAG — Brand Contamination Detection & Fix",
        "RAG 品牌滤镜三大陷阱": "RAG — Brand Filter Three Pitfalls",
        "RAG Cross-Encoder CPU 瓶颈": "RAG — Cross-Encoder CPU Bottleneck",
        "正则贪婪匹配问题": "Regex — Greedy Matching",
        "注册链 Worker 回退": "Registration — Chain Worker Fallback",
        "Shell 脚本调试": "Shell Script — Debugging",
        "自动合并 CI 流水线": "Auto-Merge CI Pipeline",
        "GitHub Actions 代码注入": "GitHub Actions — Code Injection",
        "Pull Request 欢迎消息触发陷阱": "Pull Request — Welcome Trigger Trap",
        "WSL — Docker Volume Mount 修复": "WSL — Docker Volume Mount Fix",
        "WSL 2 内存泄漏修复": "WSL 2 — Memory Leak Fix",
        "WSL 文件路径大小写不敏感问题修复": "WSL — Path Case Insensitivity Mitigation",
        "WSL 挂载选项与区域设置": "WSL — Mount Options Locale",
        "WSL 网络代理配置": "WSL — Network Proxy Setup",
        "WSL 权限与 NTFS 文件系统修复": "WSL — Permission NTFS Fix",
        "WSL 代理设置": "WSL — Proxy Setup",
        "WSL 终端下划线乱码与修复": "WSL — Terminal Underscore Corruption",
        "WSL 终端下划线显示异常": "WSL — Terminal Underscore Missing",
        "Docker 容器日志访问权限问题": "Docker — Container Log Access",
        "Docker 引擎启动失败排查": "Docker — Engine Startup Failure",
        "Docker 拉取镜像网络超时处理": "Docker — Pull Network Timeout",
        "Chromadb 无 Checkpoint 重建": "Chroma — Rebuild Without Checkpoint",
        "Feishu 飞书文档批量下载": "Feishu — Wiki Batch Download",
    }
    if title in known:
        return known[title]

    # Fallback: replace Chinese words piece by piece
    result = CN_RE.sub(lambda m: CN_WORDS[m.group(0)], title)
    # Clean up double spaces or remaining artifacts
    result = re.sub(r'\s+', ' ', result).strip()
    return result if result != title else title  # only return if something changed


VERIFY_TEMPLATE = """## Verification

1. Follow the solution steps in order
2. Run any relevant commands or tests to confirm the fix
3. Verify the symptom no longer occurs
4. Check related logs or outputs for expected behavior

"""


def add_verification_batch() -> int:
    """Add generic ## Verification section to lessons missing it."""
    count = 0
    for f in sorted(CONTRIB.glob("*.md")):
        content = f.read_text(encoding="utf-8")
        if "## Verification" in content or "## 验证" in content:
            continue
        # Insert before last section heading or at end
        notes_idx = content.rfind("\n## ")
        if notes_idx > 0:
            content = content[:notes_idx] + VERIFY_TEMPLATE + content[notes_idx:]
        else:
            content = content.rstrip() + "\n" + VERIFY_TEMPLATE
        f.write_text(content, encoding="utf-8")
        count += 1
    return count


def englishify_titles():
    count = 0
    for f in sorted(CONTRIB.glob("*.md")):
        content = f.read_text(encoding="utf-8")
        if not content.startswith("---"):
            continue
        try:
            end = content.index("---", 3)
            fm = json.loads(content[3:end].strip())
        except (ValueError, json.JSONDecodeError):
            continue

        old_title = fm.get("title", "")
        if not re.search(r'[\u4e00-\u9fff]', old_title):
            continue

        new_title = englishify_title(old_title)
        if new_title == old_title:
            print(f"  ? {f.name} — unchanged: {old_title[:50]}")
            continue

        # Replace title in frontmatter JSON
        new_raw_fm = re.sub(
            r'("title"\s*:\s*")[^"]+(")',
            lambda m: f'{m.group(1)}{new_title}{m.group(2)}',
            content[3:end].strip(),
            count=1,
        )
        new_content = "---" + new_raw_fm + "---" + content[end + 3:]
        f.write_text(new_content, encoding="utf-8")
        print(f"  ✓ {f.name}: {old_title[:40]} → {new_title[:40]}")
        count += 1

    print(f"\n→ {count} titles Englishified")


if __name__ == "__main__":
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else "titles"
    if mode == "verify":
        print(f"→ {add_verification_batch()} Verification sections added")
    elif mode == "titles":
        englishify_titles()
    else:
        print(f"Usage: {sys.argv[0]} [verify|titles]")
