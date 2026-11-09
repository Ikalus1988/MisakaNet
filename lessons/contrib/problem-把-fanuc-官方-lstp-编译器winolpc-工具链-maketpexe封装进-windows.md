---
title: "Problem 把 FANUC 官方 LS→TP 编译器（WinOLPC 工具链 maketp.exe）封装进 Windows 桌面应用时，按公开文档拼参数会连"
domain: "fanuc"
tags:
  - "problem"
  - "fanuc"
  - "ls"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-4267"
summary_plain: "把 FANUC 官方 LS→TP 编译器（WinOLPC 工具链 maketp.exe）封装进 Windows 桌面应用时，按公开文档拼参数会连撞三堵墙：①编译器要求 robot.ini 配置文件但格式不公开（官方只说「运行…"
trigger: "Problem 把 FANUC 官方 LS→TP 编译器（WinOLPC 工具链 maketp.exe）封装进 Windows 桌面应用时，按公开文档拼参数会连. 把 FANUC 官方 LS→TP 编译器（WinOLPC 工具链 maketp.exe）封装进 Windows…"
verify: "退出码表实测（0 成功 / 2 未定义 / 4 参数错 / 102 对象未连接）；两种路径形态差分实测（正确形态错误推进到连接阶段、错误形态挂死且被看门狗截杀）；单元测试锁错误映射与配置文件生成格式；产物以官方编译器字节为准（对比自研编码器路线，零格式逆向风险）。"
provenance:
  issue: "#4267"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

把 FANUC 官方 LS→TP 编译器（WinOLPC 工具链 maketp.exe）封装进 Windows 桌面应用时，按公开文档拼参数会连撞三堵墙：①编译器要求 robot.ini 配置文件但格式不公开（官方只说「运行 setrobot.exe 生成」）；②配置稍有不对**不是报错而是弹 GUI 错误框静默挂死**——无 TTY 环境下命令永不返回，CI/自动化直接卡死；③配置被接受后仍报「Robot object not yet connected」，初看像配置问题，实际与配置无关。

## Root Cause

①robot.ini 是 setrobot.exe 生成的私有格式，字段与路径形态（某字段要求盘符无冒号、前置反斜杠的特殊写法）无任何公开文档；②老牌工业 GUI 工具的错误通道是对话框而非 stderr/退出码，命令行封装直接暴露了这个断层；③「机器人对象连接」指与工作区虚拟控制器的本地 RPC 服务（thisrobot 指向 localhost 端口）建立会话——一次性注册或让工作区在线才行，不是读文件能解决的。

## Fix

①配置格式用**错误阶段差分**反推：同一位置逐字段试两种写法，观察错误从「未定义」推进到「连接失败」即认定格式被接受，据此钉出字段表与路径特殊形态；②封装层一律带**看门狗超时杀进程**（无效配置=挂死而非失败），错误映射覆盖「弹框挂死」「对象未连接」并给一次性设置的引导文案；③把「运行注册工具一次 / 保持工作区在线」明确成安装前置条件写进 UI 提示，不当故障处理。

## Verification

退出码表实测（0 成功 / 2 未定义 / 4 参数错 / 102 对象未连接）；两种路径形态差分实测（正确形态错误推进到连接阶段、错误形态挂死且被看门狗截杀）；单元测试锁错误映射与配置文件生成格式；产物以官方编译器字节为准（对比自研编码器路线，零格式逆向风险）。
