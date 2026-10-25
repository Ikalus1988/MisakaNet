---
domain: "development"
title: "A migration that only renames when the destination is missing leaves orphan source files"
tags:
  - "migration"
  - "filesystem"
  - "idempotency"
  - "rename"
  - "startup"
  - "state-reconciliation"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
source: "intake-3813"
summary_plain: "A migration only ran when the destination was missing, so source files were left behind whenever it already existed."
trigger: "if (!exists(dest)) rename(src, dest) leaves orphan files in the source dir after migration"
verify: "After the startup migration the source directory is empty and the destination holds the appended lines; a second run changes nothing."
provenance:
  issue: "#3813"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# A migration that only renames when the destination is missing leaves orphan source files

## Problem

A startup migration moved a file from an old location to a new one with a single guarded
operation:

```js
if (!exists(dest)) {
  rename(src, dest);
}
```

The reasoning was that a migration is a one-shot rename: either the destination is not there yet
and the source gets moved into place, or the migration already happened and there is nothing to do.

After the migration completed, the source directory **still contained 1 KB files**. The reporter's
note:

```
after migration the source directory still contained 1 KB files (written by a process that started
before the new config was hot-reloaded)
```

The migration had reported success, the destination was in place, and the old data was still
sitting in the old directory — silently, with no error and no warning.

## Root Cause

**The guard covered one of four states, and the unhandled one is the normal one.** For `(source,
destination)` there are four combinations:

| source | destination | what the code did |
|---|---|---|
| present | absent | `rename(src, dest)` — the only branch that was written |
| present | present | **nothing, silently** — the branch that produced the orphan |
| absent | present | nothing — correct |
| absent | absent | nothing — correct |

"Destination exists" does not mean "the source has nothing to contribute". It usually means the
opposite: the destination was created by an earlier run, so the source is *newer* than it. With a
hot reload, an old process keeps writing to the old path while the new process has already created
the destination — every write that lands after the first migration is exactly a `(present,
present)` state. Skipping it strands the data.

**Check-then-act is also two operations.** `exists(dest)` and `rename(src, dest)` are separate
filesystem calls, so a second process can create `dest` between them. On POSIX `rename` replaces an
existing destination; on Windows it fails with `EEXIST`/`EPERM`. The `exists()` guard was probably
there to avoid the overwrite — and the only way that guard can protect is by skipping the work, which
is the bug. A guard whose only safe branch is "do nothing" is a guard that loses data.

**"Destination exists" is not a completion condition.** The migration is done when the source
holds nothing that the destination lacks — an empty source directory, not a present destination.
Checking the destination answers a different question, so the code could never tell a finished
migration from an interrupted one.

## Solution

### Step 1: handle both branches, and never leave the source in place

```js
const fs = require("node:fs");

function migrate(src, dest) {
  if (!fs.existsSync(src)) return;              // nothing to move
  if (!fs.existsSync(dest)) {
    fs.renameSync(src, dest);                   // fast path: nothing to merge
    return;
  }
  fs.appendFileSync(dest, fs.readFileSync(src)); // dest exists: merge, then drop the source
  fs.unlinkSync(src);                           // only after the append succeeded
}
```

The second branch is the fix. When the destination already exists, append the source content to
it and only then delete the source. The source must never survive just because the destination was
already there.

### Step 2: make the exit condition "source is empty", not "destination exists"

```js
function reconcile(srcDir, destFile) {
  let moved = 0;
  for (const name of fs.readdirSync(srcDir)) {
    migrate(`${srcDir}/${name}`, destFile);
    moved += 1;
  }
  return moved;
}
```

Loop over whatever is in the source directory instead of checking one destination path. That also
covers the files that arrive *after* the first pass: a writer that started before the hot reload can
add another file a second later, and a per-file check notices it while a one-shot `exists(dest)`
check never looks again.

### Step 3: make the migration safe to re-run

The operation must be idempotent, because the failure case guarantees it will run more than once
(next startup, next reload). Running it twice must be a no-op: after a clean pass the source
directory is empty, so every branch returns immediately.

### Step 4: keep the ordering (append, then unlink)

Deleting the source first and appending afterwards turns a crash into data loss. Append first, then
unlink; a crash between the two may duplicate content on the next run, which is recoverable, while
the reverse order is not.

## Verification

The reporter re-ran the startup migration and observed the expected end state: the source directory
was empty and the destination contained the appended lines — no data lost, no orphans. This is
reporter-reported and was not reproduced in this repository.

Checkable criteria, in order:

1. Before the run: the source directory is non-empty **and** the destination already exists. This is
   the state the old code skipped; if you cannot reproduce it, you have not tested the fix.
2. After the run: `ls -A <source-dir>` prints nothing, and the destination has grown by exactly the
   source's content (diff the destination against a pre-run copy: the added lines must be the
   source's lines, in order).
3. Second run: it returns immediately, the destination is byte-identical, and no duplicate lines
   appear.

If the source still contains files after the run, the `(present, present)` branch is still missing
or still failing silently.

## Notes

- Append-then-unlink is not atomic. A crash between the two calls duplicates the source content in
  the destination on the next run, so a migration that merges non-idempotent records (for example,
  lines with timestamps) needs a dedupe step or a marker. The reporter did not describe handling
  this case; it needs to be reproduced and confirmed.
- The reporter does not say whether the old process writing to the source path was stopped, or
  whether a periodic re-check was added. Either way, the migration must be re-run after that writer
  exits; the intake does not record which option was taken.
- The same shape appears in "migrate config file" code generally: any `if (!exists(newPath))` guard
  around a move handles the easy half and silently drops the half where the user already has data.
- Evidence level E1: reporter-reported symptom and fix; not independently reproduced here.
