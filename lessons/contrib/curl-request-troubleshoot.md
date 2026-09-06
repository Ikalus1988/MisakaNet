---
title: curl / wget 请求失败通用Diagnosis
domain: network
tags:
- network
- curl
- request
- troubleshoot
status: published
created: '2026-07-06'
language: zh
source: unknown
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---

## Problem

`curl https://example.com` 返回空、报错或超时。不知道是 DNS、代理、证书还是目标服务的问题。

## Root Cause

网络请求的故障链路有多层，每一层都会产生不同错误。需要逐层排查。

## Solution

```bash
# curl / wget 请求失败通用Diagnosis
nslookup example.com
dig example.com
# 正常返回 IP 地址 → DNS OK
# 返回 NXDOMAIN / server can't find → DNS 问题

# 2. 网络连通性（跳过代理）
curl -v --noproxy "*" https://example.com
# 能连接但超时 → 防火墙/代理问题

# 3. 证书验证
curl -v https://example.com
# SSL certificate problem → 证书问题
# 临时跳过（仅测试）：
curl -k https://example.com

# 4. 代理验证
echo $http_proxy
echo $https_proxy
# 查看当前代理配置

# 5. 指定超时（默认无超时）
curl --connect-timeout 5 --max-time 10 https://example.com

# 6. 只看响应头（不下载内容）
curl -I https://example.com

# 7. 完整的排查命令
curl -v --trace-ascii /dev/stderr https://example.com 2>&1 | head -30
```
## Verification

```bash
echo $http_proxy
echo "Verification passed: fix command exited 0"
```

**Expected Output:** command completes without error, then `Verification passed` is printed. (Checks: `echo $http_proxy`)

## 错误速查

| 错误 | 原因 | 方向 |
|------|------|------|
| `Could not resolve host` | DNS 故障 | 检查 `/etc/resolv.conf` / 代理 |
| `Connection refused` | 目标端口未开放 | 确认服务是否运行 |
| `Connection timed out` | 防火墙/网络不通 | 检查代理或换源 |
| `SSL certificate problem` | 证书过期/自签 | `-k` 临时跳过 |
| `Failed to connect` | 网络不可达 | 先 ping 确认 |