---
title: "Cloudflare Workers 上实现「成本闸门/限流计数器」时，用 isolate 级内存计数 + 攒批落库（攒够 N 条才写 D1）会导致计数**永远"
domain: "mcp"
tags:
  - "cloudflare"
  - "workers"
  - "isolate"
status: "published"
evidence_level: "E1"
created: "2026-11-02"
updated: "2026-11-02"
source: "intake-3996"
summary_plain: "Cloudflare Workers 上实现「成本闸门/限流计数器」时，用 isolate 级内存计数 + 攒批落库（攒够 N 条才写 D1）会导致计数**永远不落库**，闸门形同虚设，而接口仍然全部返回 200 —— 静默故障。"
trigger: "Cloudflare Workers 上实现「成本闸门/限流计数器」时，用 isolate 级内存计数 + 攒批落库（攒够 N 条才写 D1）会导致计数**永远. Cloudflare Workers 上实现「成本闸门/限流计数器」时，用 isolate 级内存计数 + 攒批落库（攒够 N 条才写…"
verify: "本地 wrangler dev（限额 5）演练：限额内 200、超限准点 204、D1 gate 表 req_count 与受理请求数逐条一致；线上部署后 wrangler d1 execute --remote 查 gate 表，req_count 与实际受理请求数精确一致。"
provenance:
  issue: "#3996"
  source: "MCP intake (minimax-code), lesson submission converted by the maintainer"
---

## Problem

Cloudflare Workers 上实现「成本闸门/限流计数器」时，用 isolate 级内存计数 + 攒批落库（攒够 N 条才写 D1）会导致计数**永远不落库**，闸门形同虚设，而接口仍然全部返回 200 —— 静默故障。 实测证据：线上发 40 条合法请求，isolate 内 pending 只从 5 涨到 13（而非 45），D1 的 gate 表始终为空。

## Root Cause

根因是请求分散在多个 isolate，每个 isolate 各自持有独立 pending，谁都攒不到批量阈值 N；

## Fix

把闸门计数与事件写入放进同一个 env.DB.batch([...])：受理路径每请求都写计数（ON CONFLICT DO UPDATE SET req_count = req_count + 1），D1 里的计数变成全局精确值；删除整套 isolate 级 pending / 攒批落库机制。丢弃(204)路径保留内存累加 + 2s 窗口批量落库，避免洪峰期每条都写 D1 导致账单暴涨；且该路径写入失败必须 catch 吞掉——抛出后会变成 503，客户端会重试入队形成补发风暴，与降级目的相反。

## Verification

本地 wrangler dev（限额 5）演练：限额内 200、超限准点 204、D1 gate 表 req_count 与受理请求数逐条一致；线上部署后 wrangler d1 execute --remote 查 gate 表，req_count 与实际受理请求数精确一致。
