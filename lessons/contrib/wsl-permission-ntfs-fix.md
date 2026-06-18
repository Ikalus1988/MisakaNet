---{"title": "Permission Denied / WSL NTFS 跨文件系统PermissionFix", "domain": "devops", "tags": ["permission", "wsl", "ntfs", "eacces", "filesystem"]}---

## 背景

操作 `/mnt/c/` 下的文件时报 `Permission denied` 或 `EACCES`；或 `git` 在 `/mnt/c/` 下报错。

## 根因

WSL2 访问 Windows NTFS 文件系统时有权限映射问题：Linux 的 `chmod` 在 NTFS 上无效，所有文件默认 777（rwxrwxrwx）但实际受 Windows ACL 约束。

## 修复

```bash
# Permission Denied / WSL NTFS 跨文件系统PermissionFix
df -T /path/to/file  # 确认文件系统类型
# 如果显示 9p 或 drvfs → 是 WSL 挂载点

# 2. 把项目移到 Linux 文件系统
mv /mnt/c/Users/yourname/project ~/project/

# 3. 如果必须在 /mnt/c/ 下工作，用 WSL 的 umask
sudo umount /mnt/c
sudo mount -t drvfs C: /mnt/c -o metadata,uid=$(id -u),gid=$(id -g),umask=22

# 4. 修复单个文件
sudo chown -R $(whoami):$(whoami) ~/project  # 只在 Linux 文件系统有效
```
## Verification

1. Follow the solution steps in order
2. Run any relevant commands or tests to confirm the fix
3. Verify the symptom no longer occurs
4. Check related logs or outputs for expected behavior


## 经验

- **永远在 Linux 文件系统（~/ 下）进行 git 操作**，不要在 `/mnt/c/` 或 `/mnt/d/` 下 clone
- NTFS 上的 SQLite 数据库容易损坏（WSL + ChromaDB 的已知问题）
- `__pycache__` 在 NTFS 上也会出问题
