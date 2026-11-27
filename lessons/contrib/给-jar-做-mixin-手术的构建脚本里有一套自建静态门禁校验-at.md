---
title: "给 jar 做 Mixin 手术的构建脚本里有一套**自建静态门禁**（校验 `@At` 注入目标串、`@Inject`/`@Redirect` 处理器签名、`"
domain: "dsh"
tags:
  - "split"
  - "python"
  - "rc-2"
status: "published"
evidence_level: "E1"
created: "2026-11-27"
updated: "2026-11-27"
source: "intake-5897"
summary_plain: "给 jar 做 Mixin 手术的构建脚本里有一套**自建静态门禁**（校验 `@At` 注入目标串、`@Inject`/`@Redirect` 处理器签名、`@Shadow` 注解、坐标读取口径）。一次会话里这些门禁**自己错了 5…"
trigger: "static check gate false positive fault injection asserts only exit code checker model wrong"
verify: "实测 **13 条构建故障 + 4 条审计故障全部 exit=1**，且失败信息来自对应门禁（例：`--fault=guard` 报 `[2g] 这些类里有\"玩家 ↔ 方块\"距离守卫却没有对应 Mixin: ['SpeakerConfigPacket']`）；产物哈希在故障前后一致。 13 条构建故障 + 4 条审计故障均 exit=1 且失败文本来自对应门禁；部署产物 sha256…"
provenance:
  issue: "#5897"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

给 jar 做 Mixin 手术的构建脚本里有一套**自建静态门禁**（校验 `@At` 注入目标串、`@Inject`/`@Redirect` 处理器签名、`@Shadow` 注解、坐标读取口径）。一次会话里这些门禁**自己错了 5 次**，每次都是"响亮地错、但理由不对"：

1. 故障注入 `--fault=coordshape` 以 exit≠0 "通过"，真因是**临时源码文件名 ≠ public 类名**，javac 直接报错，被测门禁**根本没跑到**；
2. 朴素 `split(',')` 切方法参数，不认泛型里的逗号，`BiFunction<Object, BlockPos, Object>` 被数成 3 个参数；
3. `@Shadow` 检查用 `'@Shadow' in line` 全文匹配，javadoc 里的 `{@code @Shadow}` 被当成注解行，误报并中止构建；
4. 按"目标描述符实参个数"算 Mixin 处理器参数，忽略**实例方法调用还要多接一个接收者**，8 个 `Vec3.distanceToSqr` 重定向全被误判；
5. 跑"故障注入总检"时在**错误的工作目录**下执行，`python` 自己以 `rc=2`（`can't open file`）退出、输出为空 —— 13 条故障"全部 rc≠0"，看起来每条门禁都被验证过了，**实际上门禁一次都没跑**。

## Root Cause

门禁解析源码文本/字节码文本，而作者把"语言语义"和"框架调用约定"写成了脑子里的**简化模型**（用逗号切参数、用子串找注解、按描述符参数个数算处理器参数）。模型一旦偏差，门禁就报假错 —— 更危险的是也可能**反向放行**。

结构性问题：故障注入只断言"退出码非 0"，没有断言"失败来自被测门禁"，于是"编译失败"这类无关错误会伪装成"门禁生效"。

## Fix

① 每条门禁配"注入错误 → 必须 FAIL"的故障用例，且**故障注入自身要自检**（断言被检对象真被改变；替换没生效就立刻停下）；
② 解析按语言/框架形态：按泛型深度切逗号；注解只认行首 `^\s*@Annotation\b`；静态/实例调用**从字节码 opcode 判断**（`invokevirtual`/`invokeinterface` ⇒ 处理器多一个接收者）；
③ 门禁的 ok 信息写出**判定依据**，让模型偏差一眼可见；
④ 保留"解析到 0 个 = 失败"的空门禁防线；
⑤ 故障总检对每条**同时**要求 `rc≠0` **且**输出含该门禁专属失败标记，并断言部署产物在整轮故障前后逐字节未变。

## Verification

实测 **13 条构建故障 + 4 条审计故障全部 exit=1**，且失败信息来自对应门禁（例：`--fault=guard` 报 `[2g] 这些类里有"玩家 ↔ 方块"距离守卫却没有对应 Mixin: ['SpeakerConfigPacket']`）；产物哈希在故障前后一致。

13 条构建故障 + 4 条审计故障均 exit=1 且失败文本来自对应门禁；部署产物 sha256 在整轮故障前后不变
