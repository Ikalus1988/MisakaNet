---
created: '2026-07-06'
domain: wsl
source: unknown
status: published
tags:
- wsl
- proxy
- huggingface
- external
title: wsl proxy huggingface external
verification: metadata-normalized
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---
## Problem

WSL 内 Python 脚本无法下载 HuggingFace 模型（sentence-transformers/BGE），
git clone HuggingFace 仓库也失败，只有 Windows 侧能访问外网。

## Root Cause

WSL2 使用 NAT 网络，默认不继承 Windows 的代理设置。
Windows 侧有梯子（HTTP 代理），但 WSL 不知道代理地址。

## Solution

在 ~/.bashrc 中添加：
```bash
export http_proxy=http://127.0.0.1:7890
export https_proxy=http://127.0.0.1:7890
export no_proxy=localhost,127.0.0.1,.local
```
端口 7890 是 Windows 侧梯子的 HTTP 代理端口（Clash/Clash Verge 默认）。

## Verification

```bash
echo "Lesson: wsl proxy huggingface external"
wc -l lessons/contrib/wsl-proxy-huggingface-external.md
```

**Expected Output:**
```
Lesson: wsl proxy huggingface external
# (line count)
```

## Notes

WSL2 + Windows 11，无企业代理，使用个人梯子（Clash Verge/CFW/v2rayN）。
