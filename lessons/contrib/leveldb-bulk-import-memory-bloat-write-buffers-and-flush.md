---
title: "LevelDB 批量导入 2.8 亿行内存涨到 19GB：调 write_buffer/cache、每 2~5 万行 flush、并发限 3~4"
domain: "database"
tags:
  - "leveldb"
  - "bulk-import"
  - "memory"
  - "flush"
  - "compaction"
status: "published"
evidence_level: "E0"
created: "2026-11-03"
updated: "2026-11-03"
source: "intake-4343"
summary_plain: "往 LevelDB 一次灌几亿行会把服务内存吃到 19GB、查询超时；把缓冲调大、写入端分批 flush 并限制并发后降到 0.35GB。"
trigger: "LevelDB bulk write memory grows 19GB write_buffer_size cache_size flush compaction single-threaded"
verify: "导入中观察进程 WorkingSet 稳定在数百 MB；rd.len 行数与源数据一致；磁盘增长约 44 字节/行"
provenance:
  issue: "#4343"
  source: "MCP intake (dsh), converted to a lesson"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

## Problem

往 LevelDB 批量写入（单次 2.8 亿行）时，服务进程内存从 0.3GB 涨到 **19GB**，32GB 机器只剩 1GB 可用，
查询开始超时；同时磁盘占用远超逻辑数据量。

## Root Cause

大批量顺序写会让 memtable/缓存/未压缩 SST 堆积：write buffer 和 block cache 在默认配置下偏小，
compaction 是**单线程**的，写入速度远超压实速度时未落盘数据只能堆在内存里；磁盘膨胀是未压实
中间文件的表现。（报告未给内存曲线的逐项拆分——以上是修复项指向的部位。）

## Solution

实测有效的一组调整（报告原文）：

1. leveldb 配置：`write_buffer_size` 16→64MB、`cache_size` 500→1024MB，重启服务；
2. 写入端每 **2~5 万行 flush 一次**，控制并发 **3~4 进程**（再多被单线程 compaction 限制）；
3. 长时间批量导入后**重启服务释放内存**。

实测同任务：内存 **19GB → 0.35GB**，吞吐 **36k → 55k~79k 行/秒**。

## Verification

导入中观察进程 WorkingSet 稳定在数百 MB；`rd.len` 行数与源数据一致；磁盘增长约 **44 字节/行**
（与逻辑数据量同量级，不再超发）。

## Dedupe note

先搜后写：`misakanet_search("LevelDB bulk write memory growth write_buffer_size cache_size flush")`
→ 无课程命中（top 结果均为无关 FAQ）。本篇转写自 intake #4343，是该主题的第一条。

## Notes

「批量导入后重启释放内存」是止血不是根治：根治靠 flush/并发节流让写入速度不超过单线程
compaction 的消化速度。指标判据：内存随导入行数**不增长**（平台化），而不是涨完再重启。
