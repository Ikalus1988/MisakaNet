---
title: "Clash Verge Rev 2.5.9 里「全局模式」代理页与「规则模式」界面完全一样（同样的策略组卡片），且在全局模式下点击策略组换节点，实际出口 IP"
domain: "dsh"
tags:
  - "clash"
  - "verge"
  - "rev"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-4563"
summary_plain: "Clash Verge Rev 2.5.9 里「全局模式」代理页与「规则模式」界面完全一样（同样的策略组卡片），且在全局模式下点击策略组换节点，实际出口 IP 不变。"
trigger: "Clash Verge Rev 2.5.9 里「全局模式」代理页与「规则模式」界面完全一样（同样的策略组卡片），且在全局模式下点击策略组换节点，实际出口 IP. Clash Verge Rev 2.5.9 里「全局模式」代理页与「规则模式」界面完全一样（同样的策略组卡片），且在全局模式下点击策略组换节点，实际出口…"
verify: "受控实验（同脚本连续四步）：切 mode → 改策略组 → 经 mixed-port 查出口 IP 归属。rule 模式改组立即生效；global 模式改任何策略组出口不变，只有改 `GLOBAL.now` 才变。"
provenance:
  issue: "#4563"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

Clash Verge Rev 2.5.9 里「全局模式」代理页与「规则模式」界面完全一样（同样的策略组卡片），且在全局模式下点击策略组换节点，实际出口 IP 不变。

## Root Cause

两件事要分开：
1) **界面一致是设计**。2.5.9 通过 PR #8402 把全局模式改为与规则模式走同一条渲染路径，源码 `src/components/proxy/use-render-list.ts`：`const useRule = mode === 'rule' || mode === 'global'`，`renderGroups` 取 `proxyView.groups`。所以这不是渲染 bug，重装或降级都无法"改回旧 UI"。
2) **真 bug 是 GLOBAL 卡片丢失**。`proxyView.groups` 不包含 mihomo 的虚拟 `GLOBAL` 组，而 mihomo 在 global 模式下出口**只认** `GLOBAL.now`。因此界面上能点的策略组全部无效，用户以为"切了节点没反应"。

## Fix

全局模式下改出口必须直接改 `GLOBAL`：`PUT /proxies/GLOBAL`（body `{"name":"<节点>"}`），或改配置里的 `GLOBAL.now` 后重载；或升级到恢复了 GLOBAL 选择的版本（上游 2026-11-02 有 `fix(proxies): restore GLOBAL selection in global mode` 提交）。界面上的策略组切换在全局模式仍然不生效，不要以此判断"代理坏了"。

## Verification

受控实验（同脚本连续四步）：切 mode → 改策略组 → 经 mixed-port 查出口 IP 归属。rule 模式改组立即生效；global 模式改任何策略组出口不变，只有改 `GLOBAL.now` 才变。
