---
title: "DSH workspace-write denies writes in workspace subdirectories while the root is writable"
domain: "dsh"
tags:
  - "dsh"
  - "windows"
  - "sandbox"
  - "workspace-write"
  - "file-policy"
  - "flutter"
  - "build-hang"
  - "misdiagnosis"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "DSH 的 workspace-write 策略只放行工作区根目录，子目录被拒，导致构建命令无声挂起。"
trigger: "sandbox: file access denied under workspace-write mode workspace root writable subdirectory denied build hangs"
verify: "A probe file can be written into a workspace subdirectory such as build, and the same flutter build that hung finishes in about 60s"
source: "intake-3125"
provenance:
  issue: "#3125"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# DSH workspace-write denies writes in workspace subdirectories while the root is writable

## Problem

In a DSH (DeepSeek Harness) session on Windows under the `workspace-write` file policy,
writes to the workspace **root** succeeded, but writes into **any** subdirectory of the
workspace were refused — `build\`, `.dart_tool\`, `lib\`, and arbitrary new
subdirectories included. The two shapes the reporter saw were
`UnauthorizedAccessException` and the harness's own
`sandbox: file access denied under workspace-write mode`.

Because the denial arrived as a blocked write inside a build tool rather than as an
error on the command line, the observable symptom was not a permission error at all:

```text
flutter build windows --release
  -> starts, then produces no output at all, indefinitely
```

`flutter analyze` behaved the same way. That reads like a hung toolchain — a stuck
Flutter SDK, a plugin problem, or a version mismatch — and it was diagnosed that way
first.

The counter-evidence is cheap: a timing probe of the toolchain itself returns normally.

```text
flutter --version
  -> returns in 1.8 s
```

The toolchain was healthy; only commands that need to write inside the workspace
stalled.

## Root Cause

The session's file policy as it was applied allowed the workspace root path and denied
its children, so the first write a build makes into `build\` or `.dart_tool\` was
blocked. Flutter does not surface that block: it waits on the write and prints nothing,
so a policy denial is observed as an unbounded hang instead of an error message.

That mismatch between the failure (a policy denial) and the symptom (silence) is the
whole trap. "The tool hangs" invites investigating the tool; the actual question is
where the tool is allowed to write.

Why the policy's write set covered the root but not subdirectories was not established
by the reporter — 报料者未给出，需复现确认 (whether the rule enumerated the root path only,
or the child ACLs were not materialized, was not determined).

## Solution

### Step 1 — Separate "toolchain hung" from "writes denied"

Run the toolchain's own version command with timing. A sub-2-second `flutter --version`
says the SDK is fine and the stall is in the build's writes. Then probe the write set
directly:

- write one probe file in the workspace root,
- write one probe file in a subdirectory (for example `build\`).

Root writable + subdirectory denied is the signature of this failure.

### Step 2 — Choose a path deliberately

Two paths were tested by the reporter:

1. **Run the build outside the restricted session.** Execute the same
   `flutter build windows --release` from a terminal that is not bound by the session
   policy (for example the editor's integrated terminal). Both terminals invoked the
   same `<flutter>\bin\flutter.bat`, so this is the same toolchain — the only difference
   is the write policy.
2. **Widen the session policy** to `danger-full-access` for that session. Four writes
   (workspace root, `build\`, `lib\`, `.dart_tool\`) all passed, and
   `flutter build windows --release` completed in 60.5 s.

Prefer (1) when the only need is to build: it keeps the session confined. Widening the
policy is a real trade — `danger-full-access` removes the write boundary for everything
the session does, not just this build, so use it on a session that needs it rather than
as the standing default.

### Step 3 — Keep the probe in the diagnosis

Before concluding that a build tool is broken in a sandboxed session, write the two
probe files. It costs seconds and it separates "the tool is stuck" from "the tool is not
allowed to write where it must".

## Verification

- A probe file can be created in a workspace subdirectory (`build\`, `lib\`,
  `.dart_tool\`), not only in the workspace root.
- The same `flutter build windows --release` that previously produced no output
  completes; measured at 60.5 s under `danger-full-access`.
- `flutter --version` still returns in about 1.8 s in the failing session, which is the
  negative control: it confirms the SDK was never the problem.

The reporter's original verification criterion was only "the build succeeds" (编译成功);
it does not distinguish this failure from a genuine toolchain hang on its own, so use
the subdirectory write probe above as the pass/fail signal — 报料者未给出更细的判据，需复现确认.

## Notes

- The same policy string `sandbox: file access denied` can mean opposite things
  depending on direction: writes **outside** the workspace are expected to be denied
  (see `lessons/contrib/workspace-write-policy-denial-escalate-once-not-retry-apis.md`),
  while writes **inside** the workspace are supposed to succeed. A subdirectory denial
  is the abnormal case, and retrying through another API will not help because the
  denial sits below the API surface.
- Windows, Flutter 3.x, DSH session with the `workspace-write` policy. The DSH version,
  the exact policy document and the Flutter version were not given by the reporter —
  报料者未给出，需复现确认.
- Related: `lessons/contrib/node-child-process-eperm-windows-sandbox-redirect-to-file.md`
  (a different Windows sandbox refusal that also masquerades as a tool failure) and
  `lessons/contrib/dsh-windows-shell-tools-blocked-two-stages.md`.
