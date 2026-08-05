---
{
  "domain": "contrib",
  "title": "GitHub DNS 污染/443端口不通 — hosts 备用 IP 方案",
  "verification": "metadata-normalized",
  "{\"title\"": "GitHub DNS 污染/443端口不通 — hosts 备用 IP 方案\", \"domain\": \"devops\", \"tags\": [\"git\", \"github\", \"TLS\", \"network\", \"DNS\", \"hosts\", \"connectivity\"], \"domain_expert\": \"unknown\"}",
  "created": "2026-07-06",
  "source": "unknown"
}
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

### 3. 写入 hosts — ⚠️ 只加 github.com，不加 api.github.com

**关键陷阱：`api.github.com` 的真实 IP 不同于 `github.com`。**

| 域名 | 真实 IP | 说明 |
|------|---------|------|
| `github.com` | 140.82.112.x/20 | Web/Git 服务 |
| `api.github.com` | **20.205.243.168** | REST API 服务（独立 IP 段） |

如果 hosts 里把 `api.github.com` 也指向 `github.com` 的 IP，API 请求会返回 **301 重定向**（TLS SNI 路由将 API 请求误识别为 Web 请求），导致 `curl -X POST https://api.github.com/user/repos` 等 API 调用全部失败。

**正确写法：**

```bash
# GitHub DNS 污染/443端口不通 — hosts 备用 IP 方案
echo "<可达IP> github.com" | sudo tee -a /etc/hosts

# ❌ 不要这样写——api.github.com 有自己的 IP
echo "<可达IP> github.com api.github.com" | sudo tee -a /etc/hosts

# 如果必须调 API，用 --resolve 绕过 hosts：
curl --resolve "api.github.com:443:20.205.243.168" \
  -H "Authorization: token $TOKEN" \
  https://api.github.com/user
```

**如果 hosts 已经写错了，修复：**

```bash
# 从 /etc/hosts 中移除 api.github.com
sudo sed -i 's/ github.com api.github.com/ github.com/' /etc/hosts
# 或者直接删掉整行重新写
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

## git push 的临时绕过方案（无需 sudo 改 hosts）

当 hosts 中的 IP 临时失效（如 `140.82.112.4` 的 443 端口间歇性不可达），且没有 sudo 权限改 hosts 时：

```bash
# 先扫一个可达的 IP
python3 -c "import socket;s=socket.create_connection(('140.82.112.3',443),timeout=5);s.close();print('OPEN')"

# 用 http.curloptResolve 跳过 hosts 直接指定 IP
git -c "http.curloptResolve=github.com:443:140.82.112.3" push

# 也可用于 git clone
git -c "http.curloptResolve=github.com:443:140.82.112.3" clone https://github.com/user/repo.git
```

原理：`http.curloptResolve` 等价于 curl 的 `--resolve` 选项，在 libcurl 层面强制域名解析到指定 IP，绕过系统 hosts 和 DNS。

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
