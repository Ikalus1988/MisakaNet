#!/usr/bin/env python3
"""
MisakaNet 历史教训批量提取工具 (Phase 1)
=========================================
各节点将加入虫群前的踩坑记录写入 staging/ 目录，
待后续清洗 node 统一去重、冲突检测后入仓。

用法:
  # 创建一个新 lesson 模板
  python3 misakanet/scripts/bulk_import_lessons.py init node1_hermes "RAG 中文乱码修复" \\
    --domain rag-retrieval --tags "project:rag,severity:high"

  # 从 stdin 快速导入
  cat > /tmp/lesson.md
  python3 misakanet/scripts/bulk_import_lessons.py import node6_cloud /tmp/lesson.md

  # 列出 staging 中所有草稿
  python3 misakanet/scripts/bulk_import_lessons.py list

  # 验证 staging 中的所有 lessons 格式
  python3 misakanet/scripts/bulk_import_lessons.py validate

  # 从 session_search 输出快速创建（交互式）
  python3 misakanet/scripts/bulk_import_lessons.py wizard node1_hermes

Schema:
  见 schema 说明：https://github.com/Ikalus1988/MisakaNet
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
STAGING_DIR = PROJECT_ROOT / ".nodes" / "staging"
LESSONS_DIR = PROJECT_ROOT / "lessons"

VALID_NODES = ["node1_hermes", "node2_wsl2", "node3_cc", "node6_cloud"]
VALID_STATUSES = ["published", "draft", "rejected", "deprecated", "superseded", "needs_review"]
VALID_SOURCES = ["bootstrap", "realtime", "opus4.6"]
VALID_REF_TYPES = [
    "iteration-trajectory",   # 迭代轨迹：α→β→γ→δ
    "architecture-decision",  # 架构决策：约束→选择→结果
    "context-mapping",       # 上下文映射：需求→代码→依赖
    "planning-logic",        # 规划逻辑：复杂任务拆解步骤
    "self-correction",       # 代码自修正：标注→修正→说明
]

TEMPLATE = """---
title: {title}
domain: {domain}
subdomain: {subdomain}
source: bootstrap
status: draft
tags: [{tags}]
confidence: 0.7
created: {created}
last_verified:
verified_by:
related:
alternative_of:
---

## 问题

（什么情况下出了什么问题？）

## 根因

（为什么会出现这个问题？）

## 修复

（怎么修复的？具体命令或代码）

## 验证

（怎么确认修好了？）

## 场景

