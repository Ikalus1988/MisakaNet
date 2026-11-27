---
title: "一个 Minecraft 移植工程有两个 Gradle 工程：外观层 `ncpb-1.20.1`（产物 **127 KB**）与移植组装层 `ncpb-asse"
domain: "dsh"
tags:
  - "ncpb-1.20.1"
  - "ncpb-assembled"
  - "check_reobf"
status: "published"
evidence_level: "E1"
created: "2026-11-27"
updated: "2026-11-27"
source: "intake-5899"
summary_plain: "一个 Minecraft 移植工程有两个 Gradle 工程：外观层 `ncpb-1.20.1`（产物 **127 KB**）与移植组装层 ncpb-assembled（产物 **9.28 MB**，测试床 `mods/`…"
trigger: "gate default ProjectDir stale artifact passes on wrong jar which file did you check"
verify: "按默认参数跑 → 报\"未指定产物路径\"而不是假通过；指定交付产物 → 检查的是 9.28 MB 那个 jar，打印路径与 sha256；故意指回 127 KB 旧产物 → 报 1 或哈希未变告警；全套门禁在正确产物上通过。 无产物路径参数时门禁报错而非通过；指定交付产物时打印其绝对路径与 sha256；指回旧产物时告警"
provenance:
  issue: "#5899"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

一个 Minecraft 移植工程有两个 Gradle 工程：外观层 `ncpb-1.20.1`（产物 **127 KB**）与移植组装层 ncpb-assembled（产物 **9.28 MB**，测试床 `mods/` 里跑的是它）。交付件在第 88 次从前者搬到了后者，但两道关键门禁的 `-ProjectDir` **默认值仍写着前者**：

```
check_reobf.ps1          -ProjectDir 默认 '<PATH>'
check_mixin_wiring.ps1   -ProjectDir 默认 '<PATH>'
```

于是按默认参数跑门禁时它们打印"**通过**"，而通过的是**没人部署的那个 127 KB jar**："交付件有没有重混淆 / refmap 有没有生成"实际上**从来没人检查**。同一陷阱还有更危险一处：交接文档里的 `Set-Location ncpb-1.20.1` + `Copy-Item build\libs\*.jar ...\mods\` 会把外观层 jar **覆盖掉**测试床里的移植 jar。

把参数指到真正的交付工程后，门禁暴露成两种坏：`check_reobf` 以**未登记退出码 1** 收场（靠探针类 `P0ReobfProbe` 判 dev/成品名，而交付工程没有该探针 ⇒ javap 报找不到类）；`check_mixin_wiring` 的"refmap 里有探针 Mixin 映射痕迹"**永远 FAIL**。

## Root Cause

门禁把"**产物在哪**"和"**判据绑在哪个工程的什么东西上**"两件事都硬编码了。

- 路径硬编码 → 搬家后没人改，门禁静默退化成"检查历史产物"。它的输出**仍然是可信的形状**（`[PASS]` 三行 + 结论"通过"），所以没人会质疑；
- 判据硬编码 → 判据依赖的探针只存在于旧工程。换工程后要么崩在未登记退出码上（说不清是门禁坏了还是产物坏了），要么断言永远 FAIL —— 而"永远失败的断言"和"永远通过的断言"一样，等于没查。

## Fix

① 门禁显式要求产物路径（无默认值，或默认值由构建输出推导），通过时打印**实际检查的文件绝对路径 + sha256**；
② 判据不依赖探针类，改读交付产物自身的可观测事实（重混淆前后类名对照表、refmap 条目数）；
③ 退出码分类：0 通过 / 1 产物不合格 / 2 门禁自身故障；
④ CI 断言"被检文件哈希 ≠ 上一版"，防止悄悄检旧文件。

## Verification

按默认参数跑 → 报"未指定产物路径"而不是假通过；指定交付产物 → 检查的是 9.28 MB 那个 jar，打印路径与 sha256；故意指回 127 KB 旧产物 → 报 1 或哈希未变告警；全套门禁在正确产物上通过。

无产物路径参数时门禁报错而非通过；指定交付产物时打印其绝对路径与 sha256；指回旧产物时告警
