---
title: "评估未知 Windows 安装包时，用「安装器文件名」精确短语做公开情报检索，会把正式产品误判为「未公开发布」。 Root Cause 安装器文件名（如 Ins"
domain: "windows"
tags:
  - "windows"
  - "ins"
status: "published"
evidence_level: "E1"
created: "2026-11-16"
updated: "2026-11-16"
source: "intake-4723"
summary_plain: "评估未知 Windows 安装包时，用「安装器文件名」精确短语做公开情报检索，会把正式产品误判为「未公开发布」。"
trigger: "评估未知 Windows 安装包时，用「安装器文件名」精确短语做公开情报检索，会把正式产品误判为「未公开发布」。 Root Cause 安装器文件名（如 Ins. 评估未知 Windows 安装包时，用「安装器文件名」精确短语做公开情报检索，会把正式产品误判为「未公开发布」。"
verify: "同一安装包复测：精确名 \"Install-EigenEngineeringAgent\" 零结果；宽搜 \"Siemens Eigen Engineering Agent TIA Portal\" 命中 siemens.com 产品页、news.siemens.com 发布稿、docs.tia.siemens.cloud…"
provenance:
  issue: "#4723"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

评估未知 Windows 安装包时，用「安装器文件名」精确短语做公开情报检索，会把正式产品误判为「未公开发布」。

## Root Cause

安装器文件名（如 Install-XXX-china.exe）是构建产物名，厂商官网/新闻稿/文档站使用的是带空格的品牌名（如 "XXX Agent"）。精确短语搜索（尤其带连字符）命中率为零，被错误解释为「全网无足迹=未公开/内部产品」，并写进了给用户的评估结论。实际用「品牌词(空格分词)+厂商名+品类词」宽搜，一次就命中官网产品页、新闻稿和官方文档站三源。

## Fix

1. 公开情报判断不得只用文件名/哈希精确搜索；至少跑两组查询：精确名（哈希/文件名）+ 品牌宽搜（版本资源里的 ProductName/WindowTitle 拆词 + 厂商 + 品类词，如 "XXX Agent" + Siemens + TIA）。
2. 优先从二进制内部提取「人类品牌词」（版本资源 FileDescription/ProductName、UI 窗口标题字符串、PDB 路径里的项目名），而不是用打包文件名当搜索词。
3. 「无公开足迹」结论必须至少两组不同构造的查询均为零结果才允许写下，并注明查询词可复现。

## Verification

同一安装包复测：精确名 "Install-EigenEngineeringAgent" 零结果；宽搜 "Siemens Eigen Engineering Agent TIA Portal" 命中 siemens.com 产品页、news.siemens.com 发布稿、docs.tia.siemens.cloud 中文文档——三源交叉证实产品公开存在，此前「未公开发布」结论被推翻并已在回复中更正。
