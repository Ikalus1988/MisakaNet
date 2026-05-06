---
{"title": "磁盘空间不足 / 缓存清理方案", "domain": "devops", "tags": ["disk-space", "cleanup", "docker", "pip-cache"]}
---

## 背景

写入文件或构建时报 `No space left on device` / `ENOSPC`，进程崩溃。

## 根因

Cron 日志、pip 缓存、Docker 镜像、pyc 文件、大模型缓存长期积累。

## 修复

```bash
# 1. 查看磁盘占用
df -h /
du -sh ~/.cache/* | sort -rh | head -10

# 2. pip 缓存
pip cache purge

# 3. apt 缓存
sudo apt clean
sudo apt autoremove

# 4. Docker（如果使用）
docker system prune -af

# 5. journal 日志
sudo journalctl --vacuum-size=100M

# 6. 大文件查找
find ~ -type f -size +100M -exec ls -lh {} \; | sort -rh | head -20

# 7. Python __pycache__（递归删除）
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
```

## 预防

```bash
# 添加 cron：每周清理一次
0 3 * * 0 pip cache purge && sudo apt clean
```
