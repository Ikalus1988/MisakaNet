---
title: "A pnpm store moved across drives over a junction breaks hard links and empties the plugin list"
domain: "nodejs"
tags:
  - "pnpm"
  - "hard-links"
  - "windows"
  - "junction"
  - "node-modules"
  - "plugin-install"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "用目录联接把 pnpm store 挪到别的盘后硬链接跨不过去，profile 里已装的插件全部失效。"
trigger: "is not used because packages cannot be hard linked from it into this project"
verify: "恢复后 pnpm 不再报 cannot be hard linked，dsh plugin list 与宿主启动都能看到全部插件，node_modules 无缺失目录。"
source: "intake-3579"
provenance:
  issue: "#3579"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

## Problem

为清理 C 盘空间，把 pnpm 缓存目录 `C:\Users\<user>\AppData\Local\pnpm` 迁移到 `D:\`，并在原位置建立**目录联接（Junction）**。之后宿主执行插件安装时，pnpm 报出：

```
[WARN] The store at C:\Users\<user>\AppData\Local\pnpm\store\v11 is not used because packages
cannot be hard linked from it into this project. Using the store at
C:\Users\<user>\.pnpm-store\v11 instead.
```

随后 profile 的 `node_modules` 中已安装插件**全部失效**：宿主界面里 6 个插件"全部消失"，`package.json` 的 `dependencies` 被重写为**仅剩 1 项**。

这条 WARN 极易被当成"pnpm 换个 store 也能用"的良性提示——它实际上是"我放弃了这个 store"的宣告，后面那句 `Using the store at ... instead` 才是重点。

## Root Cause

**pnpm 依赖硬链接把包从全局 store 链入 `node_modules`，而硬链接不能跨卷**（NTFS 限制）。store 搬离原盘后，所有既有链接的目标都失效了。

pnpm 不会因此拒绝运行：它自动回退到新建的 `<home>\.pnpm-store\v11`（报料中为 `C:\Users\<user>\.pnpm-store\v11`），并在一条 WARN 里说明——但**既有 `node_modules` 树不会自动重建**。于是磁盘上的树与 manifest/lockfile 不一致。

为什么这件事看起来像"插件随机消失"而不是"我搬了 store"：

- 原路径上留着 Junction，`dir` 看起来"store 还在 `C:\...`"，掩盖了它其实位于 `D:\`；
- 失败点不在迁移那一刻，而在之后某次插件安装/依赖重算时才暴露；
- `package.json` 被改写是**结果**，不是原因：先把 store 修回去、再重建 `node_modules`，manifest 才会重新收敛。

`package.json` 的 `dependencies` 为什么被重写成 1 项，报料者未给出逐步归因，需复现确认（不能直接推断为 pnpm 的某一行为）。

## Solution

1. **诊断**：pnpm 日志里出现 `store ... is not used because packages cannot be hard linked` 即可确认是跨盘迁移所致，不必再猜插件或宿主配置。
2. **规则**：**不要用 Junction/symlink 把 pnpm store 移到其他磁盘**。store 必须与 profile 同盘——这不是性能建议，是硬链接的物理限制。
3. **恢复**：把 store 移回原盘 → 删除 pnpm 自动回退生成的 `<home>\.pnpm-store`（确认是刚生成的那个，不是原有 store）→ 在受影响 profile 重新安装依赖以重建 `node_modules` → 重启宿主并确认插件加载。
4. **想省空间时，优先清理与硬链接无关的目标**：pip/npm 的纯下载缓存、浏览器缓存、各 `*-updater` 更新器残留、无用的 `ProgramData` 目录。**pnpm store 与 `nodeLinker=hoisted` 的 `node_modules` 都不适合跨盘迁移。**
5. **迁移任何包管理器缓存之前**，先备份 profile 的 `package.json` / `pnpm-lock.yaml` / `cordis.patch.yml`——本例里 `package.json` 被改写后才想起备份就已经晚了。

迁移前后确认"那个路径到底是什么"：

```powershell
# 是不是联接？LinkType / Target 会直接告诉你
Get-Item "$env:LOCALAPPDATA\pnpm" | Select-Object FullName, LinkType, Target
cmd /c dir /AL "%LOCALAPPDATA%\pnpm"
```

恢复时的顺序（先确认再删，store 是缓存但重建要花时间与流量）：

```powershell
pnpm store path                    # 当前生效的 store 在哪
# 把 store 移回 profile 所在盘后，再删回退生成的那个：
Remove-Item "$env:USERPROFILE\.pnpm-store" -Recurse -Force
cd <profile>
pnpm install                       # 重建 node_modules（硬链接需要同卷）
```

## Verification

- **迁移前后**用 `dir /AL` 或 `Get-Item` 确认目标是否为 Junction——这是"我到底做没做跨盘"的判据。
- **迁移后立即**在受影响 profile 执行 `dsh plugin list` **并实际启动宿主**，确认插件仍能加载；若 `node_modules` 下出现缺失或异常包目录，即硬链接已断裂。
- **恢复后的通过判据**：不再出现 `cannot be hard linked` 警告，且 `pnpm-workspace.yaml` 中没有遗留 `storeDir` 覆盖（有覆盖时 pnpm 仍可能指向别处，看起来"又好了又坏了"）。
- 恢复后 `node_modules` 里每个直接依赖都应能用 `pnpm why <pkg>` 解析到；解析不到即为树未重建完成。

## Notes

- 同样的坑对 `nodeLinker: hoisted` 的 `node_modules` 也成立：它虽然不再用"每包一个硬链接"的布局，但仍有需要同卷的部分，报料者明确把它列进了"不适合跨盘迁移"。
- 判断"能不能跨盘"的通用方法：**看这个目录里的内容是不是靠硬链接/符号链接维持的**。纯下载缓存（如 npm 的 `_cacache`）可以随便搬；靠链接装配出来的目录（store、`node_modules`、部分构建缓存）不能。
