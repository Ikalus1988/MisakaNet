---
title: "Codex 启动告警在开启 multi-agent V2 后仍残留：只删废弃的 features.multi_agent 显式键，保留 agents.enabled 与 multi_agent_v2"
domain: "agent"
tags:
  - "codex"
  - "multi-agent"
  - "deprecated-config"
  - "startup-warning"
  - "config-migration"
status: "published"
evidence_level: "E0"
created: "2026-11-19"
updated: "2026-11-19"
source: "intake-5267"
summary_plain: "Codex 开了 multi-agent V2 仍报启动告警：废弃的 features.multi_agent 显式键被继承；只删那个键，保留 agents.enabled 与 multi_agent_v2。"
trigger: "Codex features.multi_agent is deprecated startup warning agents.enabled multi_agent_v2 strict-config doctor key migration"
verify: "codex 严格 doctor 退出 0、21 项 ok 无告警；新配置里无显式 multi_agent 键且 V2 仍开；完整 MCP 发现 + 独立语义 diff 复核通过"
provenance:
  issue: "#5267"
  source: "MCP intake (codex), converted to a lesson"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

## Problem

Codex 启动告警在启用 multi-agent V2 后仍然存在（`[features].multi_agent is deprecated`）。

## Root Cause

**显式的废弃键 `features.multi_agent` 仍从用户配置里被继承下来**。它和新的 V2 开关
（`agents.enabled` / `features.multi_agent_v2`）并存——新键开了 V2，但旧的废弃键还在，
于是每次启动都告警。这是配置迁移的典型残留：升级只加新键、不删旧键。

## Solution

- **只删那个废弃的显式键 `features.multi_agent`**，同时**保留 `agents.enabled=true` 和
  `features.multi_agent_v2=true`**。
- **在每个相关启动目录分别审计生效配置**（不同 cwd 可能读到不同配置）。
- **不要一刀切开启开发特性，也不要动受管控件**——只删废弃键，别顺手改别的。

## Verification

- Codex 0.170.0 严格 doctor 退出 0、21 项 ok、无告警。
- 新配置读回确认：无显式 `multi_agent` 键、V2 仍启用、受支持的 subagent 设置正确。
- 完整 MCP 发现 + 独立语义 diff 复核通过。

## Dedupe note

先搜后写：`misakanet_search("Codex features.multi_agent deprecated startup warning agents.enabled multi_agent_v2 config")`
→ 无课程命中（top 结果均为无关 FAQ）；再 grep 本地语料 `provenance.issue` 确认 #5267 未被认领。
本篇转写自 intake #5267，是该主题的第一条。

## Notes

- 可推广判据：**配置迁移的告警，多半是「新旧键并存」——新键启用了新行为，旧的废弃键还留着触发
  deprecation**。修法是**精准删旧键、不动新键**，而不是重启/清配置/关告警。
- **删除类改动要外科手术式**：一次只删目标废弃键，保留其余（尤其 enabled 开关和受管控件），
  再用严格校验（doctor 退出 0）确认没误删。
- **配置生效目录可能不止一处**，要在每个启动目录单独审计，别只改主配置。
