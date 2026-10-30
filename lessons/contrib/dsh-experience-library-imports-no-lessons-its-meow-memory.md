---
title: "dsh-experience-library imports no lessons: its meow-memory adapter resolves memory.db relative to the plugin and…"
domain: "devops"
tags:
  - "dsh"
  - "experience-library"
  - "meow-memory"
  - "sqlite"
  - "adapter"
  - "junction"
  - "mklink"
  - "silent-failure"
  - "windows"
  - "node_modules"
status: "published"
evidence_level: "E1"
created: "2026-10-30"
updated: "2026-10-30"
source: "intake-3900"
summary_plain: "After installing the DSH plugin `dsh-experience-library` next to `meow-memory`, `experience_import(action=\"list\")`…"
trigger: "dsh-experience-library imports no lessons: its meow-memory adapter resolves memory.db relative to the plugin and…. After installing the DSH plugin…"
verify: "`experience_import(action=\"list\")` prints `可导入 lesson(N 条,...)` instead of `无可用 lesson`; `experience_import(action=\"import\", ids=[...])` answers `导入 N 条 lesson → pending(重复已跳过)`…"
public_analogue: "@modelcontextprotocol/server-memory"
provenance:
  issue: "#3900"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

After installing the DSH plugin `dsh-experience-library` next to `meow-memory`, `experience_import(action="list")` kept answering:

```
无可用 lesson(要求 active 且 importance≥3 或 corrected)。
```

even though the same moment `memory_read` showed a healthy lesson row: `[lesson] （active）` with `importance` 3 then raised to 4, `corrected: true`, project set. `experience_import(action="import", ids=[...])` failed the same way:

```
导入 0 条 lesson → pending(重复已跳过);未找到/歧义 1 个:0mvpesq2b-5e7d8ff557174985aad5ee2758。
```

Bumping `importance` to 4 and re-trying changed nothing, and writing the lesson under project `全局` instead of a named project changed nothing either - so it was not the `importance≥3 / corrected` filter and not a project filter.

## Root Cause

The adapter opens the meow-memory SQLite file at a guessed path that does not exist on a normal npm install, and the failed open is swallowed.

`dsh-experience-library/lib/index.js://[REDACTED:url_credential]@host the first probe walks up to `.../node_modules/@scope/.dsh-meow/memory.db` - the extra `@scope` level makes it land one directory too high. The second probe expects `$DSH_HOME/profiles/<p><PATH>`, which does not exist when the plugin is installed into `node_modules` rather than `profiles/<p>/plugins`.

When neither exists, `resolveMeowDbPath()` still returns the (missing) first path; `new DatabaseSync(dbPath, {readOnly:true})` throws, the surrounding `catch` at `lib/index.js:3804-3807` logs a console warning and returns `[]`. The tool layer then renders an empty list as "no usable lesson" - a silent failure that reads like a data problem instead of a path problem.

The real database lives in the workspace: `<workspace><PATH>` (meow-memory stores per workspace).

## Fix

Point one of the two probed paths at the real database with a directory junction - no code change, no admin rights://[REDACTED:url_credential]@host satisfies the first probe instead.

## Verification

`experience_import(action="list")` prints `可导入 lesson(N 条,...)` instead of `无可用 lesson`; `experience_import(action="import", ids=[...])` answers `导入 N 条 lesson → pending(重复已跳过)`; `experience_refine(action="list")` shows the samples with `tools=adapter-meow`; after `action="done"` it reports `已标记 N 条完成,队列剩余 0 条`. If it still says `无可用 lesson` while the SQLite clearly has `active` lessons with `importance>=3`, print the exact resolved path and check the `@scope` level - that is the bug, not your data.
