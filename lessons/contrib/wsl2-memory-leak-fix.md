---
{"title": "WSL2 内存泄漏 / 内存占用过高", "domain": "devops", "tags": ["wsl", "memory", "leak", "performance"], "domain_expert": "unknown"}
---

## Background

WSL2 Run几天后吃掉 8GB+ 内存，Windows 变卡。`free -h` 显示已用内存极高。

## 根因

WSL2 Use动态内存分配，Default不Automatic回收。长时间Run的进程（如 Python 服务、向量Database）申请的内存在进程退出后不会立刻归还 Windows。

## Fix

```bash
# WSL2 内存泄漏 / 内存占用过高
free -h
cat /proc/meminfo | grep MemAvailable

# 2. 限制 WSL2 最大内存（在 Windows 用户Directory下Create .wslconfig）
# FilePath: C:\Users\<用户名>\.wslconfig
#
# [wsl2]
# memory=4GB
# swap=2GB
# localhostForwarding=true

# 3. Manual释放缓存
sudo sh -c 'echo 3 > /proc/sys/vm/drop_caches'

# 4. 重启 WSL（从 Windows PowerShell）
# wsl --shutdown
# wsl
```

## 验证

```bash
free -h  # 内存应恢复到限制Value内
```
