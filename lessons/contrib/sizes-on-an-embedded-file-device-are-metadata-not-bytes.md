---
title: "Sizes on an embedded file device are metadata, not bytes — verify transfers by what landed"
domain: "fanuc"
tags:
  - "ftp"
  - "file-transfer"
  - "manifest"
  - "timeout"
  - "verification"
status: "published"
evidence_level: "E1"
created: "2026-11-18"
updated: "2026-11-18"
source: "intake-4755"
summary_plain: "控制器的 LIST size 是逻辑元数据（.TP 报源大小、.LS 报 0），SIZE 命令不支持；批量传输要靠落盘字节数和旁路清单对账，而不是比大小。"
trigger: "FTP SIZE command unsupported LIST size not bytes TP reports source size LS reports 0 batch RETR timeout cannot read from timed out object"
verify: "Download a batch, then compare file count and bytes on disk against a sidecar manifest written during the transfer. Comparing LIST sizes instead flags files that transferred perfectly."
provenance:
  issue: "#4755"
  source: "MCP intake (claude-code), contributor-reported"
---

## Problem

A full download of ~190 files from an embedded controller had two failures at once. After ~380
transfers the control connection was poisoned (`OSError: cannot read from timed out object`) and the
FTP service then refused connections entirely while the web UI still answered 200. And the sizes never
matched: `SIZE` returns `500` (unsupported), and the numbers in `LIST` are not bytes — a `.TP`
reported 132 (its *source* size) while the file on disk was 74 bytes, and a `.LS` reported `0` while
the transfer carried five digits.

## Root Cause

Two independent assumptions, both reasonable on a real filesystem:

1. **A socket timeout sized for one request is too short for a batch.** With a 10 s default, one stall
   longer than that poisons the buffered reader and every later read on that connection fails. The
   device's FTP daemon can also wedge under dense transfers, independently of its HTTP side.
2. **`LIST`'s size column is logical metadata**, not a byte count, and `SIZE` is not implemented. So
   "compare the size to the downloaded file" produces mismatches on transfers that were perfect — and
   a manifest that trusts it will report a broken backup when the backup is fine.

## Fix

Verify by **what landed**, and keep the timeout in the batch's own terms:

```python
ftp.sock.settimeout(120)                      # a batch, not one request
for path in paths:
    try:
        n = 0
        with open(dest, "wb") as fh:
            def sink(chunk):
                global n
                fh.write(chunk); n += len(chunk)
            ftp.retrbinary(f"RETR {path}", sink)
        manifest[path] = n                    # bytes on disk: the only size that means anything
    except (ftplib.error_temp, OSError):
        reconnect()                           # one retry per file, then record the gap
```

Write the manifest **beside the output, not inside the backup tree** — otherwise the next run's
reconciliation counts the manifest as a backup file. Files whose content is regenerated on read
(reports, rolling logs) are listed separately and do not count as failures: their hash changes between
two reads of the same file.

## Verification

```console
$ python3 fetch_all.py --dest out/
backup ok: 194 files, 6793139 bytes
$ python3 - <<'EOF'
# manifest count == FTP file count, per-file bytes == bytes on disk, rerun skips 194
EOF
```

Before the fix, every run ended with size mismatches on files that were complete. After it, the
mismatch list is empty for stable files and the regenerated ones are named instead of counted.
