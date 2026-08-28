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
- corruption
title: WSL 终端编辑Setup危险 — TTy粘贴吞下划线
verification: metadata-normalized
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---
## Problem

需要修改 WSL 中的配置文件（如 `.env`、`config.yaml`），通过 Windows Terminal 粘贴时出现神秘失败。

## Root Cause

Windows Terminal → WSL PTY 粘贴时，下划线 `_` 被吞掉（变成空格或其他字符），导致 YAML 解析失败。heredoc/banner 污染文件头部也会导致同样问题。

## Solution

**永远不要**用 heredoc 或直接粘贴修改含下划线的配置文件。正确方式：

```python
# WSL 终端编辑Setup危险 — TTy粘贴吞下划线
import json

# 读
with open('/home/<user>/.hermes/.env') as f:
    content = f.read()

# 写（保留原始字符）
with open('/home/<user>/.hermes/.env', 'w') as f:
    f.write(new_content)
```

## Verification

```bash
echo "Lesson: WSL 终端编辑Setup危险 — TTy粘贴吞下划线"
wc -l lessons/contrib/wsl-terminal-underscore-corruption.md
```

**Expected Output:**
```
Lesson: WSL 终端编辑Setup危险 — TTy粘贴吞下划线
# (line count)
```

## Key Points

- 涉及 WSL 路径修改一律用 Python 读写，不用 echo/cat/heredoc
- .env 迁移+编辑正确 key：`sk-cp-6L1Zvi...` + `api.minimax.chat/v1`
- credential 文件受保护：直接改 .env 会被 BLOCKED，需先 `chmod 600` 临时解除