（在什么环境/条件下发生的？）
"""


def _slugify(title: str) -> str:
    """标题 → 文件名"""
    slug = title.lower().strip()
    slug = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", slug)
    return slug.strip("-")[:60]


def _validate_frontmatter(path: Path) -> list[str]:
    """验证单个 lesson 文件 frontmatter，返回错误列表"""
    errors = []
    try:
        content = path.read_text(encoding="utf-8")
    except Exception as e:
        return [f"读取失败: {e}"]

    if not content.startswith("---"):
        return ["缺少 frontmatter (不以 --- 开头)"]

    # 提取 frontmatter
    parts = content.split("---", 2)
    if len(parts) < 3:
        return ["frontmatter 格式错误"]

    raw_fm = parts[1]
    body = parts[2].strip()

    # 简单 yaml 解析（不用 yaml 库，保持无依赖）
    fields = {}
    for line in raw_fm.strip().split("\n"):
        if ":" in line:
            key, _, val = line.partition(":")
            fields[key.strip()] = val.strip().strip('"').strip("'")

    # 必填检查
    required = ["title", "domain", "source", "status", "created"]
    for field in required:
        if field not in fields or not fields[field]:
            errors.append(f"缺少必填字段: {field}")

    # 值域检查
    if fields.get("status") and fields["status"] not in VALID_STATUSES:
        errors.append(f"status 非法: {fields['status']} (允许: {','.join(VALID_STATUSES)})")
    if fields.get("source") and fields["source"] not in VALID_SOURCES:
        errors.append(f"source 非法: {fields['source']} (允许: {','.join(VALID_SOURCES)})")

    # 质量门禁：必须有问题/修复/验证
    has_problem = "## 问题" in body or "## Problem" in body
    has_fix = "## 修复" in body or "## Fix" in body
    has_verification = "## 验证" in body or "## Verification" in body
    missing = []
    if not has_problem:
        missing.append("问题")
    if not has_fix:
        missing.append("修复")
    if not has_verification:
        missing.append("验证")
    if missing:
        cause = f"缺少: {'/'.join(missing)}"
        if fields.get("status") == "published":
            errors.append(f"published 状态但 {cause}")
        elif fields.get("status") != "rejected":
            pass  # draft 允许缺字段

    return errors


def cmd_init(args):
    """创建 lesson 模板"""
    node = args.node
    title = args.title
    domain = args.domain
    subdomain = args.subdomain or ""
    tags_input = args.tags or f"node:{node}"

    # 处理 tags
    tag_list = [t.strip() for t in tags_input.split(",") if t.strip()]
    if not any(t.startswith("node:") for t in tag_list):
        tag_list.insert(0, f"node:{node}")

    tags_str = ", ".join(f'"{t}"' for t in tag_list)

    slug = _slugify(title)
    filename = f"{slug}.md"
    filepath = STAGING_DIR / node / filename

    body = TEMPLATE.format(
        title=title, domain=domain, subdomain=subdomain,
        tags=tags_str, created=datetime.now().strftime("%Y-%m-%d"),
    )

    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_text(body, encoding="utf-8")
    print(f"  ✅ 模板已创建: {filepath}")
    print(f"  编辑后运行: python3 misakanet/scripts/bulk_import_lessons.py validate")


def cmd_import(args):
    """从文件导入 lesson"""
    node = args.node
    src = Path(args.file)
    if not src.exists():
        print(f"  ❌ 文件不存在: {src}", file=sys.stderr)
        sys.exit(1)

    content = src.read_text(encoding="utf-8")
    if not content.startswith("---"):
        print("  ⚠ 文件不以 --- 开头，将包装为模板", file=sys.stderr)
        slug = _slugify(src.stem)
        content = "---\ntitle: " + src.stem + "\nstatus: draft\nsource: bootstrap\n---\n\n" + content

    # 提取 title 作为文件名
    title_match = re.search(r'^title:\s*["\']?(.+?)["\']?\s*$', content.split("---", 2)[1], re.MULTILINE)
    filename = _slugify(title_match.group(1) if title_match else src.stem) + ".md"
    filepath = STAGING_DIR / node / filename

    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_text(content, encoding="utf-8")
    print(f"  ✅ 已导入: {filepath}")

    errors = _validate_frontmatter(filepath)
    if errors:
        print(f"  ⚠ 验证发现 {len(errors)} 个问题:")
        for e in errors:
            print(f"    - {e}")
    else:
        print(f"  ✅ 格式验证通过")


def cmd_list(args):
    """列出 staging 中所有 lessons"""
    if not STAGING_DIR.exists():
        print("  staging 目录为空")
        return

    total = 0
    for node_dir in sorted(STAGING_DIR.iterdir()):
        if not node_dir.is_dir():
            continue
        files = sorted(node_dir.glob("*.md"))
        if not files:
            continue
        print(f"\n  {node_dir.name}/ ({len(files)} 条):")
        for f in files:
            total += 1
            # 提取 title
            content = f.read_text(encoding="utf-8")
            title = "?"
            if content.startswith("---"):
                m = re.search(r'^title:\s*["\']?(.+?)["\']?\s*$', content.split("---", 2)[1], re.MULTILINE)
                if m:
                    title = m.group(1)
            status_m = re.search(r'^status:\s*(\S+)', content.split("---", 2)[1], re.MULTILINE)
            status = status_m.group(1) if status_m else "?"
            print(f"    [{status[:4]}] {f.name}  {title}")

    print(f"\n  总计: {total} 条草稿")


def cmd_validate(args):
    """验证 staging 中所有 lessons 格式"""
    if not STAGING_DIR.exists():
        print("  staging 目录为空")
        return

    total = errors = 0
    for node_dir in sorted(STAGING_DIR.iterdir()):
        if not node_dir.is_dir():
            continue
        for f in sorted(node_dir.glob("*.md")):
            total += 1
            errs = _validate_frontmatter(f)
            if errs:
                errors += 1
                title = f.name.replace(".md", "")
                print(f"  ❌ {node_dir.name}/{f.name}")
                for e in errs:
                    print(f"      {e}")

    if errors == 0:
        print(f"  ✅ 全部 {total} 条格式验证通过")
    else:
        print(f"  ⚠ {total} 条中 {errors} 条有问题")


def cmd_wizard(args):
    """交互式引导创建 lesson（供 Hermes agent 调用）"""
    print("  ⚡ 交互模式：请按提示输入")
    print("  (直接回车跳过可选字段)")

    title = input("  title: ").strip()
    if not title:
        print("  ❌ title 必填")
        sys.exit(1)

    domain = input("  domain (rag/devops/fanuc/network/hub/feishu/claude): ").strip()
    if not domain:
        domain = "general"

    subdomain = input("  subdomain (可选): ").strip()

    tags_input = input("  tags (逗号分隔, e.g. project:rag,severity:high): ").strip()

    print("  --- 输入 lesson 正文（Ctrl+D 结束） ---")
    print("  (请包含 ## 问题 / ## 修复 / ## 验证)")
    body_lines = []
    try:
        for line in sys.stdin:
            body_lines.append(line)
    except EOFError:
        pass

    body = "".join(body_lines).strip()
    if not body:
        body = "## 问题\n\n（待填写）\n\n## 修复\n\n（待填写）\n\n## 验证\n\n（待填写）\n"

    slug = _slugify(title)
    filename = f"{slug}.md"
    filepath = STAGING_DIR / args.node / filename

    tag_list = [t.strip() for t in tags_input.split(",") if t.strip()]
    if not any(t.startswith("node:") for t in tag_list):
        tag_list.insert(0, f"node:{args.node}")

    frontmatter = {
        "title": title,
        "domain": domain,
        "subdomain": subdomain,
        "tags": tag_list,
        "source": "bootstrap",
        "status": "draft",
        "confidence": 0.7,
        "created": datetime.now().strftime("%Y-%m-%d"),
        "last_verified": "",
        "verified_by": "",
        "related": "",
        "alternative_of": "",
    }

    fm_str = "---\n" + "\n".join(f"{k}: {v}" for k, v in frontmatter.items()) + "\n---\n\n"
    content = fm_str + body

    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_text(content, encoding="utf-8")
    print(f"\n  ✅ 已保存: {filepath}")

    errors = _validate_frontmatter(filepath)
    if errors:
        print(f"  ⚠ 验证发现 {len(errors)} 个问题:")
        for e in errors:
            print(f"    - {e}")


def cmd_wizard_ref(args):
    """交互式引导创建 reference 文档"""
    import yaml

    print("  ⚡ Reference 向导：请按提示输入")
    print("  (直接回车跳过可选字段)\n")

    title = input("  title: ").strip()
    if not title:
        print("  ❌ title 必填")
        sys.exit(1)

    domain = input("  domain (rag/devops/fanuc/network/hub/feishu/wechat): ").strip()
    if not domain:
        domain = "general"

    ref_type = input(f"  type ({'/'.join(VALID_REF_TYPES)}): ").strip()
    if not ref_type or ref_type not in VALID_REF_TYPES:
        ref_type = "iteration-trajectory"

    related_input = input("  related_lessons (逗号分隔文件名，不含.md): ").strip()
    related_lessons = [l.strip() for l in related_input.split(",") if l.strip()]

    print("\n  --- 输入 reference 正文（Ctrl+D 结束） ---")
    print("  模板结构:")
    print("    ## 背景")
    print("    ## 迭代一: ... (α→β→γ→δ)")
    print("    ## 迭代二: ...")
    print("    ## 收敛总结")
    print("    ## 对后续 agent 的建议")
    print()

    body_lines = []
    try:
        for line in sys.stdin:
            body_lines.append(line)
    except EOFError:
        pass

    body = "".join(body_lines).strip()
    if not body:
        body = "## 背景\n\n（需求/上下文）\n\n## 迭代一\n\n### α 方案\n\n**背景**：\n\n**行动**：\n\n**结果**：\n\n**决策**：[继续/反转 → β]\n\n## 收敛总结\n\n| 阶段 | 触发 | 决策 | 原因 |\n|------|------|------|------|\n\n## 对后续 agent 的建议\n\n1. \n"

    slug = _slugify(title)
    filename = f"{slug}.md"
    PROJECT_ROOT = Path(__file__).parent.parent.parent
    REFS_DIR = PROJECT_ROOT / "reference"
    filepath = REFS_DIR / filename

    frontmatter = {
        "title": title,
        "domain": domain,
        "source": "opus4.6",
        "created": datetime.now().strftime("%Y-%m-%d"),
        "status": "reference",
        "type": ref_type,
        "related_lessons": related_lessons,
    }

    fm_str = yaml.safe_dump(frontmatter, allow_unicode=True, default_flow_style=False, sort_keys=False)
    content = f"---\n{fm_str}---\n\n{body}"

    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_text(content, encoding="utf-8")
    print(f"\n  ✅ 已保存: {filepath}")
    print(f"  类型: {ref_type}")
    if related_lessons:
        print(f"  关联 lessons: {', '.join(related_lessons)}")


def main():
    parser = argparse.ArgumentParser(description="MisakaNet 历史教训批量提取工具")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # init
    p_init = sub.add_parser("init", help="创建 lesson 模板")
    p_init.add_argument("node", choices=VALID_NODES, help="节点名")
    p_init.add_argument("title", help="Lesson 标题")
    p_init.add_argument("--domain", default="general", help="Domain 分类")
    p_init.add_argument("--subdomain", default="", help="领域细分")
    p_init.add_argument("--tags", default="", help="逗号分隔的标签")

    # import
    p_imp = sub.add_parser("import", help="从文件导入 lesson")
    p_imp.add_argument("node", choices=VALID_NODES)
    p_imp.add_argument("file", help="markdown 文件路径")

    # list
    sub.add_parser("list", help="列出所有草稿")

    # validate
    sub.add_parser("validate", help="验证所有草稿格式")

    # wizard
    p_wiz = sub.add_parser("wizard", help="交互式引导创建 lesson")
    p_wiz.add_argument("node", choices=VALID_NODES)

    # wizard-ref
    p_ref = sub.add_parser("wizard-ref", help="交互式引导创建 reference 文档")
    p_ref.add_argument("node", choices=VALID_NODES)

    args = parser.parse_args()

    commands = {
        "init": cmd_init,
        "import": cmd_import,
        "list": cmd_list,
        "validate": cmd_validate,
        "wizard": cmd_wizard,
        "wizard-ref": cmd_wizard_ref,
    }

    commands[args.cmd](args)


if __name__ == "__main__":
    main()
