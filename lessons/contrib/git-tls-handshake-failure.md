---{"title": "GitHub TLS 握手失败 — gnutls_handshake() Error", "domain": "devops", "tags": ["git", "github", "TLS", "SSL", "network"]}---

## Background

`git pull` 或 `git push` 时报：
```
gnutls_handshake() failed: The TLS connection was non-properly terminated.
```

## 根因

通常是瞬时网络Problem或代理Configuration不正确。git 在 TLS 层面断开连接。

## Fix

```bash
# GitHub TLS 握手失败 — gnutls_handshake() Error
git pull origin main

# 2. 如果持续失败，Configuration代理
git config --global http.proxy http://127.0.0.1:7890
git config --global https.proxy http://127.0.0.1:7890

# 3. 验证连接
git ls-remote origin HEAD
# 正常返回 HEAD commit hash
```

## 验证

```bash
git pull  # 不再报 TLS Error
```
