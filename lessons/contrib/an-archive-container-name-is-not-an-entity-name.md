---
domain: "data"
title: "An archive container name is not an entity name: parse the entries before grouping"
tags:
  - "archive-extraction"
  - "rar"
  - "7z"
  - "zip"
  - "entity-name"
  - "grouping"
  - "silent-merge"
  - "robot-backup"
status: "published"
evidence_level: "E0"
created: "2026-10-03"
updated: "2026-10-03"
source: "intake-issue-1978"
summary_plain: "上传一个装着多台机器人备份的压缩包，工具只报出 1 台。压缩包文件名不是机器人名字——实体名必须从包内条目路径里解析出来，否则多台会被静默合并成一台。"
trigger: "archive filename used as the only entity/group name; rar/7z branch misses the zip subdirectory logic; multi-robot backup archive shows 1 robot"
verify: "Grouped output lists one entity per distinct inner directory (FD/r01/TPS0010.LS -> r01) and the entity count matches the number of distinct per-robot subdirectories, not 1."
provenance:
  issue: "#1978"
  source: "intake issue #1978 (claude-code submission, 2026-09-21). Observations are the reporter's; not reproduced by this lesson's author."
---

# An archive container name is not an entity name

## Problem

An uploaded `.rar`/`.7z` holding **several** robot backups — one per subdirectory — produced a single
robot task. Recorded in [issue #1978](https://github.com/Ikalus1988/MisakaNet/issues/1978) (2026-09-21):

- The offending line was `const robotName = fileName.replace(/\.rar$/i, '')` — the archive's own
  filename became the entity name (`TG-PLC2_离线程序.rar` → entity `TG-PLC2_离线程序`), and every
  extracted file joined that one group.
- The backend log showed **25 `.LS` files extracted successfully**, so unpacking was fine. The loss
  happened afterwards, in the client-side grouping.
- The report gives two counts that do not agree with each other: the symptom is described as
  "only 1 robot recognized", and a separate line records "2 recognized, 4 actually present (LS
  only)". Both are kept here as written. The shape they share is what matters: the reported count
  is derived from the container name instead of from the entries, so it is always **lower** than
  the real number — and nothing errors when it collapses.

The container name in that example is not a robot name at all. `TG-PLC2_离线程序` names a project or
a production line; the per-robot identity lives one level down, in the entry paths.

## Root Cause

Two different identifiers were conflated, and the second failure is what let the first one survive.

**A container has exactly one name; a dataset has one entity per unit.** A `.rar`/`.7z`/`.zip`/`.tar`
is a bundle — often named after a site, project, or shipment, and deliberately not after any single
unit inside it. Deriving a group key from the bundle name therefore answers a question nobody asked,
and the answer is *worse than nothing*: it is a plausible-looking key that maps N entities onto one
group. The count comes back smaller than reality and no layer reports an error, because from the
grouping function's point of view nothing failed.

**The identity rule was implemented per container format instead of once on the entry path.** The
ZIP branch already parsed the entry path — checking for a subdirectory (`name.includes('/')`) and
taking the parent directory as the entity name. The RAR/7z branch was forked later from the older
code and never received that logic. So the list of supported formats grew faster than the rule that
decides identity, and every format added after the rule was written is a fresh chance to skip it.

The transferable part is the second point, not the missing feature: **the bug is the duplicated
branch.** Any code that keys entities off a filename has the same defect, whatever the format.

## Fix

The reporter's fix enumerates four rules (detect a subdirectory → take the parent segment → else
parse the filename, preferring a machine-number pattern → clean the name). Folded into one reusable
three-step decision:

### Step 1 — Decide from the entries, never from the container

Treat the container name as bundle metadata and discard it as a grouping key. The only inputs that
can name an entity are the entry paths inside. If a code path groups before it has seen the entries,
that is the bug, regardless of format.

### Step 2 — Take the entity name from the entry path, in this order

```javascript
function entityFromPath(name) {
  // (a) entry sits in a subdirectory → the directory above the file is the entity
  //     FD/r01/TPS0010.LS -> r01
  if (name.includes('/')) {
    const parts = name.split('/');
    return clean(parts[parts.length - 2]);
  }
  // (b) flat entry → parse the filename, preferring the machine-number pattern
  // (c) clean() drops decorations such as trailing _suffix
  return clean(extractNumberedId(name) ?? name);
}
```

Order matters: the subdirectory is the stronger signal, so it wins over anything found in the
filename. Cleaning is part of step 2, not an afterthought — a raw parent directory such as `FD` or a
numbered folder with a trailing decoration will re-merge entities under the wrong key later.

### Step 3 — One function, called by every container branch

`entityFromPath` must be reached from ZIP, RAR, 7z, tar, and every format added later. The failure
mode this removes is precisely the one that occurred: a new branch that reimplements naming instead
of calling the shared rule. Add a new format, and the only new code should be the extraction — never
the identity decision.

**Guard worth keeping:** after grouping, compare the entity count against the number of distinct
parent directories. A mismatch is a bug, and it is the only check that catches a collapse silently
merging real entities.

## Verification

What the report recorded, on re-upload of `TG-PLC2_离线程序.rar`:

- Before: the UI listed **1** robot task. After the fix: **4** robot tasks.
- Browser console showed the per-entry grouping decisions, e.g.
  `[Archive] File: FD/r01/xxx.LS -> Robot: r01`.

The independent re-check anyone can run on any multi-entity archive (the invariant from step 3 —
**not run by this lesson's author**, the reporter's archive was not available here):

```bash
# one line per distinct per-robot directory inside the archive
unzip -Z1 <archive> | awk -F/ 'NF>1 {print $(NF-1)}' | sort -u

# pass: the list has one line per entity and the grouped output shows the same count
# fail: the list has >1 line but the grouped output shows 1 entity
```

The failure is silent by construction, so a count comparison is the only acceptance that works. A UI
that renders "1 robot" without error is exactly the symptom.

## Notes

- **Sibling lesson, different container:** `cross-sheet-name-merge-data-chaos` is the same failure
  shape across Excel sheets — a name that is unique inside one container and not unique across them,
  silently merged by `groupby`. Its fix is to prefix the key with the source; here the source is the
  entry's parent directory. Different container, same lesson: derive the key from the source of the
  record, not from the container that shipped it.
- **Not the same as a failed unpack:** 25 files extracted successfully here, so "the archive was
  broken" was already excluded by the backend log. Check the extraction log before touching the
  grouping logic — they fail differently and the log separates them in one line.
- **Applies beyond archives:** ISO images, Docker layers, mail attachments, and multi-sheet
  workbooks are all containers with one name and many entities. The same three steps apply.
- `fanuc-backup-payload-extraction` covers reading the *contents* of an unpacked backup directory;
  it does not address how the directory is mapped back to robot identity.
