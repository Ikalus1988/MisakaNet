---
domain: "nodejs"
title: "A child stat failure must not fail the whole parent directory listing"
tags:
  - "nodejs"
  - "filesystem"
  - "error-handling"
  - "windows"
  - "acl"
  - "listing"
  - "degradation"
status: "published"
evidence_level: "E1"
created: "2026-10-03"
updated: "2026-10-03"
source: "intake-2314"
summary_plain: "One locked sub-folder made the whole folder listing fail, so the app showed an empty file list."
trigger: "FsError: cannot list \"<child>\": permission denied FS_PERMISSION_DENIED listingIoError one-level listDir fails"
verify: "Listing a parent that contains an ACL-denied child returns entries with that child as type=other plus an unresolved count, and throws nothing."
provenance:
  issue: "#2314"
  source: "MCP intake (dsh), contributor-reported"
---

## Problem

On Windows, with the process working directory inside a protected system directory, a
"list the first level of the workspace" feature failed outright instead of degrading. In the DSH Web
`dsh-novel-forge` panel, scanning the workspace for books (`GET /projects`) rendered:

```
FsError: cannot list "C:\Windows\System32\WebThreatDefSvc": permission denied
```

The book list was permanently empty, and users read that as "my projects are gone". The same failure
appeared on other protected children of that directory — `config\BFS`, `LogFiles\WMI\RtBackup` — and
on a volume root, `System Volume Information`.

Minimal repro: process cwd is a directory that contains an ACL-restricted subdirectory, then call a
one-level `listDir` on it. The cwd is easy to land on by accident: an elevated terminal, or a Windows
shortcut with no "Start in" set, both start in `C:\Windows\System32`.

## Root Cause

Two separate mistakes stack, and the listing one hides behind the caller one.

**1. A child's failure is reported as the directory's failure.** `listDirectory` in `dsh-fs-local`
(JavaScript) does the right thing at the `readdir` step, then enriches each returned entry with
`resolveListedChildTarget` plus a `probe` (`stat`). That enrichment failure is thrown as a
*directory-level* error. As reported by the contributor, `dsh-fs-local/lib/index.js` throws
`listingIoError(join(target.displayPath, entry.name), error)` at ~line 304, and `listingIoError`
(~line 251) returns `FsError('cannot list "<child>": permission denied', FS_PERMISSION_DENIED)`.

The permission denial is real. The *scope* is wrong. `readdir` succeeded and the parent is perfectly
listable — one child's `stat` failing is not the parent's failure. The branch's own comment assumes
"Windows chmod does not refuse directory listing"; on a protected system directory the ACL refuses
`stat` outright, so that assumption fails and a single child poisons the whole listing. The message
then names the child while being thrown as if the parent were the thing that could not be listed,
which is why the failure reads as a permission problem with System32 itself.

**2. The caller has no per-root isolation.** The scanning side (`dsh-novel-forge/lib/server-api.js`)
builds roots as `[process cwd, ...session workspaces]` (`collectRoots`, with
`roots[0] = config.workspaceRoot || process.cwd()`) and `scanBooks` issues a one-level
`fsio.listDirs('.')` with no `try`/`catch` per root. One unreadable root therefore aborts the entire
scan, and the raw `FsError` goes straight to the user.

Why the workspace looked *empty* rather than partially populated: the registered session workspaces
were independently found to have been deleted or moved, so once the first root threw, the scan had no
fallback root left to answer with. "The projects are gone" is a reporting artifact, not data loss.

## Fix

Two independent changes. The second is still required after the first lands.

**A. The listing API — upstream, in the external package.** This is the actual fix and it does
**not** belong in this repository: `dsh-fs-local` is an external package, and a repository-wide
search for `dsh-fs-local` and `listingIoError` returns nothing. Report and fix it in the upstream
project; editing code here will not change this behaviour. The correct shape:

- Reserve directory-level failure for `readdir` itself. If the directory cannot be opened or
  enumerated, that is the *only* condition allowed to throw a "cannot list" error.
- A failed child `stat` degrades instead of throwing: keep the entry with `type` set to
  `unknown` / `"other"`, and count it (e.g. `unresolved`).
- Return that count alongside the entries, so a caller can tell "listed, 1 entry unresolvable" from
  "listed everything".

**B. The scanning caller — per-root `try`/`catch`, one failure per root.**

```js
const roots = collectRoots();
const items = [];
const unreadable = [];

for (const root of roots) {
  try {
    items.push(...scanBooks(root));
  } catch (err) {
    unreadable.push({ root, message: err instanceof FsError ? err.message : String(err) });
  }
}

// Answer with what did list, and state the shortfall rather than hiding it.
return { items, rootsScanned: roots.length, rootsUnreadable: unreadable };
```

**C. The UI.** `FsError` is not a user-facing string. Map it to a sentence that names the root and
says what happened — *"1 of 3 scan roots is unreadable: `C:\Windows\System32` (permission denied).
The other 2 were listed."* — and never render a raw error where an empty list is also possible.

**User-side workaround**, independent of all of the above: start the service from an ordinary
directory. Note that switching the workspace *inside* the app is not enough — `roots[0]` is the
process cwd, so the protected root is still scanned and still throws. On Windows, set "Start in" on
the shortcut.

## Verification

What was actually observed on the reporter's machine:

1. With cwd = `C:\Windows\System32`, a one-level list of the workspace root throws `FsError` /
   `FS_PERMISSION_DENIED`, with the message path pointing at `WebThreatDefSvc`.
2. An independent directory-walk tool on the same three paths reports "拒绝访问 (os error 5)", which
   rules out a bug local to the plugin.
3. End-to-end contrast on the same machine: restart with cwd on an ordinary directory → the book-list
   endpoint returns 200 with entries; set cwd back to `System32` → the red error and the empty list
   return.
4. The registered session workspaces (`~/.dsh/storages/workspace.json` and the session projcache) were
   checked and found deleted or moved, so the scan had no remaining root to fall back on.

The code fix (A) is **not** applied — the code is not in this repository — so the following is the
criterion the fix must meet, not a result that has been observed:

5. Construct a parent directory containing a child whose ACL denies `stat` to the current user
   (`icacls` on a scratch directory), then call the one-level list: before the fix it throws with the
   child's path in the message; after the fix it returns the entries with that child as
   `type=other` / `unknown` plus the unresolved count, and does not throw.
6. Point the scanner at 3 roots of which 1 is unreadable: the response lists the readable roots and
   reports "2 of 3 roots readable" instead of failing.

## Notes

- **Scope of the evidence.** The failing code path was read in the external `dsh-fs-local` package;
  the line numbers are as reported by the contributor and were not re-verified here, and the
  Windows environment was not reproduced in this repository. Treat the mechanism as the portable
  part and the specific build as as-reported.
- The portable rule: **a child probe failure must not poison the parent listing.** `readdir` failing
  is a directory error; `stat` failing is a per-entry fact. Any "list, then enrich" API has to keep
  those two scopes apart, and any fan-out over N roots has to isolate failures per root and report the
  shortfall. Both halves are needed — fixing only the listing leaves a caller that still aborts on the
  first unreadable root, and fixing only the caller leaves a listing that dies on one locked sub-folder.
- Related: `lessons/contrib/dsh-home-robocopy-junction-fallback-breakage.md` — another Windows-side
  dsh failure where a check encodes an assumption about the environment that does not hold.
