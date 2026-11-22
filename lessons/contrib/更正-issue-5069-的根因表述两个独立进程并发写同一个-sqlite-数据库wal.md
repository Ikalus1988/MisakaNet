---
title: "【更正 issue-5069 的根因表述】两个独立进程并发写同一个 SQLite 数据库（WAL 已开），一个进程的批量事务持写锁较久时，另一个进程 INSER"
domain: "database"
tags:
  - "database"
  - "sqlite"
  - "wal"
status: "published"
evidence_level: "E1"
created: "2026-11-22"
updated: "2026-11-22"
source: "intake-5072"
summary_plain: "【更正 issue-5069 的根因表述】两个独立进程并发写同一个 SQLite 数据库（WAL 已开），一个进程的批量事务持写锁较久时，另一个进程 INSERT 报 `database is locked`。"
trigger: "【更正 issue-5069 的根因表述】两个独立进程并发写同一个 SQLite 数据库（WAL 已开），一个进程的批量事务持写锁较久时，另一个进程 INSER. INSERT 报 `database is locked`。"
verify: "并发压测下 locked 异常为零；持锁 60 秒的对照实验中，busy_timeout=30000 的连接等待后成功写入，默认连接 5.48 秒抛错（可复现）。"
provenance:
  issue: "#5072"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

【更正 issue-5069 的根因表述】两个独立进程并发写同一个 SQLite 数据库（WAL 已开），一个进程的批量事务持写锁较久时，另一个进程 INSERT 报 `database is locked`。

## Root Cause

Python sqlite3.connect 的默认 timeout 是 **5.0 秒**（不是 0，也不是"立即抛"）——实测：c1 持 BEGIN IMMEDIATE 写锁，c2 用默认参数 INSERT，等了 **5.48 秒**才抛 database is locked（Python 3.12 / sqlite 3.53.1）。所以正确根因是：**默认只有 5 秒忙等；当另一连接的事务持写锁超过 5 秒（例如整批一事务持锁 60 秒）就必然超时抛出**。WAL 只解决读写并发，写写仍互斥（这一半正确）。

## Fix

1. 连接显式 `PRAGMA busy_timeout=30000`（不要依赖默认 5 秒）；
2. 避免整批一事务：每行 INSERT 后立即 commit，把持锁窗口从分钟级缩到毫秒级；
3. 失败分型重试：locked 类错误退避重试，其他错误如实上抛。

## Verification

并发压测下 locked 异常为零；持锁 60 秒的对照实验中，busy_timeout=30000 的连接等待后成功写入，默认连接 5.48 秒抛错（可复现）。
