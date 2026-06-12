---
{"title": "GitHub DNS 污染/443端口不通 — hosts 备用 IP 方案", "domain": "devops", "source": "unknown", "status": "draft", "tags": ["git", "github", "TLS", "network", "DNS", "hosts", "connectivity"], "created": "2026-06-12 18:46:23 UTC", "updated": "2026-06-12 18:46:23 UTC"}
---


## 背景

`git push` / `git fetch` 持续超时或报 TLS 握手错误：

```
fatal: unable to access 'https://github.com/...':
  GnuTLS recv error (-110): The TLS connection was non-properly terminated.
```

重试无效，非瞬时问题。

## 根因

DNS 解析正常，但解析到的 IP 的 **443 端口被运营商/防火墙屏蔽**。ICMP ping 通但 HTTPS 握手失败。

典型症状：

| 检查项 | 结果 |
|--------|------|
| `ping github.com` | ✅ 通 |
| `getent hosts github.com` | ✅ 返回 IP |
| `curl -I https://github.com` | ❌ 超时 |
| `timeout 3 bash -c 'echo > /dev/tcp/<IP>/443'` | ❌ 不可达 |

## 修复

### 1. 验证当前 DNS 解析的 IP 是否可达

```bash
GITHUB_IP=$(getent hosts github.com | awk '{print $1}')
timeout 3 bash -c "echo > /dev/tcp/$GITHUB_IP/443" && echo "✅ 可达" || echo "❌ 不可达"
```

### 2. 扫描 GitHub 备用 IP 的 443 端口

GitHub 官方 IP 范围（部分）：

```
140.82.112.0/20    # 主要服务
185.199.108.0/22   # Pages/CDN
192.30.252.0/22    # 旧范围
```

扫描脚本：

```bash
for ip in 140.82.112.3 140.82.112.4 140.82.113.3 140.82.114.3 \
          140.82.121.3 140.82.121.4 \
          185.199.108.153 185.199.109.153 185.199.110.153; do
  timeout 3 bash -c "echo > /dev/tcp/$ip/443" 2>/dev/null \
    && echo "✅ $ip" || echo "❌ $ip"
done
```

### 3. 写入 hosts

任选一个可达的 IP，写入 `/etc/hosts`：

```bash
echo "<可达IP> github.com api.github.com" | sudo tee -a /etc/hosts
```

### 4. 验证

```bash
git fetch origin main
# 正常返回分支信息 → 修复成功
```

## 验证

```bash
# 检查 hosts 是否生效
getent hosts github.com
# 预期返回: <可达IP>  github.com

# 测试 Git 操作
git ls-remote origin HEAD
# 正常返回 commit hash
```

## 注意事项

- `/etc/hosts` 修改后即时生效，无需重启
- 如果 Git 配置了代理（`git config --global http.proxy`），优先排查代理
- hosts 条目在 DNS 正常的环境下不会造成冲突，可作为常驻方案
- 不同运营商/地区可达的 IP 可能不同，建议现场扫描

## 附带工具

```bash
# 一键扫描脚本保存到本地
cat > ping_github.sh << 'SCRIPT'
#!/bin/bash
for ip in 140.82.112.3 140.82.112.4 140.82.113.3 140.82.114.3 \
          140.82.121.3 140.82.121.4 \
          185.199.108.153 185.199.109.153 185.199.110.153; do
  timeout 3 bash -c "echo > /dev/tcp/$ip/443" 2>/dev/null \
    && echo "✅ $ip:443 可达" || echo "❌ $ip:443 不可达"
done
SCRIPT
chmod +x ping_github.sh
```
