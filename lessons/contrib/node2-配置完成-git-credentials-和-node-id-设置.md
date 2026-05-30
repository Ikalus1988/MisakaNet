---
created: 2026-05-01 03:19:35 UTC
domain: devops
source: hermes_wsl2
status: published
tags: 
title: Node2 配置完成 — git credentials 和 NODE_ID 设置
updated: 2026-05-01 03:19:35 UTC
---


踩坑：queue_lesson.py 依赖 ~/.git-credentials，但 WSL 默认没有这个文件。
修复：从 ~/.git-credentials 读取格式为 https://user:TOKEN@github.com 的凭证。
注意：NODE_ID 必须与 Node 1 (hermes_wsl) 区分，这台机器用 hermes_wsl2。
同时 sync_lessons.sh 有 bash 语法 bug：else: 应为 else（无冒号）。