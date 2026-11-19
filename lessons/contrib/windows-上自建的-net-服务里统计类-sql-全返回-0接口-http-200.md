---
title: "Windows 上自建的 .NET 服务里统计类 SQL 全返回 0，接口 HTTP 200 且不报错，但用同一个 .db 文件在外部 sqlite3/pyth"
domain: "windows"
tags:
  - "factory_ledger.db"
  - "winsqlite3.dll"
  - "localtime"
status: "published"
evidence_level: "E1"
created: "2026-11-19"
updated: "2026-11-19"
source: "intake-5159"
summary_plain: "Windows 上自建的 .NET 服务里统计类 SQL 全返回 0，接口 HTTP 200 且不报错，但用同一个 .db 文件在外部 sqlite3/python 里跑同样的 SQL 能算出几十条。"
trigger: "sqlite date now localtime returns null winsqlite3 count 0 但外部 sqlite 有数据 统计全是0"
verify: "修前外部 python 算 62 行、接口返回 0；修后接口返回 `62 / 0 / 85`，与外部 python 同条件逐项相等。 修后用同一 SQL 在接口与外部 sqlite 各跑一次，两边数字相等（62/0/85）"
provenance:
  issue: "#5159"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

Windows 上自建的 .NET 服务里统计类 SQL 全返回 0，接口 HTTP 200 且不报错，但用同一个 .db 文件在外部 sqlite3/python 里跑同样的 SQL 能算出几十条。

症状：每天早上用 `SELECT COUNT(*) ... WHERE date(due_col) < date('now','localtime')` 算逾期行数并推送。某天消息写「已逾期 0 行 / 今天到期 0 行 / 三日内到期 0 行」，用户质疑；用 python 只读打开同一个 `factory_ledger.db`、按服务里完全相同的 WHERE 条件算，得到 alive 579 行、逾期 62 行。接口返回 `{overdue:0,dueToday:0,dueSoon:0}`、状态 200、日志无异常。

## Root Cause

服务通过 P/Invoke 加载 Windows 自带的 `winsqlite3.dll`（回落才用随包的 e_sqlite3），**该构建不支持 `localtime` 日期修饰符**：`date('now','localtime')` 返回 NULL，`date(col) < NULL` 恒为 NULL、`COUNT` 全落空为 0；取标量的封装对 NULL 直接返回 0，于是整条链路"成功"地给出 0，没有任何异常。

## Fix

不在 SQL 里用 `localtime`，把"今天"交给宿主语言算再作为参数传入：`var today = DateTime.Now.ToString("yyyy-MM-dd")`，SQL 用 `date(col) < ?` / `= ?` / `<= date(?, '+3 day')`；库内其它 `date('now'...)` 一并替换。

## Verification

修前外部 python 算 62 行、接口返回 0；修后接口返回 `62 / 0 / 85`，与外部 python 同条件逐项相等。

修后用同一 SQL 在接口与外部 sqlite 各跑一次，两边数字相等（62/0/85）
