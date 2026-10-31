---
title: "docker compose restart 不重建镜像：改了代码重启后行为还是旧的"
domain: "devops"
tags:
  - "docker"
  - "docker-compose"
  - "restart"
  - "rebuild"
  - "bind-mount"
  - "deployment"
  - "nas"
status: "published"
evidence_level: "E1"
created: "2026-10-31"
updated: "2026-10-31"
source: "intake-4155"
summary_plain: "服务端代码改了，`docker compose restart` 之后行为完全没变，日志还是旧文案，看着像代码没生效或者文件没上传。"
trigger: "docker compose restart 不重建镜像：改了代码重启后行为还是旧的. 服务端代码改了，`docker compose restart` 之后行为完全没变，日志还是旧文案，看着像代码没生效或者文件没上传。"
verify: "改一行日志文案，restart 后在容器里 `grep` 到新文案；`docker compose config` 确认 volumes 含源码目录。"
provenance:
  issue: "#4155"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

服务端代码改了，`docker compose restart` 之后行为完全没变，日志还是旧文案，看着像代码没生效或者文件没上传。

## Root Cause

两种部署形态完全不同：

| 形态 | 代码在哪 | 改代码要做什么 |
|---|---|---|
| 镜像模式（仓库 Dockerfile COPY） | 打进镜像层 | `up -d --build` |
| 挂载模式（宿主目录挂进容器） | 宿主机目录 | `restart` 就够 |

restart 只重启进程，不重新 build，也不重新读镜像里的代码。给部署建议前没先看对方实际的 compose，本地文件早就和 NAS 上那份分叉了（端口 8787 / 18787 也是这么发现的）。

## Fix

先判形态，再决定命令：

```bash
docker inspect bms-server --format '{{json .Mounts}}' | python3 -m json.tool

## Verification

改一行日志文案，restart 后在容器里 `grep` 到新文案；`docker compose config` 确认 volumes 含源码目录。
