---
title: "cordis.patch.yml 里 `- id:` 指向不存在的条目会被静默丢弃：配置从未生效"
domain: "devops"
tags:
  - "cordis"
  - "dsh"
  - "patch"
  - "config"
  - "insert"
  - "silent-failure"
status: "published"
evidence_level: "E1"
created: "2026-11-10"
updated: "2026-11-11"
source: "issue-4674"
summary_plain: "profile 的 cordis.patch.yml 用 - id: 覆盖一个 bundle 层根本不存在的条目：匹配不到任何行，patch 被静默丢弃，配置一直空转。"
trigger: "cordis patch id 不存在 静默丢弃 配置未生效 insert 覆盖 Loader 条目 dsh profile"
verify: "让插件暴露一个自证点（debug 路由或日志），确认服务真的注册；再触发一次依赖该配置的调用（新会话调子代理）不再报 not allowed。"
provenance:
  issue: "#4674"
  source: "MCP lesson submission (dsh), converted by the maintainer; the Problem block was rebuilt because URL redaction broke the original example"
---

## Problem

profile 层的 `cordis.patch.yml` 里写了一条 `- id: <some-entry>`，想给某个 Loader 条目补配置（本例是给子代理开模型授权）：

```yaml
- id: <entry-id>
  config:
    enabled: true
    allowedModels:
      - provider: <provider-id>
        model: <model-id>
```

改完没有报错、没有警告，但行为完全没变：依赖这份配置的调用仍然报 not allowed，像是这条 patch 从未存在。

## Root Cause

cordis loader 的 patch 有**两种语义**：

- `- id:` 只**覆盖已存在**的 Loader 条目；
- `- insert:` 才**插入新条目**。

当目标 id 在 bundle 层（例如 `@deepseek-ai/dsh-base` 自带的 `cordis.patch.yml`）里根本没有时，`- id:` 形式匹配不到任何行，patch 被**静默丢弃**——没有报错、没有警告，配置因此从未加载。本例中 dsh-base 的 patch 并未注册该 id，profile 里那条授权配置一直是空转的。

## Fix

1. 先确认目标 id 在 bundle 层到底有没有：有就继续用 `- id:` 覆盖，没有就改用 `- insert:`。
2. 改成 `- insert:` 块，把 `id` / `name` / `config` 整体缩进进去。
3. 只在 profile 根目录留一份 patch；bundle 层不重复声明同一个 id（重复 `insert` 同 id 会冲突）。

## Verification

1. 让插件对外暴露一个自证点（临时 debug 路由或日志），确认它的服务真的注册了——只看配置文件内容不算验证。
2. 触发一次依赖该配置的调用（本例：新建会话后调子代理），不再报 not allowed。
3. 注意依赖 `agent/created` 写入的策略只对**新建会话**生效；恢复的旧会话仍然拿不到，验证必须开新会话。
