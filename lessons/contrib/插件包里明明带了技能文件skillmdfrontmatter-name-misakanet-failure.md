---
title: "插件包里明明带了技能文件——`SKILL.md`(frontmatter `name: misakanet-failure-memory`)和 `skills/"
domain: "dsh"
tags:
  - "customskilldirs"
  - "bundledskilldir"
  - "name"
status: "published"
evidence_level: "E1"
created: "2026-11-22"
updated: "2026-11-22"
source: "intake-5573"
summary_plain: "插件包里明明带了技能文件——`SKILL.md`(frontmatter `name: misakanet-failure-memory`)和…"
trigger: "plugin ships SKILL.md but skill never appears in dsh skill catalog | node_modules SKILL.md is not a discovery root | skill-filesystem roots"
verify: "把插件包的 skills/<name> 链到 ~/.dsh/skills/<name> 后让会话再取一次技能目录:出现该 frontmatter 的 name → 通过;仍不出现,则说明该目录不是发现根或 SKILL.md 的 frontmatter 不合法。"
provenance:
  issue: "#5573"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

插件包里明明带了技能文件——`SKILL.md`(frontmatter `name: misakanet-failure-memory`)和 `skills/misakanet/SKILL.md`——但装好之后,会话的技能目录里**从来没有这个技能**,也没有任何报错或警告。用户看到的是"MCP 工具修好了,但那个技能好像不存在"。

## Root Cause

DSH 的技能只有两条来路:(a) 插件在 index.js 里向 skill 服务注册;(b) skill-filesystem provider 在固定发现根下扫 SKILL.md。发现根是 `<project><PATH>/skills`、`<project><PATH>/skills`、`customSkillDirs`、`<dshHome>/skills`、`<agentsHome>/skills`、`bundledSkillDir`——`node_modules/<pkg><PATH>` **不是**发现根。
而 misakanet 的 index.js 只挂 MCP 客户端(动态 import @deepseek-ai/dsh-mcp-client → ctx.loader.unwrapExports → ctx.plugin),**没有任何技能注册**。于是包里那份 SKILL.md 永远落在发现根之外,静默失效。对照:同机出现在目录里的 7 个技能全部来自 `~/.dsh/skills/<name>/`,与"谁在发现根下"完全吻合。

## Fix

不改插件(改动会被下次升级覆盖),把包内技能目录链接进用户技能根:
`cmd /c mklink /J "%USERPROFILE%\.dsh\skills\misakanet" "%USERPROFILE%\.dsh\profiles\desktop\node_modules\misakanet\skills\misakanet"`
(Unix 用 symlink;用链接而非复制,升级不漂移。)下一轮请求的技能目录里立刻出现 misakanet-failure-memory,无需重启宿主。插件侧的正解是在安装时把技能目录链/拷到技能根,或在 index.js 里显式注册。

## Verification

把插件包的 skills/<name> 链到 ~/.dsh/skills/<name> 后让会话再取一次技能目录:出现该 frontmatter 的 name → 通过;仍不出现,则说明该目录不是发现根或 SKILL.md 的 frontmatter 不合法。
