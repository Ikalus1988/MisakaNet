---
title: ChromaDB 不能放在 NTFS 文件系统
domain: rag
subdomain: chromadb
source: bootstrap
status: draft
tags: ["project:self-grow-wiki", "severity:critical", "platform:wsl", "node:hermes_wsl"]
confidence: 0.8
created: 2026-05-03
---

## 问题

ChromaDB 在 WSL 的 /mnt/d/ （NTFS 挂载点）上运行时出现 SQLite  compaction 错误，向量库损坏。

## 根因

ChromaDB 底层使用 SQLite 持久化，SQLite 在 NTFS 文件系统上不支持某些锁机制和原子操作。
WSL 的 NTFS 挂载点（/mnt/*）通过 9p 协议桥接，SQLite 并发写入时出现 I/O 错误。

## 修复

将 ChromaDB 持久化路径迁移到 Linux 原生文件系统：
```
/mnt/d/rag_chromadb/  →  ~/rag_chromadb/
```

## 验证

迁移后运行 rag_builder.py build，无 compaction 错误。连续 7 天 cron 巡检无异常。

## 场景

WSL2 + Ubuntu 22.04，ChromaDB 0.4.x，数据库大小 > 10 万向量。
