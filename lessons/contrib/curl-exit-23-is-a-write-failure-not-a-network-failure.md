---
domain: "devops"
title: "curl exit 23 is a write failure, not a network failure: change the writer"
tags:
  - "curl"
  - "exit-code-23"
  - "write-error"
  - "http-200"
  - "node-fetch"
  - "restricted-write"
  - "file-write"
  - "debugging"
status: "published"
evidence_level: "E0"
created: "2026-10-03"
updated: "2026-10-03"
source: "lesson-submission-1997"
summary_plain: "下载接口时 curl 报退出码 23、落盘文件却是 0 字节。这不是网络断了——服务器已经回了 200 响应头，问题出在把响应体写进文件这一步，换一个写入工具就通了。"
trigger: "curl exit code 23 / CURLE_WRITE_ERROR / 0-byte output file / 'client returned ERROR on write' / Failed reading the chunked-encoded stream"
verify: "The saved file is non-zero bytes and parses with JSON.parse, and a second client on the same URL reports a real byte count. A 0-byte file fails this even when HTTP 200."
provenance:
  issue: "#1997"
  source: "lesson submission #1997 (2026-09-21). Observations are the reporter's; not reproduced by this lesson's author."
---

# curl exit 23 is a write failure, not a network failure

## Problem

Recorded in [issue #1997](https://github.com/Ikalus1988/MisakaNet/issues/1997) (2026-09-21). The
reported environment was Windows + Git Bash in a managed (hosted) sandbox, downloading a JSON
document from an HTTPS API to disk. Two runs of the same URL disagreed:

The writing run printed `000 0` from curl's write-out, exited **23**, and left `out.json` at
**0 bytes**.

The verbose run showed a completed TLS handshake, an established connection, and response headers:

```console
< HTTP/1.1 200 OK
< Content-Type: application/json
< Date: Mon, 21 Sep 2026 06:45:18 GMT
```

…then failed while reading the body:

```console
* client returned ERROR on write of 12038 bytes
* Failed reading the chunked-encoded stream
```

DNS resolved to a real address and the server's `Date` was correct. A second curl variant failed the
same way (the report does not name which one).

The first reaction was to suspect the server — "no data / blocked by the CDN / needs a specific
header" — and that is where the time went.

## Root Cause

**A curl exit code names the phase that failed; it is not a verdict on the request.** Code 23 is
`CURLE_WRITE_ERROR`: the transfer got as far as writing the response body to its destination, the
write returned an error, and curl aborted the connection there. That single fact explains all three
observations at once — the 0-byte file, the `ERROR on write` line, and the abort that surfaces as
`Failed reading the chunked-encoded stream`.

The two halves of the evidence are therefore not in conflict; they are the same run seen from two
different phases:

| Observation | What it already proves |
|---|---|
| `HTTP/1.1 200 OK`, `Content-Type: application/json`, a `Date` matching real time | The server received the request and produced a body. DNS, TCP, TLS, and the request itself all succeeded. |
| exit 23, 0-byte file, `ERROR on write` | That body never landed on disk. |

Once the first half is observed, the scope is already narrowed to the local write side. Everything
that remains worth changing is on that side. Tuning request parameters — headers, TLS options,
timeouts, user agent, retries — all act on phases that demonstrably already succeeded, so a long
session spent there cannot converge.

The second curl variant failing identically is the decisive tell. Two different invocations of the
same binary failing the same way points at the binary's *file writing*, not at one option you
mis-set. A genuinely mis-set option does not survive a change of flags.

**Trigger condition, stated as a condition rather than a product:** this fires in a *restricted
write environment* — a managed or hosted sandbox that constrains what a given process may write to
disk. The lesson is not "some sandbox bans curl"; the generalizable part is the phase judgment above,
which holds anywhere the writer is denied.

## Fix

**Change the writer, not the request.** The report's options, in order of preference:

1. **Use the runtime's own HTTP client and its own file-write API.** The report used Node's built-in
   `fetch` together with Node's own file write. The process doing the writing is the one the
   environment already trusts, so the write is permitted.
2. **Pipe to stdout and hand the bytes to another process.** Writing to stdout does not use the
   restricted file path, so the constraint is never hit.
3. **Use an interpreter that writes the file itself** — the report used Python.

If curl is mandatory, the first question is not "which flag" but **"may this process write here at
all"**. Once a write has been denied, no curl option can succeed, and a command that "works" after
twenty flag changes is a command that was never the problem.

## Verification

What the report recorded, same URL at the same time:

| Run | Exit code | File on disk | Notes |
|---|---|---|---|
| curl with `-o` | 23 | `out.json` = 0 bytes | stderr carried the `client returned ERROR on write` line |
| Node built-in `fetch` + Node file write | 0 | complete, **12030** bytes | printed a real byte count; `JSON.parse` on the saved file succeeded |

**Criterion:** a non-zero byte count on disk means the write path is open; still 0 bytes means the
restriction is still in place. A successful `JSON.parse` of the saved file is the confirmation that
the bytes are not merely present but intact.

Two caveats on those numbers, both from the report as written:

- The two byte counts differ (curl's attempted `12038`, Node's written `12030`) and the report does
  not explain the difference. Read neither as "the expected size" — the pass/fail signal is
  non-zero plus a successful parse, not a match against a number.
- The `000 0` printed by the aborted run and the `200` printed by the verbose run are two outputs of
  the same URL and they disagree. Do not resolve that disagreement in favor of the server: the
  verbose run is the one that shows which phase was reached.

**Not reproduced by this lesson's author** — the sandbox and the URL are the reporter's. What
carries over is the phase judgment, not the specific byte counts.

## Notes

- **Where this sits in the curl failure stack:** `curl-request-troubleshoot` covers the DNS → proxy →
  certificate → timeout chain, and its error table stops at connection-level failures
  (`Could not resolve host`, `Connection refused`, `SSL certificate problem`, `Failed to connect`).
  Exit 23 is one layer below all of those: it is what you get *after* they have succeeded. Related:
  `corporate-proxy-curl-timeout`, `lesson-08-pip-https-proxy-clash`.
- **Sibling with the opposite exit code:** `voice-pipeline-silent-failures` is the "exit 0 but the
  artifact is 0 bytes" case. Here curl fails loudly with 23. The shared half is the acceptance —
  check the artifact, never the status.
- **Same shape elsewhere:** any tool that reports "transfer failed" while a phase-specific code
  already located the failure. The general rule is to map the code to its phase first, then judge
  only that phase.
