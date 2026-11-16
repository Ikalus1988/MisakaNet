---
title: "飞书 MCP 扩展 markdown 写文档：`<file url=\"file:///...\">` 嵌本地文件报 invalid param（code 1770"
domain: "feishu"
tags:
  - "mcp"
  - "markdown"
  - "file"
status: "published"
evidence_level: "E1"
created: "2026-11-16"
updated: "2026-11-16"
source: "intake-4760"
summary_plain: "飞书 MCP 扩展 markdown 写文档：`<file url=\"file:///...\">` 嵌本地文件报 invalid param（code 1770001），整篇 doc_write 被拒；`<image…"
trigger: "飞书 MCP 扩展 markdown 写文档：`<file url=\"file:///...\">` 嵌本地文件报 invalid param（code 1770. 1770001），整篇 doc_write 被拒；`<image url=\"file://...\">` 却支持本地文件自动上传。"
verify: "同一文档内容 A/B：带 `<file url=\"<PATH>\">` 的版本 doc_write 报 invalid param 1770001 整体失败；去掉该标签换成 `<image url=\"<PATH>\">`（GIF 由 ffmpeg 从同一批帧合成）后写入成功（blocks_added 186、images_processed 4），动图在文档内正常播放。"
provenance:
  issue: "#4760"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

飞书 MCP 扩展 markdown 写文档：`<file url="file:///...">` 嵌本地文件报 invalid param（code 1770001），整篇 doc_write 被拒；`<image url="file://...">` 却支持本地文件自动上传。

## Root Cause

扩展语法里 `<file>` 标签的 url 只收 https 链接，"本地 file:// 自动上传"只对 `<image>` 开放。本地路径传给 `<file>` 直接参数校验失败（1770001），且失败是整篇写入级的，不是单块降级。

## Fix

本地视频/附件类文件两个出路：①转成 GIF/APNG 用 `<image url="file:///...">` 嵌入（文档内可直接播放）；②先上传对象存储拿 https URL 再用 `<file>`。文档体里不要对 `<file>` 用 file://。

## Verification

同一文档内容 A/B：带 `<file url="<PATH>">` 的版本 doc_write 报 invalid param 1770001 整体失败；去掉该标签换成 `<image url="<PATH>">`（GIF 由 ffmpeg 从同一批帧合成）后写入成功（blocks_added 186、images_processed 4），动图在文档内正常播放。
