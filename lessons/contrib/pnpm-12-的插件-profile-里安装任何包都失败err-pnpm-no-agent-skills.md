---
title: "pnpm 12 的插件 profile 里，安装任何包都失败：`ERR_PNPM_NO_AGENT_SKILLS_DIR`，正文却说「你正在装的这个包需要 ag"
domain: "dsh"
tags:
  - "package.json"
  - "pnpm"
  - "pnpm-workspace.yaml"
status: "published"
evidence_level: "E1"
created: "2026-11-23"
updated: "2026-11-23"
source: "intake-5607"
summary_plain: "pnpm 12 的插件 profile 里，安装任何包都失败：`ERR_PNPM_NO_AGENT_SKILLS_DIR`，正文却说「你正在装的这个包需要 agent skills 目录」。换包、换版本、换…"
trigger: "ERR_PNPM_NO_AGENT_SKILLS_DIR 所有 pnpm add 都失败 插件装不上 permissions pnpm approve"
verify: "profile 目录执行 `pnpm add <任意小包>` 退出码 0 并输出 `Done in ...`；pnpm-workspace.yaml 中不再有 `permissions:`；随后 `pnpm remove <该包>` 也成功，依赖列表回到原状。"
provenance:
  issue: "#5607"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

pnpm 12 的插件 profile 里，安装任何包都失败：`ERR_PNPM_NO_AGENT_SKILLS_DIR`，正文却说「你正在装的这个包需要 agent skills 目录」。换包、换版本、换 registry（npmjs/npmmirror）一样失败并回滚，`package.json` 不变；插件市场的直接安装因此失败，转走「AI 助手接管」兜底，用户看到的是卡在「正在唤起 AI 助手…」。

真凶与本次安装的包无关：此前为放行某个 MCP 插件的构建脚本跑过 `pnpm approve`。

## Root Cause

`pnpm approve` 把结果写进 `pnpm-workspace.yaml` 的 `permissions` 块：

```yaml
permissions:
  <pkg-name>:
    skills: true
```

`skills` 是「允许写某个目录」的权限，必须同时有 `skills.dirs` 声明目录列表才成立。缺 `skills.dirs` 时 pnpm 在**解析依赖之前**校验 workspace 配置就失败，所以：报错正文指向那个无关的包名；失败发生在 resolution 之前，`pnpm.log` 几乎为空、没有任何 registry 请求；与包/版本/registry 全部无关——整个 profile 被这一块锁死。

诊断陷阱：安装器把 pnpm 的退出归因到被安装的包，于是人去换包、查兼容性，全都无效。真正的信号是「换个完全无关的包也报同一个错」+「日志里没有网络请求」。

## Fix

1. 打开 profile 的 `pnpm-workspace.yaml`，删掉整个 `permissions:` 块（approve 之前它不存在）。
2. 重试 `pnpm add <pkg>`：应在 1 秒内进入正常解析/下载，而不是立刻失败。
3. 不要在缺 `skills.dirs` 时加回 `skills: true`；要放行构建脚本用 `allowBuilds`（如 `allowBuilds: { cpu-features: true }`），不要用 approve 的 permissions 块。
4. 顺带降噪：`minimumReleaseAge: 0`（否则刚发布的插件一律被拒装）、`strictPeerDependencies: false`（peer 差一个 rc 就硬失败）、固定到可达镜像源。

## Verification

profile 目录执行 `pnpm add <任意小包>` 退出码 0 并输出 `Done in ...`；pnpm-workspace.yaml 中不再有 `permissions:`；随后 `pnpm remove <该包>` 也成功，依赖列表回到原状。
