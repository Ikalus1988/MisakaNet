---
created: '2026-07-06'
domain: devops
language: zh
source: unknown
status: published
tags:
- devops
- hermes
- model
- switch
- ccswitch
title: ccswitch-hermes-switch 踩坑Notes
verification: metadata-normalized
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---
# ccswitch-hermes-switch 踩坑Notes

> Domain: devops | Tags: ccswitch, hermes-switch, model, switching, proxy, deepseek, InternalGateway | Source: hermes_wsl

## Problem

Claude Code (cc) 和 Hermes Agent 使用不同的配置文件/代理通道，各自需要独立的模型管理方案。手动改配置容易出错（改错文件、两侧不一致）。


## Root Cause

See problem description above for technical details.

## Solution

两个独立脚本，各管各的：

### ccswitch — 给 Claude Code 用

`~/ccswitch` — 一键切换 cc 的模型+代理上游。

```bash
ccswitch list              # 可用模型
ccswitch status            # 当前配置
ccswitch ds-flash          # 切到 DeepSeek Flash
```

自动做三件事：
1. 更新 `~/.claude/settings.json`（WSL 侧）
2. 更新 `<REDACTED> 侧）
3. 重启 `~/anthropic-openai-proxy.py` 换上游

### hermes-switch — 给 Hermes Agent 用

`~/hermes-switch` — 一键切换 Hermes 的 model/provider/base_url。

```bash
hermes-switch list         # 可用模型
hermes-switch status       # 当前配置
hermes-switch ds-flash     # 切到 DeepSeek Flash
```

改的是 `~/.hermes/config.yaml` 的 `model.default` / `model.provider` / `model.base_url`。

### 常用组合

```bash
# cc 跑 DeepSeek，Hermes 跑 InternalModel（省 Hermes token）
ccswitch ds-flash
hermes-switch InternalModel-2.5-pro

# cc 跑 InternalModel，Hermes 跑 DeepSeek（cc 省 token）
ccswitch InternalModel-2.5-pro
hermes-switch ds-flash
```

### 支持的模型

| 短名 | 模型 | 上游 |
|------|------|------|
| ds-flash | deepseek-v4-flash | DeepSeek |
| ds-pro | deepseek-v4-pro | DeepSeek |
| InternalModel-2.5-pro | internal/InternalModel-v2.5-pro | InternalGateway |
| InternalModel-2.5 | internal/InternalModel-v2.5 | InternalGateway |
| InternalModel-2-pro | internal/InternalModel-v2-pro | InternalGateway |
| InternalModel-flash | internal/InternalModel-v2-flash | InternalGateway |
## Verification

```bash
echo "Lesson: ccswitch-hermes-switch 踩坑Notes"
wc -l lessons/contrib/hermes-model-switch-ccswitch.md
```

**Expected Output:**
```
Lesson: ccswitch-hermes-switch 踩坑Notes
# (line count)
```

## 相关文件

- `~/ccswitch` — cc 切换脚本
- `~/hermes-switch` — Hermes 切换脚本
- `~/.hermes/config.yaml` — Hermes 配置（含完整 fallback 链）
- `/tmp/proxy_env.sh` — InternalGateway API key
- `~/anthropic-openai-proxy.py` — 本地代理
