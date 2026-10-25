---
title: "Two artifacts with the same name are two production paths: separate them by trigger, device and module"
domain: "development"
tags:
  - "debugging"
  - "artifact-provenance"
  - "backup"
  - "timestamp-forensics"
  - "format-string"
  - "information-asymmetry"
  - "export-path"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "同名诊断产物可能是两条独立产出路径，靠内容分不清，要看谁在什么动作下写到哪个设备。"
trigger: "两个诊断产物当成同一类 反复找导出入口 备份里没有 可移动设备 控制器内存设备"
verify: "每个产物都能答出触发动作、目标设备、生成模块；备份里缺该产物时能判定它属 UI 导出型，不是备份工具漏过滤。"
source: "intake-3563"
provenance:
  issue: "#3563"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# Two artifacts with the same name are two production paths: separate them by trigger, device and module

## Problem

While tracing how a diagnostic report file is exported, one dataset turned out to have **two** artifacts
— call them A and B — that kept being treated as one thing:

- **A** can only be produced by a **manual UI action**, writes to a **removable device**, and is
  **absent** from backups.
- **B** is generated automatically during **archive/backup**, writes to a **controller memory device**,
  and is present in every backup.

Because the two share a name and overlap in content, the investigation went wrong in three separate
directions:

1. B was assumed to be a "simplified version of A", so the work became hunting for an export entry point
   that generates A — but B is not produced by any export at all.
2. "A is missing from the backup" was assumed to be the backup tool filtering files — in fact these are
   two independent production paths with different sources, so nothing was being filtered.
3. A's data was used to reconstruct B backwards — the direction is wrong: A carries **more**
   information than B, so B cannot be built from A's fuller form and still be B.

## Root Cause

Similar names, overlapping content (both are called "diagnostic report"), but the **triggering action**,
the **target device** and the **data drop point** differ completely. Content alone cannot separate them;
you have to look at *who writes what, to which device, at which moment*.

The counter-intuitive part is the **information asymmetry**: the automatically generated B is the
*poorer* one — key fields come masked — while the manually exported A is the raw data with per-event
parameters and real counts. The intuition "the one that comes automatically must be complete" is
backwards here, and it is what makes the "simplified version" theory feel right.

## Solution

Build a triple for every artifact: **trigger action × target device × generating module**.

| Dimension | How to check |
|---|---|
| Trigger | Is the artifact's timestamp the same instant as some operation (archive / export)? Does the same file also exist in a runtime directory? |
| Target device | Which directory it lands in — removable device vs controller memory device |
| Generating module | Search the implementation binary for the artifact's format string (e.g. the header text) — this localizes the module and its call entry |

The reporter's measured triple:

| | A (raw data) | B (report) |
|---|---|---|
| Trigger | UI button → device picker | archive / backup |
| Target | removable device (three choices) | controller memory device |
| Module | task module holding a four-part format string | goes through the file-backup channel |
| In backup | **no** | **yes** |
| Information | **complete** (per-event parameters, real counts) | **reduced** (key fields masked) |

Three rules that came out of it:

1. **Do not assume "the automatic one is the complete one."** Manual export tends to be the raw data and
   automatic backup tends to be a rendered summary — verify, do not assume.
2. **Whether bulk collection is possible depends on "can the trigger be scripted"**, not on "does an
   export function exist". Here the UI export had no scriptable interface, so bulk acquisition was only
   possible through UI automation.
3. **A number in the file name is not necessarily a timestamp.** Here it was an incrementing ID whose
   magnitude fell inside the Unix-timestamp range but carried no temporal meaning — parsing it as a
   timestamp produces completely wrong conclusions about when the file was written.

## Verification

For each artifact you must be able to answer "who writes it, under which action, to which device?" If
all you know is "it is generated automatically", the information is insufficient — that answer cannot
distinguish A from B.

The reporter's discriminating observations, in order of strength:

- **Presence in a backup**: A is absent from the backup set while B appears in every backup of the same
  controller. One backup listing separates them.
- **Timestamp distribution**: A's time coincides with the export operation, B's with the archive
  operation; the runtime directory holds one shape and not the other.
- **Module localization**: the format string found in the binary belongs to one module, and which call
  entry reaches it tells you the producing path.

When an artifact is missing from a backup, first decide which path it belongs to. A UI-export-only
artifact is *supposed* to be missing — that is the expected behaviour, not the backup tool filtering
files. Pass = A and B each have a filled triple and the "missing from backup" case is explained by path,
not by a filter suspicion.

## Notes

The reporter did not name the controller/product, so no platform-specific endpoint is asserted here —
**报料者未给出，需复现确认**. The method is recorded generically on purpose: it is the
identify-by-provenance step, and it applies to any "two files that share a name" confusion (save states,
crash dumps, config snapshots), not only to the device in this report.

The `A`/`B` labels are the reporter's; the actual file names were not given.
