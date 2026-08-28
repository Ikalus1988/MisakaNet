---
created: '2026-07-06'
domain: wsl
language: zh
source: unknown
status: published
tags:
- wsl
- terminal
- underscore
- missing
title: WSL Windows 终端复制粘贴吞下划线Issue
verification: metadata-normalized
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---
## Problem

从 Windows 复制文本粘贴到 WSL 终端时，下划线 `_` 字符消失。配置文件、命令中的下划线名全部错误。

## Root Cause

Windows Terminal 的「使用 Ctrl+Shift+C/V 作为复制粘贴」和「将文本格式设置为 HTML」同时启用时，某些版本的 Windows Terminal 在 VIM/Python REPL 中粘贴时过滤了下划线。

## Solution

```bash
# WSL Windows 终端复制粘贴吞下划线Issue
# 设置 → 交互 → 将文本格式设置为 HTML → 关闭

# 方案 2：右键粘贴代替 Ctrl+Shift+V（不经过过滤）

# 方案 3：通过文件中转
# Windows:
echo "your_text_with_underscores" > \\\\wsl$\\<distro>\\home\\hp\\temp.txt

# WSL:
cat ~/temp.txt
```

## Verification

```bash
echo "Lesson: WSL Windows 终端复制粘贴吞下划线Issue"
wc -l lessons/contrib/wsl-terminal-underscore-missing.md
```

**Expected Output:**
```
Lesson: WSL Windows 终端复制粘贴吞下划线Issue
# (line count)
```
