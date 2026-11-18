---
title: "Listing a directory on an embedded controller can be the one operation that kills it"
domain: "fanuc"
tags:
  - "ftp"
  - "nlst"
  - "roboguide"
  - "controller"
  - "crash"
  - "memory"
status: "published"
evidence_level: "E1"
created: "2026-11-18"
updated: "2026-11-18"
source: "intake-5166"
summary_plain: "在虚拟控制器的内存设备上列目录会把设备服务打死（内存分配失败 → 访问违例 → OS-145 锁存），而同设备上单文件读写是安全的。"
trigger: "FTP NLST MD: controller crash cptable_expand bad status VARS-021 memory allocation failure DVNEWMD NTOS-001 access violation OS -145"
verify: "On a healthy controller, a 16-byte STOR probe returns 226 and the log stays clean; listing the directory instead ends in cptable_expand and OS -145. Never use a listing to test writability."
provenance:
  issue: "#5166"
  source: "MCP intake (claude-code), contributor-reported"
---

## Problem

Listing a memory-device directory over FTP **took the controller down**: the listing hung, the log
filled with `[mdserv] bad status from cptable_expand = 0x100015` and `VARS-021 Memory allocation
failure`, then the device DLL raised `NTOS-001 Memory access violation` and the controller latched
`OS -144 / OS -145` — a state that needs a power cycle.

The dangerous part is not the crash; it is that it reads as "FTP is not working" or "the device is
write-protected", which sends you into the network and the password instead of away from the listing.

## Root Cause

On this device, the directory service expands its own character table to build a listing. Given an
invalid status (`0x100015`) it fails to allocate, and the failure surfaces as an access violation in
the service that owns memory — so **the listing is a write-shaped operation on internal state**, not
a read. Single-file `RETR` and `STOR` against the same device are fine: measured on the same machine,
`STOR UD1:...` answers `226`, and the crash only arrives with the listing.

Absence of evidence that a "read" can be dangerous is common: FTP's verbs suggest reads are safe. On
an embedded controller, "list" is a different code path from "read one file", and it can be the one
that allocates.

## Fix

Treat the device as **files, not a filesystem**:

```python
# Never: ftp.nlst("MD:")   # expands the device's directory table; can kill the controller

# Single-file only. Writability is proven by a small real write, not by a listing.
probe = io.BytesIO(b"PROBE-16-BYTES!!")
ftp.storbinary("STOR MD:PROBE.TP", probe)      # 226 == writable; 550 == refused, and that is safe
```

And when the log shows `cptable_expand` or `OS -145`, stop touching that controller: cycle it
(power, reopen the workcell, wait for the boot window) before continuing. Continuing after the first
`0x100015` is what turns a wedged service into a latched controller.

## Verification

On a healthy controller:

```console
$ python3 probe.py   # 16-byte STOR to the target device, then read the log back
STOR ... -> 226 Binary Transfer complete
log      -> no cptable_expand, no OS -145
```

`550` or a timeout on the probe means "refused", which is a safe answer. A listing is never a valid
way to test writability: on this device it is the test that causes the failure.
