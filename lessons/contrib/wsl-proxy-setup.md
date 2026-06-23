---{"title": "WSL 代理Setup — Via Windows 梯子Access外网", "domain": "devops", "tags": ["wsl", "proxy", "network", "windows"]}---

## Background

WSL 内 `curl google.com` 失败，但 Windows 能正常访问外网。WSL Default不走 Windows 的代理。

## 根因

WSL2 有自己的网络命名空间，Windows 代理不会Automatic继承到 Linux 环境。

## Fix

```bash
# WSL 代理Setup — Via Windows 梯子Access外网
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

# 3. git 单独Settings（WSL git 不走Environment variable）
git config --global http.proxy http://$(hostname).local:7890
git config --global https.proxy http://$(hostname).local:7890
```

**Note：** 端口 7890 是常见代理端口，实际端口由你的代理软件决定（Clash Default 7890，v2ray Default 10808）。

## 验证

```bash
curl -I https://google.com  # 应返回 200
```
