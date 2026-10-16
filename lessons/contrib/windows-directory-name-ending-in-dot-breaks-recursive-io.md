---
domain: "windows"
title: "A Windows directory name ending in a dot breaks ripgrep, glob and recursive IO (os error 3)"
tags:
  - "windows"
  - "ripgrep"
  - "glob"
  - "path-normalization"
  - "trailing-dot"
  - "os-error-3"
status: "published"
evidence_level: "E1"
source: "intake-3068"
summary_plain: "A Windows folder whose name ends in a dot is listed but cannot be opened, so recursive search dies with os error 3."
trigger: "rg: IO error for operation on ...: 系统找不到指定的路径 / The system cannot find the path specified (os error 3) on a path whose last component ends with a dot"
verify: "Test-Path -LiteralPath on the trailing-dot name returns False while Get-ChildItem on the parent lists that exact name; prefixing the path with \\\\?\\ makes Get-ChildItem list its contents."
provenance:
  issue: "#3068"
  source: "dsh (node Misaka28603) lesson_submission"
  evidence: "self-observed"
  note: "Contributor-reported on Windows (PowerShell 7); not reproduced in this repository. The submitter's real directory names and profile path are replaced by the placeholders <parent>, <id> and <user> in the text below."
---

# A Windows directory name ending in a dot breaks recursive IO

## Problem

A recursive search over a Windows user profile failed part-way through on a path that the
parent directory listing had just displayed:

```
rg: C:\Users\<user>\.dsh\profiles\desktop\.backup-memos-<id>.: IO error for operation on ...:
系统找不到指定的路径。 (os error 3)
```

The directory name ended with a literal dot (`.backup-memos-<id>.`). The parent enumerated the
name correctly — including the trailing dot — but nothing that tried to **open** that name
worked:

```powershell
Test-Path -LiteralPath '<parent>\.backup-memos-<id>.'      # -> False
Get-ChildItem -LiteralPath '<parent>\.backup-memos-<id>.'  # -> ItemNotFoundException: 找不到路径
```

The tool impact is the real cost: ripgrep / a `glob` walk aborts the whole traversal, or
silently loses that subtree, on a directory that has nothing to do with the query. An agent
that discovers files by globbing a home or profile directory gets an IO error instead of
results, and the error names a path the same listing says exists.

## Root Cause

Win32 path normalization strips **trailing dots and trailing spaces** from each path component
before the path is handed to the filesystem. A component literally named `dir.` is therefore
opened as `dir`, which does not exist.

Directory *enumeration*, by contrast, uses `FindFirstFile` semantics and returns the on-disk
name unchanged. That asymmetry is the whole trap: the same name is simultaneously **listed**
and **unopenable**, so `stat`, `open` and any recursive descent into it fail with
`ERROR_PATH_NOT_FOUND` (os error 3). Any walker that trusts the enumerated name and then opens
it — ripgrep, `glob`, `Get-ChildItem -Recurse` — trips over it.

The ghost is usually tool-created. Some Win32 creation APIs strip a trailing dot at creation
time while others do not, so a backup or scratch directory written by a script can end up in
the state where it exists on disk under a name that normal path handling can no longer reach.

## Solution

Any one of these, in order of preference:

```powershell
# 1. Don't enter it at all: exclude the path, or narrow the search root to real project dirs
rg --glob '!**/.backup-memos-*' "<pattern>" <search-root>

# 2. Reach it with the extended-length prefix, which skips Win32 normalization entirely
Get-ChildItem -LiteralPath "\\?\C:\Users\<user>\.dsh\profiles\desktop\.backup-memos-<id>."

# 3. Rename it so the name no longer ends in a dot — the prefix is needed on BOTH sides
Rename-Item -LiteralPath "\\?\C:\Users\<user>\.dsh\profiles\desktop\.backup-memos-<id>." `
            -NewName 'backup-memos-<id>'
```

And when *creating* directories programmatically:

```powershell
# 4. Never emit a trailing dot or space in a path component you construct
$name = $rawName.TrimEnd('.', ' ')
```

Two boundaries of the `\\?\` prefix, both of which cause silent misbehavior if ignored: it
disables all normalization (so `/` separators and `.`/`..` segments are passed through
verbatim), and the path must be fully qualified — a relative path after `\\?\` is not resolved
against the current directory.

## Verification

The failure has a cheap two-command signature, and it is worth running both halves — either one
alone is ambiguous:

1. `Test-Path -LiteralPath '<parent>\.backup-memos-<id>.'` returns **False**, while
   `Get-ChildItem '<parent>' -Force | Where-Object Name -like '.backup-memos*'` returns that
   exact name. "Listed but not testable" is the signature of the normalization strip.
2. `Get-ChildItem -LiteralPath "\\?\<same path>"` returns the directory's contents (observed: a
   `package.json` / lockfile set), which confirms the name is real and reachable only through
   the prefix.

After the rename in fix 3, the normal form `<parent>\backup-memos-<id>` is `Test-Path` True and
a recursive search over the parent completes without `os error 3`.

## Notes

* Domain note: the submitter labelled this `windows`, which is now part of the
  `data/domains.json` vocabulary, so the lesson keeps that domain.
* The root cause is in Win32 path handling, so the same failure reaches any tool built on it —
  this is not a ripgrep bug. The fix that generalizes is fix 4: do not create such names, and
  do not assume a name that came out of a directory listing can be opened.
* A directory that cannot be opened is also invisible to `Test-Path`-based existence checks, so
  a "directory exists" assertion will report the opposite of what the listing shows.
