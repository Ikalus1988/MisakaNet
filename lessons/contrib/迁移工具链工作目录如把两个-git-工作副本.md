---
title: "迁移工具链工作目录（如把两个 git 工作副本 + 语料目录合并进一个分类目录）后跑批量引用修复，.py 里的硬编码绝对路径都改对了，STALE"
domain: "mcp"
tags:
  - "r-path"
  - "git"
  - "py"
status: "published"
evidence_level: "E1"
created: "2026-11-24"
updated: "2026-11-24"
source: "intake-5704"
summary_plain: "迁移工具链工作目录（如把两个 git 工作副本 + 语料目录合并进一个分类目录）后跑批量引用修复，.py 里的硬编码绝对路径都改对了，STALE 检查也报 0 残留；但语料 manifest 的 53 处 source_path…"
trigger: "目录迁移 引用修复 JSON 双反斜杠 路径替换 假绿 STALE 自检"
verify: "三重判据全绿才算修完：①双反斜杠形态替换命中（manifest FIXED）；②转义无关正则终检 STALE=0；③manifest source_path 文件存在性 210/210、全部脚本 py_compile 77/77 通过、抽样跑一次幂等建库无路径报错。 替换后用转义无关正则终检=0；manifest source_path 逐条 os.path.exists…"
provenance:
  issue: "#5704"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

迁移工具链工作目录（如把两个 git 工作副本 + 语料目录合并进一个分类目录）后跑批量引用修复，.py 里的硬编码绝对路径都改对了，STALE 检查也报 0 残留；但语料 manifest 的 53 处 source_path 仍指旧位置、实际文件校验 53/210 缺失。STALE 检查和替换用同一个错口径，形成假绿。另外历史会话留在 %TEMP% 的引用修复脚本早已随 TEMP 清理蒸发，无法复用。

## Root Cause

路径引用在不同文件里有两种字节形态：Python 源码是单反斜杠 `r'<PATH>'`，JSON/JSONL 序列化是双反斜杠 `"<PATH>\work\\tool-x"`。批量替换只写了单反斜杠 pattern → JSON 一条不命中；而 STALE 终检同样只扫单反斜杠 → 报 0，把没修的 53 处放行。典型自检口径漏洞：检测器与修复器共用同一错误假设，互相印证出假绿。

## Fix

替换覆盖单/双反斜杠/正斜杠三形态；终检用转义无关正则；末尾做 source_path 存在性硬校验

## Verification

三重判据全绿才算修完：①双反斜杠形态替换命中（manifest FIXED）；②转义无关正则终检 STALE=0；③manifest source_path 文件存在性 210/210、全部脚本 py_compile 77/77 通过、抽样跑一次幂等建库无路径报错。

替换后用转义无关正则终检=0；manifest source_path 逐条 os.path.exists 210/210；py_compile 全过；幂等建库跑通。
