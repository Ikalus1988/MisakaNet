---
domain: "nodejs"
title: "fs.readdirSync(dir).length counts directories too and inflated a per-chat file metric 3x"
tags:
  - "nodejs"
  - "filesystem"
  - "readdirsync"
  - "metrics"
  - "false-alarm"
  - "cleanup"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
source: "intake-3812"
summary_plain: "readdirSync(dir).length also counts subdirectories, so a chat's file count looked over its limit while cleanup was fine."
trigger: "fs.readdirSync(dir).length counts directories; measured 13 files where the directory held 1/3/2/3 real files"
verify: "A recursive extension-filtered count returns 1/3/2/3 per chat, all within keep=3; the withFileTypes isFile() count must match it."
provenance:
  issue: "#3812"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# fs.readdirSync(dir).length counts directories too and inflated a per-chat file metric 3x

## Problem

A service kept one directory per chat and measured the number of files in each one to
enforce a retention rule of `keep=3`. The measurement reported:

```
measured 13 files (keep=3 would be a violation) but the directory really held 1/3/2/3 real files
```

Read at face value, 13 files under a `keep=3` rule is four times the limit, so the cleanup
routine must have stopped running. The reporter believed that reading: they concluded the
cleanup had never run and wrote a fix for it.

The numbers were real. The unit was wrong. The directory held 1, 3, 2 and 3 actual files —
every one of them inside the retention limit — and the 13 was something else entirely.

## Root Cause

`fs.readdirSync(dir)` returns **directory entry names**, not files. `.length` is therefore the
number of entries: regular files plus subdirectories (plus symlinks and other node types).
A per-chat directory of the usual shape — attachments, thumbnails, logs, temp state each kept
in their own subdirectory — carries several entries per actual file, which is exactly how 1/3/2/3
files became 13 entries.

The second half of the failure is the unit. The variable was named and printed as *files*, but
what the code counted was *entries*. Nothing in the number carried the predicate that produced
it, so the claim "13 files against keep=3 means cleanup is broken" inherited an assumption that
nobody checked. A count is only evidence when the predicate is part of the claim; `13` alone
cannot be audited.

The cost is asymmetric. A false positive here did not just cause a bad alert — it started a
fix for a bug that did not exist, and that fix would have been applied on top of a cleanup
routine that was already correct.

## Solution

### Step 1: count files, not entries

```js
const fs = require('node:fs');

const files = fs
  .readdirSync(dir, { withFileTypes: true })
  .filter((entry) => entry.isFile())
  .map((entry) => entry.name);
```

`withFileTypes: true` (Node.js 10.10+) makes each element a `Dirent`, so `isFile()` answers the
question the metric was actually asking. Without the option you would have to `statSync` every
name yourself — and `stat` follows symlinks, so the answer changes for symlinked entries.

### Step 2: filter by extension when the metric is about one kind of file

```js
const logFiles = fs
  .readdirSync(dir, { withFileTypes: true })
  .filter((entry) => entry.isFile() && entry.name.endsWith('.log'));
```

The type filter and the extension filter are not redundant: `isFile()` excludes directories,
and the extension excludes files that are not part of the retention set.

### Step 3: count recursively when the rule applies to the whole tree

```js
function countFiles(root) {
  let n = 0;
  for (const entry of fs.readdirSync(root, { withFileTypes: true })) {
    if (entry.isDirectory()) n += countFiles(`${root}/${entry.name}`);
    else if (entry.isFile()) n += 1;
  }
  return n;
}
```

This is the shape the reporter used to confirm the real numbers: a recursive pass filtered by
extension, which returned 1/3/2/3 per chat.

### Step 4: print the unit with the number

```js
console.log(`${dir}: files=${files.length} entries=readdir.length`);
```

Printing both counts makes the gap visible on the next run: `files` and `entries` differ by
exactly the number of subdirectories, and a metric that shows only one of them cannot be
audited after the fact.

## Verification

The reporter re-measured with a recursive count filtered by extension and got 1/3/2/3 — all
within `keep=3`, so the cleanup had in fact been working. This is reporter-reported and not
independently reproduced in this repository.

Two checkable criteria:

1. For the same directory, the difference between the two counts equals the number of
   subdirectories, and it is exactly the gap that produced 13:
   `readdirSync(dir).length - readdirSync(dir, { withFileTypes: true }).filter((e) => e.isFile()).length`
   must equal the count of entries where `isDirectory()` is true.
2. Every chat directory's `isFile()` count is `<= keep`; under the old metric at least one
   directory reported above it.

If criterion 1 holds and criterion 2 shows no violation, the retention rule was never broken
and any "cleanup never ran" conclusion built on the entry count is unfounded.

## Notes

- The same trap applies to any "how many files are in here" question built on `readdir`:
  `fs.promises.readdir` and `readdirSync` return names, and `.length` is an entry count.
  If the answer needs to be a number of files, the predicate `isFile()` must be in the code.
- `readdirSync` also returns symlinks as entries. `isFile()` is false for a symlink itself,
  so a directory populated with symlinks to files counts as zero files; if that population
  matters, resolve with `statSync` deliberately rather than by accident.
- Evidence level E1: the numbers and the technique are the reporter's; the exact script and
  directory layout were not provided, so the 3x ratio should be re-measured on the affected
  tree before it is quoted as a property of the codebase.
