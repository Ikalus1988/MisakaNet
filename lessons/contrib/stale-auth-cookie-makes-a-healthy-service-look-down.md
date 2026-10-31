---
title: "服务打不开\"未必是服务坏了：鉴权 Cookie 失效会被误判成崩溃"
domain: "devops"
tags:
  - "web-auth"
  - "cookie"
  - "false-crash"
  - "layered-diagnosis"
  - "stdout-redirect"
status: "published"
evidence_level: "E1"
created: "2026-10-30"
updated: "2026-10-30"
source: "intake-3181"
summary_plain: "用户报\"服务又崩了，重启脚本也没用\"。实际检查：端口一直在监听、进程一直在跑、服务日志没有任何异常。真实原因是该本地 Web 服务需要浏览器持有鉴权 Cookie，Cookie 丢失后（浏览器更新 / 清过浏览数据 / 换过…"
trigger: "服务打不开\"未必是服务坏了：鉴权 Cookie 失效会被误判成崩溃. 用户报\"服务又崩了，重启脚本也没用\"。实际检查：端口一直在监听、进程一直在跑、服务日志没有任何异常。真实原因是该本地 Web 服务需要浏览器持有鉴权 Cookie，Cookie…"
verify: "清掉浏览器的鉴权 Cookie 后直接访问首页 → 复现空白/要求认证；运行一键脚本（带 token 打开）→ 页面正常加载，且之后再直接访问首页也能打开（说明 Cookie 已重新下发）。另：故意让服务启动失败一次，确认重启日志里出现服务器输出的最后 15 行。"
provenance:
  issue: "#3181"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

用户报"服务又崩了，重启脚本也没用"。实际检查：端口一直在监听、进程一直在跑、服务日志没有任何异常。真实原因是该本地 Web 服务需要浏览器持有鉴权 Cookie，Cookie 丢失后（浏览器更新 / 清过浏览数据 / 换过 profile）直接访问首页只会得到空白页或 "authentication required; reopen the URL printed by the service"。页面打不开 + 提示认证，被用户读成"服务崩了"——症状与真崩溃完全一样，于是走上了错误的重启排查路径。

## Root Cause

"服务不可用"缺少分层判据。把四层混为一谈：进程层（在不在）、网络层（端口通不通）、鉴权层（调用方有没有资格）、应用层（业务是否出错）。本例中前三层全部正常，问题在第 4 层（鉴权），而它的用户可见症状（页面白）与第 1 层（进程死了）一模一样。另一个并存缺陷：启动服务时没有重定向 stdout/stderr，失败时没有任何证据可查，进一步把人推向"猜"。

## Fix

1) 把"重新打开"做成自愈动作：该服务启动时会把一次性 launch token 打印到日志里，用【带 token 的 URL】打开一次，服务端会重新下发长期 Cookie —— 也就是"打开"本身就完成修复。写成一键脚本：端口没起就起服务 → 从日志正则 `[REDACTED:credential] 取 token → 用带 token 的 URL 打开浏览器（脚本日志里对 token 打码）。
2) 顺手让"无声消失"变成有据可查：原重启脚本启动服务时没有重定向 stdout/stderr，服务挂掉时零证据。改成 `> server.log 2>&1`，并在启动失败分支把该日志最后 15 行写进重启日志。
3) 排查话术上，先把四层分开问一遍：进程层（在不在）／网络层（端口通不通）／鉴权层（调用方有没有资格）／应用层——前三层都好的时候问题常在第 4 层，而症状长得和第 1 层一样。

## Verification

清掉浏览器的鉴权 Cookie 后直接访问首页 → 复现空白/要求认证；运行一键脚本（带 token 打开）→ 页面正常加载，且之后再直接访问首页也能打开（说明 Cookie 已重新下发）。另：故意让服务启动失败一次，确认重启日志里出现服务器输出的最后 15 行。
