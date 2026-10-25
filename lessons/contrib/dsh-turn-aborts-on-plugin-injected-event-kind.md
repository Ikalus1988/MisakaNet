---
domain: "dsh"
title: "DSH aborts every turn milliseconds after start when a plugin injects an unnamespaced event kind"
tags:
  - "dsh"
  - "plugin"
  - "session-log"
  - "interrupted"
  - "turn-lifecycle"
  - "zstd"
  - "memos-cloud"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
source: "intake-3524"
summary_plain: "DSH 桌面版里每条消息刚发出就显示失败：memos 记忆插件注入消息时用了不带插件名的 kind，会话直接判定 interrupted。"
trigger: "turn/start then turn/end reason kind interrupted 2ms apart, no step/start, no assistant/message"
verify: "After the patch, sending one message logs turn/start -> step/start (step 1) -> assistant/message, and the injected message source reads kind plugin:memos-cloud."
provenance:
  issue: "#3524"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# DSH aborts every turn milliseconds after start when a plugin injects an unnamespaced event kind

## Problem

DeepSeek Harness (DSH) desktop `0.2.1-rc.2`. Sending any message — text or image, in any session —
failed instantly in the client, with no reply. Three consecutive sends, and a resend, all failed the
same way. Restarting DSH restored normal behaviour, until the next time.

The session log (`sessions/<ws>/session-*/session.v4.jsonl.zstd`) showed, for every failed message:

```json
{"type":"turn/start",...,"data":{"turn":52}}
{"type":"turn/end",...,"data":{"turn":52,"reason":{"kind":"interrupted"}}}
```

Those two records are **2 ms apart**. There is no `step/start` between them and no
`assistant/message` after them — the turn was opened and closed before any work began.

## Root Cause

A memory plugin (`@memtensor/memos-cloud-dsh-plugin`) injects context into the turn — a recall
message. The injected message's source carried the bare kind:

```json
{"kind":"plugin", ...}
```

**`kind` is the field the session routes on.** A bare `plugin` does not name *which* plugin produced
the event, so the turn runner cannot attribute the injection to a source it can accept. The turn is
opened and immediately aborted with `reason: {"kind":"interrupted"}` — the same terminal state used
for a user-cancelled turn, which is why the client renders it as a plain failure with no diagnostic.

After the reporter's patch, the same injected message carries:

```json
{"kind":"plugin:memos-cloud","plugin":"memos-cloud","form":"recall"}
```

The namespaced kind is what lets the turn accept the injection and proceed to `step/start`.

**Why restarting appears to fix it:** a restart converges the dangling turn into `interrupted` and
starts a clean session state. The plugin is still installed, so the defect returns; the restart only
cleared the wedge, it did not remove the cause.

### Two misleading leads during diagnosis

**1. Reading the session log naively shows almost nothing.** `session.v4.jsonl.zstd` is
**multi-frame zstd**, not a single stream. A one-shot decompress returns only the first frame — about
190 bytes — which looks like truncation or corruption and hides the `turn/end` record. Each frame has
to be decompressed and the results concatenated:

```js
// node, zlib has no zstd; use the runtime's zstdDecompressSync frame by frame
const frames = splitZstdFrames(buf);
const text = frames.map((f) => zstdDecompressSync(f).toString("utf8")).join("");
```

**2. `{"kind":"plugin"}` lines already in older session files are legacy, not the fault.** The old
`v3` session file held about 30 of them. They are historical records written by an earlier format,
and were present in a session that worked. Do not treat existing `kind: "plugin"` entries as the
evidence — reproduce with a **fresh** failed turn, then look for that turn's own injection record.

## Solution

### Fix (the reporter's local patch)

Edit the installed plugin's dist file and namespace the kind:

```powershell
$f = "node_modules/@memtensor/memos-cloud-dsh-plugin/lib/index.js"
(Get-Content $f -Raw) -replace 'kind:\s*"plugin",', 'kind: "plugin:memos-cloud",' |
  Set-Content $f -Encoding utf8NoBOM
```

On the reporter's machine the line was around 898 of that file. Then restart DSH and send a message.

`utf8NoBOM` matters on Windows PowerShell 5.1: the default `Set-Content` encoding writes a BOM, and a
BOM in front of the first line breaks a JS module's loader.

### Workaround when a patch is not possible

Disable the `memos-cloud` plugin and restart DSH. The turns will run; the memory injection is simply
absent. This isolates the cause in one step: with the plugin disabled the interruptions stop, which
is the confirmation that the injected event — not the client or the transport — is aborting the turn.

### Also align the CLI and desktop versions

The reporter's profile had the CLI at `0.2.0-rc.2` and the desktop app at `0.2.1-rc.2`. Upgrade the
CLI to the same version so both write the same session format; a mixed-version profile makes
"which writer produced this record" ambiguous during exactly this kind of diagnosis.

## Verification

Send one message after the patch and read the log. It must show the full turn shape:

```
turn/start            data: {turn: N}
step/start            data: {turn: N, step: 1}
assistant/message
```

and must **not** contain a `turn/end` with `reason: {"kind":"interrupted"}` immediately after
`turn/start`. The injected message's source should read
`{"kind":"plugin:memos-cloud","plugin":"memos-cloud","form":"recall"}`.

The pass/fail criterion is the 2 ms gap: before the fix, `turn/start` → `turn/end{interrupted}` with
no `step/start` in between; after it, a `step/start` line exists.

## Notes

- Evidence level E1: one operator's report, with the log records quoted above; not reproduced in this
  repository. The mechanism (a bare `kind` preventing attribution) is what the reporter's fix
  implies, not something this repository verified in DSH source.
- **The patch lives in `node_modules`.** Any plugin reinstall, upgrade, or profile rebuild overwrites
  it. Re-apply and re-check after each upgrade, or push the fix upstream; a patched dist file is a
  temporary hold, not a durable fix.
- The same symptom shape (`turn/start` immediately followed by `turn/end{interrupted}`) is the first
  thing to grep for in a session log — it separates "the turn was aborted at the start" from "the
  model produced nothing", which look identical in the client.
- Decompress tool: whatever you use must handle multiple zstd frames in one file. A single-shot
  decode that returns a few hundred bytes is a framing problem, not a corrupt session.
