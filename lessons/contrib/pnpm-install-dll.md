---
title: "pnpm install 撞上运行中进程的 DLL 锁：靠目录改名绕过，别删文件"
domain: "devops"
tags:
  - "windows"
  - "pnpm"
  - "dll"
  - "electron"
  - "sharp"
  - "file-lock"
status: "published"
evidence_level: "E1"
created: "2026-10-30"
updated: "2026-10-30"
source: "intake-4062"
summary_plain: "在 Windows 上给一个正在运行的 Electron 宿主（DeepSeek Harness）所在的 pnpm profile 安装/调整依赖时，pnpm install 报 ERR_PNPM_EPERM: rename…"
trigger: "pnpm install 撞上运行中进程的 DLL 锁：靠目录改名绕过，别删文件. 在 Windows 上给一个正在运行的 Electron 宿主（DeepSeek Harness）所在的 pnpm profile 安装/调整依赖时，pnpm install…"
verify: "1) pnpm install 退出码 0。2) 重启宿主后 Get-Process -Id <pid> | % { $_.Modules | ? ModuleName -match 'vips' } 只剩目标版本（如 libvips-cpp-8.18.7.dll）。3) 在 profile 目录 require('sharp') 报 0.35.5 / vips 8.18.7，且…"
provenance:
  issue: "#4062"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

在 Windows 上给一个正在运行的 Electron 宿主（DeepSeek Harness）所在的 pnpm profile 安装/调整依赖时，pnpm install 报 ERR_PNPM_EPERM: rename '...@img\sharp-win32-x64_tmp_4280_4' -> '...@img\sharp-win32-x64'。同一目录下删除/覆盖 libvips-42.dll、sharp-win32-x64.node 也一律失败。宿主不重启改动不生效，但用户不想中断当前会话，卡在装不上也退不掉的状态。

## Root Cause

两个机制叠加：1) Windows 锁住已 dlopen 的 DLL，删除与覆盖返回 ACCESS_DENIED/EBUSY，但目录项本身可以改名（rename 只动父目录元数据）；pnpm 的 import 流程是写临时目录再 rename 成目标名，目标被占用即失败。2) 手工替换过的包不在 node_modules/.modules.yaml 的记账里，pnpm 认为需要重新 import，于是每次 install 都去覆盖那个正被映射的目录。附：在单独进程 require 那个 .node 是成功的，所以单测能加载不能证明运行时没问题——冲突发生在同一进程先后加载两份同名 libvips 时，先加载者生效。

## Fix

三步且全程不用关宿主：1) 确认占用：遍历目标进程的 Modules 找 vips/sharp，用 [IO.File]::Open(path,'Open','ReadWrite','None') 抛异常判断被锁。2) 把整个包目录改名挪开，例如 Rename-Item node_modules\@img\sharp-win32-x64 -NewName sharp-win32-x64.orphan —— 目录能改名、文件不能删，这是关键。3) 重跑 pnpm install：目标名已空出，pnpm 正常 import，并把挪开的目录收进 node_modules\.ignored\ 并打 WARN（not in the dependency tree），属正常收尾。宿主重启后再删 .ignored。若目标不是装包而是消除两份同名 DLL 的冲突（profile 的 sharp 0.34.5 与 app 内置 0.35.5 抢同一个 libvips-42.dll），第 2 步改成版本对齐，让两份 .node 对同一 libvips 版本。

## Verification

1) pnpm install 退出码 0。2) 重启宿主后 Get-Process -Id <pid> | % { $_.Modules | ? ModuleName -match 'vips' } 只剩目标版本（如 libvips-cpp-8.18.7.dll）。3) 在 profile 目录 require('sharp') 报 0.35.5 / vips 8.18.7，且 sharp({create:{width:8,height:8,channels:3,background:'#fff'}}).png().toBuffer() 真的产出字节（实测 103 字节）。4) 原先报 ERR_DLOPEN_FAILED 的截图/图像工具恢复正常。
