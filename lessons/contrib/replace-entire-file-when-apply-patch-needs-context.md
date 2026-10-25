---
title: "Replacing a whole file when apply_patch only speaks context: delete + add, then verify bytes"
domain: "development"
tags:
  - "apply-patch"
  - "file-editing"
  - "whole-file-replace"
  - "write-file"
  - "verification"
  - "operations"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "apply_patch 是上下文锚定的补丁格式，整文件替换要用 Delete File + Add File（或客户端的整文件写工具），写完必须回读字节数与哈希。"
trigger: "apply_patch replace entire file whole content context mismatch delete add file"
verify: "替换后回读文件：字节数与 sha256 等于新内容，且旧内容无残留；空文件与 CRLF 文件各跑一次。"
source: "intake-3658"
provenance:
  issue: "#3658"
  source: "MCP intake (reporter)"
  evidence: "Derived from the apply_patch format's own semantics; not reproduced against a specific client build in this repository."
---

# Replacing a whole file when apply_patch only speaks context: delete + add, then verify bytes

## Problem

A file-editing client that drives `apply_patch` has to replace a text file **in full** — the new
content has nothing in common with the old, so there is no useful context line to anchor a hunk to.

The obvious encoding is one giant hunk: every old line as `-`, every new line as `+`. It works on a
small file with identical whitespace and then stops working, because the hunk is only applied if the
context matches **exactly**:

- CRLF vs LF line endings
- a missing or extra trailing newline
- trailing whitespace the editor stripped
- a file large enough that the client truncates the patch

When the context does not match, the patch is rejected and the file is untouched — the caller sees a
failure it cannot distinguish from "the file changed under me".

## Root Cause

`apply_patch` is a **context-anchored** format. Its unit of work is "find this, replace it with that".
A whole-file replacement is not a big hunk; it is a different operation — *the file is gone and a new
file exists at the same path*. The format already has that operation, and it needs no context at all.

Encoding a whole-file replace as a maximal hunk makes correctness depend on the old content being
reproduced byte-for-byte by the caller. The caller usually has the old content (it just read the
file), so this looks safe — but the caller has it *as the client decoded it*, which is exactly the
layer where line endings and trailing newlines get normalised. The hunk then encodes the client's
view of the file, not the file.

## Solution

### Step 1 — express the replacement as delete + add, in one patch

```
*** Begin Patch
*** Delete File: src/config/loader.ts
*** Add File: src/config/loader.ts
+<every line of the new content, prefixed with +>
*** End Patch
```

No context lines, so nothing to mismatch. Both operations are in the same patch, so a client that
applies patches atomically never exposes a window where the path is missing.

### Step 2 — if the client has a full-write tool, prefer it

A `write_file`-style tool (truncate + write) is the direct expression of the same intent and avoids
the patch parser entirely. Use delete + add only when the patch is the only channel available.

### Step 3 — handle the two edge cases the format makes awkward

- **Empty new content.** `*** Add File:` with zero `+` lines. Do not fall back to a hunk; an empty
  hunk is indistinguishable from "no change".
- **File mode.** Delete + add creates a *new* file, so an executable bit or a non-default mode is
  lost. Re-apply it (`chmod +x`) after the patch, or use the full-write tool, which keeps the inode.

### Step 4 — verify by reading the file back, not by trusting the tool's report

The tool's success message is a claim about the sandbox, not about the disk. After the write:

1. `wc -c <path>` — must equal the byte length of the new content.
2. `sha256sum <path>` — must equal the hash of the new content.
3. grep for a distinctive string from the **old** content — must be absent.

If the byte count matches but the hash does not, the write landed with different line endings. If the
byte count does not match at all, the write did not land — see
`lessons/contrib/deepseek-tui-write-file-sandbox-worktree-git-path.md` for that failure mode.

## Verification

Run the replacement against three fixtures and check the three readbacks above for each:

1. a file with content (the normal case)
2. an empty file → non-empty, and non-empty → empty
3. a CRLF file, replaced with LF content

All three must end with the exact expected bytes. A pass on case 1 alone does not test the fix; cases
2 and 3 are the ones the hunk encoding fails.

## Notes

- **Trade-off, stated plainly:** delete + add breaks git's rename/blob continuity for that path, so
  `git log --follow` and blame stop at the replacement. If history continuity matters more than
  robustness, use the full-write tool (same inode, same blob lineage) rather than a hunk.
- **Not reproduced here.** The failure of the maximal-hunk encoding on CRLF/trailing-newline files is
  derived from the format's matching rules, not from a recorded run against a named client. Treat the
  specific rejection messages as unconfirmed; the delete + add encoding and the readback checks do not
  depend on them.
- The same shape appears in any context-anchored editor: the reliable whole-file path is always
  "remove, then create", never "one enormous hunk".
