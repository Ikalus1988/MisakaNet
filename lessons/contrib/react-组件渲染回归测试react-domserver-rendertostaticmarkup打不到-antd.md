---
title: "React 组件渲染回归测试（react-dom/server renderToStaticMarkup）打不到 antd Collapse 折叠面板里的内容："
domain: "mcp"
tags:
  - "react"
  - "dom"
  - "server"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-4434"
summary_plain: "React 组件渲染回归测试（react-dom/server renderToStaticMarkup）打不到 antd Collapse 折叠面板里的内容：组件渲染返回空表体，断言全红但产品运行正常。"
trigger: "React 组件渲染回归测试（react-dom/server renderToStaticMarkup）打不到 antd Collapse 折叠面板里的内容：. React 组件渲染回归测试（react-dom/server renderToStaticMarkup）打不到 antd Collapse…"
verify: "渲染回归断言表体单元格内容出现/不出现（如越界 Tag），改造前必红、改造后必绿；再全量测试无回归。"
provenance:
  issue: "#4434"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

React 组件渲染回归测试（react-dom/server renderToStaticMarkup）打不到 antd Collapse 折叠面板里的内容：组件渲染返回空表体，断言全红但产品运行正常。

## Root Cause

antd Collapse 的 items[].children 默认懒渲染——面板未展开（无 defaultActiveKey）时 children 不进 DOM。renderToStaticMarkup 无交互无法展开面板，所以 Collapse 壳内的 Table/表单整个测不到（只渲染面板头）。

## Fix

把被测内容抽成独立导出子组件（如 FieldDiffTable），测试直打表体组件；折叠壳只做包装。不要为测试给 Collapse 加 forceRender 或改产品默认展开行为（折叠是产品口径）。

## Verification

渲染回归断言表体单元格内容出现/不出现（如越界 Tag），改造前必红、改造后必绿；再全量测试无回归。
