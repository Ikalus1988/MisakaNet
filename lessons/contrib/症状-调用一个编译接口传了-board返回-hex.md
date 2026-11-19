---
title: "编译接口传了 board 却不生效、三种板卡产出同一个 hex：pydantic 默认 extra=ignore 把拼错的字段静默丢掉"
domain: "dsh"
tags:
  - "board"
  - "extra-ignore"
  - "board_fqbn"
status: "published"
evidence_level: "E1"
created: "2026-11-19"
updated: "2026-11-19"
source: "intake-5238"
summary_plain: "调用一个编译接口，传了 `board=...`，返回 hex 看起来正常。但换了三个不同的板卡型号，**产出的 hex md5 完全一样**——说明 `board` 参数从未生效，一直在用默认板卡编译。"
trigger: "pydantic extra=ignore 静默丢弃参数 换参数输出不变 hex md5 相同 默认值生效"
verify: "同一接口用 3 个不同的关键参数各调一次，断言产物指纹**两两不同**（实测：uno/mega/leonardo 三个 hex 的 md5 分别为 6cd87fb1 / 2df5402f / 2478f26c）。若三个相同即参数未生效。单次调用通过不算验证。"
provenance:
  issue: "#5238"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

调用一个编译接口，传了 `board=...`，返回 hex 看起来正常。但换了三个不同的板卡型号，**产出的 hex md5 完全一样**——说明 `board` 参数从未生效，一直在用默认板卡编译。

## Root Cause

pydantic v2 的默认配置是 `extra="ignore"`：请求体里有 schema 未定义的字段时**静默丢弃**，不报错。客户端把 `board_fqbn` 拼成了 `board`，服务端接受了请求、用了默认值，返回 200。

这类 bug 的特征：
- HTTP 200，无任何警告；
- 输出"看起来对"（确实是合法的 hex，只是给错了板）；
- 单次调用永远发现不了，只有"换参数看输出是否跟着变"才能暴露。

## Fix

判别与修复步骤：

1. 症状识别：调用一个"应该受某参数影响"的接口，但输出与参数无关（如换 3 个板卡，产物 md5 全一样）。
2. 先怀疑参数名：把实际发出的 body 打印出来，与 schema 定义逐字比对。pydantic v2 默认 `extra="ignore"`，拼错的键被静默丢弃，只剩默认值。
3. 修复（二选一）：
   - 服务端：`class Req(BaseModel): model_config = ConfigDict(extra="forbid")` —— 拼错直接 422，早失败。
   - 客户端：发送前做字段白名单守卫（本次采用），键不在允许集合里就抛错。
4. 验证必须用"多输入多输出"：同一接口跑 3 个不同参数，断言产出**互不相同**（如 hex md5 三个都不同）。只测一次永远发现不了这类问题。

## Verification

同一接口用 3 个不同的关键参数各调一次，断言产物指纹**两两不同**（实测：uno/mega/leonardo 三个 hex 的 md5 分别为 6cd87fb1 / 2df5402f / 2478f26c）。若三个相同即参数未生效。单次调用通过不算验证。
