---
title: "飞书文档被分享为「只读、禁止下载/复制」时，文档内图片无法通过任何 OpenAPI 拿到：drive medias batch_get_tmp_download"
domain: "feishu"
tags:
  - "openapi"
  - "drive"
  - "medias"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-4485"
summary_plain: "飞书文档被分享为「只读、禁止下载/复制」时，文档内图片无法通过任何 OpenAPI 拿到：drive medias batch_get_tmp_download_url 返回空数组、medias/files download 返回…"
trigger: "飞书文档被分享为「只读、禁止下载/复制」时，文档内图片无法通过任何 OpenAPI 拿到：drive medias batch_get_tmp_download. 飞书文档被分享为「只读、禁止下载/复制」时，文档内图片无法通过任何 OpenAPI 拿到：drive medias…"
verify: "同一 token：curl medias download=403、export=no permission；CDP 页面内 fetch 同一图片 URL 返回 image/* 且 >5KB 即算成功。"
provenance:
  issue: "#4485"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

飞书文档被分享为「只读、禁止下载/复制」时，文档内图片无法通过任何 OpenAPI 拿到：drive medias batch_get_tmp_download_url 返回空数组、medias/files download 返回 403、export_tasks 返回 no permission(1069902)，drive copy 也 forbidden。连引用的 pdf/pptx 附件同样 403。

## Root Cause

图片/附件存在文档作者个人云盘（box file），API 层面的文件级 ACL 要求下载权限；文档的「禁止下载」分享设置会同时封锁 medias 下载、export、copy 三条路。自建应用 OAuth scope 即使加上 docs:document:export/drive:export:readonly 也无济于事，因为卡的是文件级权限不是 scope。

## Fix

借用户浏览器登录态在页面上下文里取图：复制 Chrome 的 Cookies+Local State 到独立 user-data-dir（新版 Chrome 禁止对默认 profile 开 --remote-debugging-port），启动 chrome --user-data-dir=副本 --remote-debugging-port=9222，让用户在该窗口完成一次 SSO；然后用 CDP 打开文档页，Network.enable 监听 Image 响应 URL + 滚动懒加载容器（feishu 文档滚动容器是 .bear-web-x-container），把 internal-api-drive-stream 的图片 URL 在页面内 fetch 成 base64 保存。30 张图可回收 20+ 张。

## Verification

同一 token：curl medias download=403、export=no permission；CDP 页面内 fetch 同一图片 URL 返回 image/* 且 >5KB 即算成功。
