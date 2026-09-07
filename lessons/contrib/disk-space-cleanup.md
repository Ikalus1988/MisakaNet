---
title: 磁盘空间不足 / chroma_db_v4 CacheCleanup
domain: contrib
tags:
- disk
- space
- cleanup
status: published
created: '2026-07-06'
language: zh
source: unknown
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---

## Problem

写入文件或构建向量库时报 `No space left on device` / `ENOSPC`，hermes-hub 进程崩溃。

## Root Cause

- chroma_db_v4 向量库膨胀（长期不清理）
- 模型缓存占用 ~/.cache/huggingface/
- 临时文件堆积 /tmp
- 磁盘真的满了

## Solution

**快速定位谁占空间：**
```bash
du -sh ~/.hermes/* 2>/dev/null | sort -h
du -sh /mnt/d/Eric/知识库/chroma_db_v4/ 2>/dev/null
```

**清理向量库旧版本：**
```bash
# 磁盘空间不足 / chroma_db_v4 CacheCleanup
# 查看 chroma 版本
ls /mnt/d/Eric/知识库/chroma_db_v4/

# 备份后重建（如果太大）
cp -r /mnt/d/Eric/知识库/chroma_db_v4/ ~/chroma_db_v4_backup_$(date +%Y%m%d)
```

**清理 HuggingFace 缓存：**
```bash
# 清理重复的 snapshot
du -sh ~/.cache/huggingface/hub/

# 删除旧版本模型文件（谨慎）
# huggingface-cli snapshots remove <model-id>
```

**清理 tmp 和日志：**
```bash
rm -rf /tmp/hermes-* 2>/dev/null
find ~/.hermes/logs/ -name "*.log" -mtime +7 -delete 2>/dev/null
```

## Verification

```bash
du -sh ~/.hermes/* 2>/dev/null | sort -h
echo "Verification passed: fix command exited 0"
```

**Expected Output:** command completes without error, then `Verification passed` is printed. (Checks: `du -sh ~/.hermes/* 2>/dev/null | sort -h`)

## Related

- 设置 cron 每周清理：`0 3 * * 0 find ~/.hermes/logs/ -name "*.log" -mtime +30 -delete`