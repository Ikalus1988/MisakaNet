---
created: '2026-07-06'
domain: git
language: zh
source: unknown
status: published
tags:
- git
- handshake
- failure
title: GitHub TLS 握手失败 — gnutls_handshake() Error
verification: metadata-normalized
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---
## Problem

`git pull` 或 `git push` 时报：
```
fatal: unable to access 'https://github.com/user/repo.git/':
gnutls_handshake() failed: The TLS connection was non-properly terminated.
```

该错误会导致所有基于 HTTPS 的 git 远程操作中断，包括 `clone`、`fetch`、`pull`、`push`。

## Root Cause

TLS 握手失败通常由以下几种原因引起：

1. **瞬时网络抖动**：ISP 或路由器在 TCP 连接建立后、TLS 握手完成前意外断开连接，是最常见原因。
2. **代理配置错误**：系统已启用代理（如 Clash、V2Ray），但 git 未配置对应的 `http.proxy` / `https.proxy`，导致流量绕过代理直连失败；或代理地址/端口填写有误。
3. **证书链问题**：企业内网或某些 Linux 发行版的 CA 证书包过旧，无法验证 GitHub 的证书链。
4. **GnuTLS 版本缺陷**：部分 Ubuntu/Debian 系统自带的 `git` 编译链接了 GnuTLS，而非 OpenSSL，GnuTLS 在某些内核/网络栈组合下存在已知兼容性问题。
5. **防火墙/DPI 干扰**：深度包检测设备（企业防火墙、运营商 QoS）会重置 TLS 握手包。

## Solution

### 步骤 1：重试（排除瞬时抖动）

```bash
# 直接重试，大多数瞬时网络问题会自动恢复
git pull origin main
```

### 步骤 2：检查并配置代理

```bash
# 查看当前 git 代理设置
git config --global --list | grep proxy

# 若本机运行了代理客户端（默认端口 7890），则配置 git 走代理
git config --global http.proxy  http://127.0.0.1:7890
git config --global https.proxy http://127.0.0.1:7890

# 若不需要代理，清除错误的代理配置
git config --global --unset http.proxy
git config --global --unset https.proxy
```

### 步骤 3：更新 CA 证书

```bash
# Debian / Ubuntu
sudo apt update && sudo apt install --reinstall ca-certificates

# RHEL / CentOS / Fedora
sudo update-ca-trust
```

### 步骤 4：切换到 OpenSSL 版本的 git（针对 GnuTLS 问题）

```bash
# 检查当前 git 链接的 TLS 库
git version --build-options | grep -i tls
# 或
ldd $(which git) | grep -E 'gnutls|ssl'

# Ubuntu 下安装链接 OpenSSL 的 git
sudo apt install git-core
# 若仍为 GnuTLS，可从 ppa:git-core/ppa 获取最新版
sudo add-apt-repository ppa:git-core/ppa
sudo apt update && sudo apt install git
```

### 步骤 5：调整 TLS 版本（高级）

```bash
# 强制 git 使用 TLS 1.2，规避部分握手兼容性问题
git config --global http.sslVersion tlsv1.2
```

## Verification

```bash
git status --short | head -5
git log --oneline -3
```

**Expected Output:**
```
# (status)
# (recent)
```
