---
{"title": "GitHub TLS 握手失败 — gnutls_handshake() 错误", "domain": "devops", "source": "unknown", "status": "draft", "tags": ["git", "github", "TLS", "SSL", "network"], "created": "2026-06-12 18:46:23 UTC", "updated": "2026-06-12 18:46:23 UTC"}
---


## 背景

`git pull` 或 `git push` 时报：
```
gnutls_handshake() failed: The TLS connection was non-properly terminated.
```

## 根因

通常是瞬时网络问题或代理配置不正确。git 在 TLS 层面断开连接。

## 修复

```bash
# 1. 先重试一次（如果是瞬时问题）
git pull origin main

# 2. 如果持续失败，配置代理
git config --global http.proxy http://127.0.0.1:7890
git config --global https.proxy http://127.0.0.1:7890

# 3. 验证连接
git ls-remote origin HEAD
# 正常返回 HEAD commit hash
```

## 验证

```bash
git pull  # 不再报 TLS 错误
```
