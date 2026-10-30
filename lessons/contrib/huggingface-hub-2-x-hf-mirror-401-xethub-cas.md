---
title: "huggingface_hub 2.x 经 hf-mirror 下载大模型 401 xethub CAS 失败"
domain: "devops"
tags:
  - "huggingface"
  - "hf-mirror"
  - "xethub"
  - "cas"
  - "401"
  - "download"
  - "cn-network"
  - "safetensors"
status: "published"
evidence_level: "E1"
created: "2026-10-30"
updated: "2026-10-30"
source: "intake-3113"
summary_plain: "在墙内服务器上设置 HF_ENDPOINT=https://hf-mirror.com，用 huggingface_hub 2.2.0 的 hf download 下载 15.7GB 的 safetensors…"
trigger: "huggingface_hub 2.x 经 hf-mirror 下载大模型 401 xethub CAS 失败. 在墙内服务器上设置 HF_ENDPOINT=https://hf-mirror.com，用 huggingface_hub 2.2.0 的 hf download 下载…"
verify: "降级到 huggingface_hub 1.1.0 后 hf download 使用同一 HF_ENDPOINT 正常完成 15.7GB 下载；sha256sum 与仓库 SHA256SUMS 完全一致（示例 a166c7bbbe66a22065159e478335fee4a633c4a3e3bb34c8e8ac4cc91bf4996f）。"
provenance:
  issue: "#3113"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

在墙内服务器上设置 HF_ENDPOINT=https://hf-mirror.com，用 huggingface_hub 2.2.0 的 hf download 下载 15.7GB 的 safetensors 模型，元数据小文件正常，但大权重文件报错并退出：RuntimeError: File reconstruction error: CAS Client Error: Request error: HTTP status client error (401 Unauthorized), domain: https://cas-server.xethub.hf.co/v2/reconstructions/&lt;hash&gt;。curl 直接访问 hf-mirror resolve 链接却 302 到 cas-bridge.xethub.hf.co 且 200 可用。

## Root Cause

huggingface_hub 2.x 下载大文件默认改用新的 xethub CAS 重构协议（cas-server.xethub.hf.co/v2/reconstructions/...），该存储 API 需要认证，匿名/镜像转发场景直接 401；而传统的 resolve 链接（302 到 cas-bridge 预签名 URL）仍开放可用。版本差异导致旧版 hf CLI 能用、2.x 反而失败。

## Fix

1) 降级为不发 xethub 的版本：pip install -U "huggingface_hub==1.1.0"，再运行 hf download（或 huggingface-cli download），走传统 resolve 预签名直链，HF_ENDPOINT=https://hf-mirror.com 下并发下载正常。\n2) 或完全绕开 hf CLI，curl 直下镜像 resolve 链接：curl -L -C - -o out.safetensors "https://hf-mirror.com/<org>/<repo>/resolve/main/<file>"。该 URL 302 跳转到官方 cas-bridge.xethub.hf.co 的预签名直链（约 1 小时有效），curl 断点续传时会重新请求镜像、自动拿到新签名，可放心大文件续传。下载完必须用仓库 SHA256SUMS 或 ModelScope API 返回的 Sha256 校验。

## Verification

降级到 huggingface_hub 1.1.0 后 hf download 使用同一 HF_ENDPOINT 正常完成 15.7GB 下载；sha256sum 与仓库 SHA256SUMS 完全一致（示例 a166c7bbbe66a22065159e478335fee4a633c4a3e3bb34c8e8ac4cc91bf4996f）。
