---
{"title": "WSL 代理配置 — 通过 Windows 梯子访问外网", "domain": "devops", "tags": ["wsl", "proxy", "network", "windows"]}
---

## 背景

WSL 内 `curl google.com` 失败，但 Windows 能正常访问外网。WSL 默认不走 Windows 的代理。

## 根因

WSL2 有自己的网络命名空间，Windows 代理不会自动继承到 Linux 环境。

## 修复

```bash
# 1. 设置代理环境变量（临时）
export http_proxy=http://$(hostname).local:7890
export https_proxy=http://$(hostname).local:7890
export HTTP_PROXY=$http_proxy
export HTTPS_PROXY=$https_proxy

# 2. 永久加入 ~/.bashrc
echo '
export http_proxy=http://$(hostname).local:7890
export https_proxy=http://$(hostname).local:7890
export NO_PROXY=localhost,127.0.0.1,.local
' >> ~/.bashrc

# 3. git 单独设置（WSL git 不走环境变量）
git config --global http.proxy http://$(hostname).local:7890
git config --global https.proxy http://$(hostname).local:7890
```

**注意：** 端口 7890 是常见代理端口，实际端口由你的代理软件决定（Clash 默认 7890，v2ray 默认 10808）。

## 验证

```bash
curl -I https://google.com  # 应返回 200
```
