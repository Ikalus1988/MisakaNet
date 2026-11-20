---
title: "Gradle toolchain 自动下载 JDK 卡死：~/.gradle/jdks 里 .part 恒 0 字节"
domain: "java"
tags:
  - "gradle"
  - "java"
  - "toolchain"
  - "foojay"
  - "download"
status: "published"
evidence_level: "E1"
created: "2026-11-20"
updated: "2026-11-20"
source: "intake-5115"
summary_plain: "多模块工程里子项目声明 java.toolchain.languageVersion = 21，本机只装了 JDK 25。build 卡在：…"
trigger: "Gradle toolchain 自动下载 JDK 卡死：~/.gradle/jdks 里 .part 恒 0 字节. 多模块工程里子项目声明 java.toolchain.languageVersion = 21，本机只装了 JDK 25。build 卡在：…"
verify: "1) gradlew -q javaToolchains 能列出该本地 JDK21，路径就是指定目录； 2) 再 build 时 ~/.gradle/jdks 不再新增 .part； 3) 子项目 compileJava 正常执行，不再卡在 configure。"
provenance:
  issue: "#5115"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

多模块工程里子项目声明 java.toolchain.languageVersion = 21，本机只装了 JDK 25。build 卡在：

~/.gradle/jdks/OpenJDK21U-jdk_x64_windows_hotspot_21-any-vendor-21.0.13_9.zip.part   恒 0 字节

既不失败也不前进，日志里只有 daemon forked 那一句，很容易误判成"编译很慢"。

## Root Cause

foojay-resolver 会去 Adoptium / GitHub 自动下约 190MB 的 JDK，该链路在国内极慢且没有进度输出；Gradle 侧没有超时，于是永久挂起。

## Fix

1) 用镜像拿同版本 JDK（例如清华 Adoptium 镜像的 21.0.13+9），解压到固定目录
2) gradle.properties 增加：
   org.gradle.java.installations.paths=<PATH>
3) 不需要自动下载就把 settings.gradle 里的 foojay-resolver-convention 插件去掉

## Verification

1) gradlew -q javaToolchains 能列出该本地 JDK21，路径就是指定目录；
2) 再 build 时 ~/.gradle/jdks 不再新增 .part；
3) 子项目 compileJava 正常执行，不再卡在 configure。
