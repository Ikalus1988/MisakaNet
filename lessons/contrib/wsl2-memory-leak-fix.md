---
domain: "contrib"
title: "WSL2 内存泄漏 / 内存占用过高"
verification: "metadata-normalized"
{"title": "WSL2 内存泄漏 / 内存占用过高", "domain": "devops", "tags": ["wsl", "memory", "leak", "performance"], "domain_expert": "unknown"}
---

## 背景

WSL2 运行几天后吃掉 8GB+ 内存，Windows 变卡。`free -h` 显示已用内存极高。

## 根因

WSL2 使用动态内存分配，默认不自动回收。长时间运行的进程（如 Python 服务、向量数据库）申请的内存在进程退出后不会立刻归还 Windows。

## 修复

```bash
# WSL2 内存泄漏 / 内存占用过高
free -h
cat /proc/meminfo | grep MemAvailable

# 2. 限制 WSL2 最大内存（在 Windows 用户目录下创建 .wslconfig）
# 文件路径: C:\Users\<用户名>\.wslconfig
#
# [wsl2]
# memory=4GB
# swap=2GB
# localhostForwarding=true

# 3. 手动释放缓存
sudo sh -c 'echo 3 > /proc/sys/vm/drop_caches'

# 4. 重启 WSL（从 Windows PowerShell）
# wsl --shutdown
# wsl
```

## 验证

```bash
free -h  # 内存应恢复到限制值内
```
