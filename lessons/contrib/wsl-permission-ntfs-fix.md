---{"title": "Permission Denied / WSL NTFS 跨File系统PermissionFix", "domain": "devops", "tags": ["permission", "wsl", "ntfs", "eacces", "filesystem"]}---

## Background

操作 `/mnt/c/` 下的File时报 `Permission denied` 或 `EACCES`；或 `git` 在 `/mnt/c/` 下报错。

## 根因

WSL2 访问 Windows NTFS File系统时有权限映射Problem：Linux 的 `chmod` 在 NTFS 上无效，所有FileDefault 777（rwxrwxrwx）但实际受 Windows ACL 约束。

## Fix

```bash
# Permission Denied / WSL NTFS 跨File系统PermissionFix
df -T /path/to/file  # VerifyFile系统Type
# 如果显示 9p 或 drvfs → 是 WSL 挂载点

# 2. 把项目移到 Linux File系统
mv /mnt/c/Users/yourname/project ~/project/

# 3. 如果必须在 /mnt/c/ 下工作，用 WSL 的 umask
sudo umount /mnt/c
sudo mount -t drvfs C: /mnt/c -o metadata,uid=$(id -u),gid=$(id -g),umask=22

# 4. Fix单个File
sudo chown -R $(whoami):$(whoami) ~/project  # 只在 Linux File系统有效
```
## Verification

1. Follow the solution steps in order
2. Run any relevant commands or tests to confirm the fix
3. Verify the symptom no longer occurs
4. Check related logs or outputs for expected behavior


## 经验

- **永远在 Linux File系统（~/ 下）进行 git 操作**，不要在 `/mnt/c/` 或 `/mnt/d/` 下 clone
- NTFS 上的 SQLite Database容易损坏（WSL + ChromaDB 的已知Problem）
- `__pycache__` 在 NTFS 上也会出Problem
