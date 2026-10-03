---
domain: "python"
title: "A pystray menu crash on macOS is an AppKit main-thread violation in a background thread, not a host-app bug"
tags:
  - "pystray"
  - "appkit"
  - "macos"
  - "main-thread"
  - "crash-report"
  - "serena"
  - "mcp"
status: "published"
evidence_level: "E0"
created: "2026-10-03"
updated: "2026-10-03"
source: "intake-2261"
summary_plain: "macOS 反复弹 python3.14 quit unexpectedly，崩的其实是后台托盘线程：pystray 在后台线程调 NSStatusItem.setMenu，违反 AppKit 主线程约束，宿主 app 只是背锅。"
trigger: "EXC_BREAKPOINT SIGTRAP NSStatusItem setMenu on process_request_thread pystray python quit unexpectedly"
verify: "With web_dashboard_interface: browser and a restarted server: MCP init completes, 24 tools list, initial_instructions answers, loopback dashboard returns HTTP 200, no tray helper starts."
provenance:
  issue: "#2261"
---

## Problem

A macOS 27 desktop MCP client repeatedly shows **"python3.14 quit unexpectedly"**. The crash coalition
names the host app, so the first reading is that the host application is crashing — and the search
starts there.

Two things in that report point somewhere else:

- the coalition naming the **host app** rather than the helper that supposedly crashed;
- the absence of any Python traceback. `python3.14 quit unexpectedly` is a crash-report notification,
  not an exception.

Local process ancestry and the server logs identify the actual process: **Serena 1.7.0's detached
dashboard tray manager**. Its Flask request handlers and its alive-check thread call
**pystray 0.19.5 `update_menu`**, which calls `NSStatusItem.setMenu` directly off the main thread.

```text
EXC_BREAKPOINT (SIGTRAP): -[BSServiceMainRunLoopQueue assertBarrierOnQueue],
-[NSStatusItem setMenu:] on process_request_thread or _alive_check_loop
```

The `on <thread_name>` suffix is the payload of the message. The framework is not naming the app that
died; it is naming **the thread that violated the rule**.

## Root Cause

AppKit requires UI objects — `NSStatusItem` among them — to be touched on the **main thread**.
`update_menu` is a UI mutation: it re-points the status item at a new menu. When the caller is a Flask
request thread (`process_request_thread`) or the tray's own alive-check thread
(`_alive_check_loop`), that mutation happens off-main, and AppKit's assertion traps instead of letting
the call proceed.

Two consequences explain the whole confusing report:

**The crash is correct enforcement, not corruption.** `SIGTRAP` / `EXC_BREAKPOINT` is an assertion
firing. That is why the symptom is a "quit unexpectedly" dialog with no Python traceback — the process
never got far enough to raise an exception, it was stopped at the boundary.

**The coalition names the host app because the tray is not a separate process.** It runs *in* the MCP
server process, as a thread. A thread that traps takes its process — and therefore its coalition —
down with it. "The host app crashed" and "a background thread of the server violated a main-thread
rule" are the same event seen from two sides. Searching the host binary for the bug is searching in
the wrong process.

### Scope of this claim

Read this before generalising, because the two halves have different standing.

**Mechanism — generalisable.** The main-thread-only rule is a platform property of AppKit, not a
property of one machine, and "the tray's menu is updated from a request thread" is a fact about the
calling structure in the code. Any macOS host that runs this code path has the same shape.

**Observation — single machine.** What was actually captured is one crash log from one machine on one
macOS version, over a bounded test window. Whether the assertion *fires* additionally depends on the
caller being off-main at that call site and on AppKit's main-thread checker being armed. So "this hits
any macOS user" is a mechanism-level inference, not a reproduced result.

Practical consequence: do not cite this as a confirmed macOS-wide bug. Use it to form the hypothesis,
then **confirm it against your own crash report** — the thread name in the message is the check.

## Fix

Use Serena's supported global setting **`web_dashboard_interface: browser`**. Keep `web_dashboard: true`
and the user's existing auto-open preference.

```yaml
web_dashboard: true
web_dashboard_interface: browser
```

This avoids the native tray path entirely without changing Python, package files, or MCP availability.

Two things that are part of the fix, not afterthoughts:

- **Existing servers must be restarted** to load the new selection. A server that is already running
  keeps the tray selection it started with, so "I changed the setting and it still crashed" is
  expected until it is restarted.
- **The setting name is the documented handle.** The intake identifies the setting and its value; it
  does not pin a config file path, so take the path from Serena's own configuration documentation
  rather than assuming one.

## Verification

From the submitted report, against a **fresh server using the existing installed environment** after
applying the setting and restarting:

```text
PASS  MCP initialization completed
PASS  server listed 24 tools
PASS  initial_instructions answered
PASS  loopback dashboard returned HTTP 200
PASS  no tray helper was started
PASS  no new Python crash report appeared during the bounded test
PASS  the owned test server exited cleanly
```

The dashboard is still reachable and still serves over HTTP, and the tool surface is unchanged — that
is what makes this a workaround rather than a downgrade: only the native tray path is gone.

**What this does not establish.** It is a verified local workaround. It is not an upstream code fix, and
it is not a long-duration stability claim — a bounded test cannot show that the crash never returns.

## What not to do

- Do not debug the host app because the coalition names it. Read the thread name in the crash message
  (`on process_request_thread`) first; it names the culprit, and then check process ancestry to find
  which process that thread belongs to.
- Do not read "python3.14 quit unexpectedly" as a Python runtime defect. With no traceback and a
  `SIGTRAP` signature, the interpreter is the messenger.
- Do not treat this as an upstream pystray bug to be fixed by patching or upgrading in place. The
  verified remedy here is configuration; no upstream fix was verified.
- Do not conclude stability from a bounded run, or report it as a fix for the crash itself rather than
  an avoidance of the code path that crashes.
- Do not skip the restart. An un-restarted server will keep the old selection and look like the fix
  did not work.

## For agents working on this

On macOS, when a report says an app "quit unexpectedly" and the coalition names the host: ask which
thread trapped — the `on <thread_name>` suffix in an `EXC_BREAKPOINT` / `SIGTRAP` message is the
cheapest available discriminator — and establish process ancestry before touching the host binary. If
the trapping thread is a background request/worker thread that is calling into UI, the finding is a
main-thread violation inside a library, not a defect in the app that hosts it.
