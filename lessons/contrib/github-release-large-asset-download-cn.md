---
{
  "title": "GitHub Release 大文件下载在 CN 网络超时：分段并行下载方案",
  "domain": "devops",
  "tags": ["github", "download", "cn-network", "proxy", "large-file", "timeout"],
  "status": "published",
  "evidence_level": "E2",
  "source": "mcp-intake-1069",
  "created": "2026-08-17",
  "updated": "",
  "verified_date": "",
  "domain_expert": ""
}

provenance:
  source: "unknown"
  contributor: "Ikalus1988"
  merged_at: "2026-08-17"
  evidence: "post-publication"
---

## Problem

GitHub Release 大文件（60MB）在 CN 网络下载失败：直连 GitHub 速度极慢（~107KB/s）然后不可达；gh-proxy 镜像大多失效或 429；单连接断点续传通过代理会损坏文件（重试后文件大小缩小）。

## Root Cause

1. GitHub CDN 在 CN 限流严重，直连大文件下载容易超时
2. 代理服务（ghproxy 等）对长连接不稳定，会断开连接
3. 断点续传通过代理时，代理可能从头传输，导致文件损坏
4. 并发直连 GitHub 会被 CDN 限流

## Solution

**分段并行下载 + 校验：**

1. 将大文件分成 6 个 10MB 分段
2. 通过 ghproxy 代理并行下载（代理不限制并发）
3. 每个分段独立 `--retry`
4. 合并分段
5. sha256 校验（对照官方 manifest）

```bash
# 分段下载示例
for i in $(seq 0 5); do
  start=$((i * 10485760))
  end=$(((i + 1) * 10485760 - 1))
  curl -C - -R -o "segment_$i" \
    "https://ghproxy.net/https://github.com/owner/repo/releases/download/v1.0/large-file" \
    -H "Range: bytes=$start-$end" \
    --retry 3 --retry-delay 5 &
done
wait

# 合并
cat segment_* > large-file
rm segment_*

# 校验
sha256sum -c manifest.sha256
```

**npm 包安装替代方案：**

```bash
# 安装时跳过脚本
npm install --ignore-scripts

# 手动下载二进制到 bin/downloads/
# 创建 .version 标记文件
```

## Verification

1. sha256 与官方 manifest 一致
2. 执行 `codewhale --version` 确认版本正确
3. 文件大小与官方 Release 一致

## Key Points

- 分段大小 10MB 低于代理稳定传输窗口
- ghproxy 代理不限制并发连接数
- 每个分段独立重试，避免整体失败
- sha256 校验是必须的，防止代理篡改或传输损坏
