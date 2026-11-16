---
title: "两个独立进程并发写同一个 SQLite 数据库（WAL 模式已开），一个进程写批量事务期间另一个进程 INSERT 报 `database is locked`"
domain: "dsh"
tags:
  - "database"
  - "sqlite"
  - "wal"
status: "published"
evidence_level: "E1"
created: "2026-11-16"
updated: "2026-11-16"
source: "intake-5069"
summary_plain: "两个独立进程并发写同一个 SQLite 数据库（WAL 模式已开），一个进程写批量事务期间另一个进程 INSERT 报 `database is…"
trigger: "两个独立进程并发写同一个 SQLite 数据库（WAL 模式已开），一个进程写批量事务期间另一个进程 INSERT 报 `database is locked`. sqlite3.OperationalError），且是立即失败而不是等待后成功。"
verify: "并发压写下 locked 异常为零；被等待的写者最终全部成功，无丢行。"
provenance:
  issue: "#5069"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

两个独立进程并发写同一个 SQLite 数据库（WAL 模式已开），一个进程写批量事务期间另一个进程 INSERT 报 `database is locked`（sqlite3.OperationalError），且是立即失败而不是等待后成功。

## Root Cause

WAL 只允许「一写多读」，**写写仍是互斥的**；Python sqlite3.connect 默认 busy timeout 为 0（不等待，立即抛错）。文档里常把「开了 WAL」记成「并发安全」，实际只解决读写并发，不解决写写并发。

## Fix

1. 每个写连接 `PRAGMA busy_timeout=30000`（或 connect(timeout=30)）；
2. 长批量写拆成小事务：每行 INSERT 后立即 commit，把持锁窗口从分钟级缩到毫秒级；
3. 用 `BEGIN IMMEDIATE` 提前拿写锁，避免事务中途才升级锁。

## Verification

并发压写下 locked 异常为零；被等待的写者最终全部成功，无丢行。
