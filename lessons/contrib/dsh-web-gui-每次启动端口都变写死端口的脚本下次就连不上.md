---
title: "DSH Web GUI 每次启动端口都变，写死端口的脚本下次就连不上"
domain: "devops"
tags:
  - "dsh"
  - "port"
  - "http"
  - "localhost"
  - "scripting"
  - "random-port"
status: "published"
evidence_level: "E1"
created: "2026-11-02"
updated: "2026-11-02"
source: "intake-4246"
summary_plain: "用脚本或插件去探测本机 DSH 的 HTTP 接口（例如插件的 /dsh-market/* 路由）时，把 http://127.0.0.1:PORT 写死，下次启动后全部失败，表现为连接被拒。"
trigger: "DSH Web GUI 每次启动端口都变，写死端口的脚本下次就连不上. 用脚本或插件去探测本机 DSH 的 HTTP 接口（例如插件的 /dsh-market/* 路由）时，把 http://127.0.0.1:PORT…"
verify: "重启宿主后脚本仍能连上，不再出现 ECONNREFUSED。"
provenance:
  issue: "#4246"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

用脚本或插件去探测本机 DSH 的 HTTP 接口（例如插件的 /dsh-market/* 路由）时，把 http://127.0.0.1:PORT 写死，下次启动后全部失败，表现为连接被拒。

## Root Cause

DSH 每次启动随机选择监听端口，不是固定端口，端口只体现在运行时的注入变量/GUI 地址里。

## Fix

不要写死端口：每次从运行时环境读取当前 GUI/服务地址；排查时先枚举进程的监听端口再拼 URL。

## Verification

重启宿主后脚本仍能连上，不再出现 ECONNREFUSED。
