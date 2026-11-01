---
title: "没有 git 的机器装 GitHub-only 的 DSH 插件：gh-proxy 下 zip 再打 tgz"
domain: "devops"
tags:
  - "dsh"
  - "github"
  - "gh-proxy"
  - "no-git"
  - "tgz"
  - "china-network"
  - "offline-install"
status: "published"
evidence_level: "E1"
created: "2026-11-01"
updated: "2026-11-01"
source: "intake-4244"
summary_plain: "目标机器没装 git，插件只在 GitHub 上有（没发 npm），dsh plugin add github:owner/repo 直接失败；国内网络下 github 直连也常超时。"
trigger: "没有 git 的机器装 GitHub-only 的 DSH 插件：gh-proxy 下 zip 再打 tgz. 目标机器没装 git，插件只在 GitHub 上有（没发 npm），dsh plugin add github:owner/repo 直接失败；国内网络下 github…"
verify: "安装后 node_modules 里有该包且含构建产物；重启后插件加载。"
provenance:
  issue: "#4244"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

目标机器没装 git，插件只在 GitHub 上有（没发 npm），dsh plugin add github:owner/repo 直接失败；国内网络下 github 直连也常超时。

## Root Cause

dsh 的 github: 依赖走 git clone / codeload，本机无 git 时不可用；跨境访问 github 还可能被阻断。

## Fix

用 gh-proxy 下载源码 zip（`https://gh-proxy.com/https://github.com/<owner>/<repo>/archive/refs/heads/<branch>.zip`）→ 解压 → tar 打成 .tgz → pnpm add file:./pkg.tgz。前提：仓库已提交构建产物，且 package.json 不带 prepare 脚本（否则装的时候会跑构建而失败）。

## Verification

安装后 node_modules 里有该包且含构建产物；重启后插件加载。
