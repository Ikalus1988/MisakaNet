---
title: "ftplib reports a server's immediate refusal as a timeout, so \"rejected\" looks like \"unreachable\""
domain: "python"
tags:
  - "ftplib"
  - "ftp"
  - "timeout"
  - "status-code"
  - "diagnosis"
status: "published"
evidence_level: "E1"
created: "2026-11-18"
updated: "2026-11-18"
source: "intake-5183"
summary_plain: "服务器对 STOR 立刻回 550 时，ftplib 等在等 150/数据通道，最后抛 TimeoutError —— 把「被拒绝」报成「链路不通」，于是去查网络全白费。"
trigger: "ftplib stor Timed out 550 operation password protected data channel fine passive mode connected blocked status code 5xx"
verify: "Run the sequence with a raw socket (USER, PASS, TYPE I, PASV, connect data port, STOR) and print the server's reply line. A 550 there, where ftplib raised TimeoutError, is the whole diagnosis."
provenance:
  issue: "#5183"
  source: "MCP intake (claude-code), contributor-reported"
---

## Problem

Every upload to an embedded controller's FTP service failed with `TimeoutError: timed out`. The
natural reading — the data channel is blocked — sent the investigation into loopback, firewall and
passive-mode settings. All of them were fine: the passive data connection was established in
`0.00s`.

## Root Cause

`ftplib` sends the command and waits for a **preliminary** reply (`150`) before it starts pushing
data. The server refused immediately with `550 Operation password protected`, so there was never a
`150` to wait for; the library waited for its socket timeout and raised `TimeoutError`. The exception
names the wrong layer: the server answered, promptly and specifically.

The refusal itself is a separate fact: on that device, writing a program file is a privileged
operation, and whether it is allowed depends on **which channel the request arrives from** — a
console, a local command layer, or the network. The FTP service is the network channel, and it has no
way to ask for that password, so it can only refuse.

## Fix

Ask the server, don't infer from the exception:

```python
import ftplib, socket
ftp = ftplib.FTP()
ftp.connect(host, 21, timeout=30)
print(ftp.getwelcome())        # 230 ... [NORM]
ftp.login("anonymous", "anonymous@")
ftp.sendcmd("TYPE I")
ftp.sendcmd("PASV")            # print this: 227 Entering Passive Mode (…)
conn, _ = ftp.ntransfercmd("STOR MD:PROBE.TP")   # raises only on a real 5xx, with the code
```

Then read the reply code, not the wall clock: `550` is "refused, and here is the reason"; a timeout
with a live data channel is worth investigating; a timeout with no `227` is a connectivity problem.
Sending a small probe first turns the question into one line of output.

## Verification

```console
$ python3 probe.py --host <controller>
230 User logged in [NORM]
227 Entering Passive Mode (127,0,0,1,236,140)
STOR MD:PROBE.TP -> 550 Operation password protected
```

The same probe against a writable device answers `226`. In both cases the data channel is established,
which is the fact `TimeoutError` hid.
