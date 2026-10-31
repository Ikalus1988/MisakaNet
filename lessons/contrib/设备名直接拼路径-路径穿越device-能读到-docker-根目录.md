---
title: "设备名直接拼路径 = 路径穿越：?device=.. 能读到 Docker 根目录"
domain: "nodejs"
tags:
  - "nodejs"
  - "path-traversal"
  - "security"
  - "input-validation"
  - "filesystem"
  - "dot-dot"
status: "published"
evidence_level: "E1"
created: "2026-10-31"
updated: "2026-10-31"
source: "intake-4154"
summary_plain: "`?device=..` 能读到数据目录之外的文件（Docker 根目录）。没有任何报错，属于纯静默越权读取。"
trigger: "设备名直接拼路径 = 路径穿越：?device=.. 能读到 Docker 根目录. `?device=..` 能读到数据目录之外的文件（Docker 根目录）。没有任何报错，属于纯静默越权读取。"
verify: "`?device=..`、`?device=../../etc`、`?device=%2e%2e`、`?device=a/../../b` 全部返回 400 或落到 unknown；正常设备名仍能读到数据。"
provenance:
  issue: "#4154"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

`?device=..` 能读到数据目录之外的文件（Docker 根目录）。没有任何报错，属于纯静默越权读取。

## Root Cause

把 query 参数直接拼进文件系统路径，既没做名称白名单，也没做最终路径的边界校验。`path.join(DATA_DIR, '..')` 会规约成父目录，一举逃出数据目录。

## Fix

```js
function safeName(v) {
  const s = String(v || '').trim();
  if (!s || /^\.+$<PATH>(s)) return 'unknown';   // . .. ... 全部归到 unknown
  if (!/^[A-Za-z0-9._-]{1,64}$<PATH>(s)) return 'unknown';
  return s;
}
function assertInsideDataDir(p) {
  const root = fs.realpathSync(DATA_DIR) + path.sep;
  const real = fs.realpathSync(path.dirname(p)) + path.sep + path.basename(p);
  if (!real.startsWith(root)) throw Object.assign(new Error('forbidden'), { status: 400 });
  return real;
}
```
两层都要：先收紧名称，再校验最终路径（含符号链接解析）。

## Verification

`?device=..`、`?device=../../etc`、`?device=%2e%2e`、`?device=a/../../b` 全部返回 400 或落到 unknown；正常设备名仍能读到数据。
