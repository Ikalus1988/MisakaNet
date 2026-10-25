---
domain: "dsh"
title: "A catch-all reports every prompt-admission failure as session/agent-busy and hides the cause"
tags:
  - "error-taxonomy"
  - "catch-all"
  - "remote-error"
  - "diagnostics"
  - "session-agent-busy"
  - "logging"
  - "triage"
  - "dsh"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
source: "intake-3334"
summary_plain: "Every unexpected prompt failure is labelled session/agent-busy, so a permanent error is retried like a busy session."
trigger: "prompt rejected session/agent-busy RemoteError details.reason"
verify: "An admission throw returns code=session/prompt-admission-failed with the real cause text, while genuine subagent-ownership cases still return session/agent-busy."
provenance:
  issue: "#3334"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# A catch-all reports every prompt-admission failure as session/agent-busy and hides the cause

## Problem

Sending a prompt into an existing session returned:

```
code:    session/agent-busy
message: prompt rejected
```

…even when the actual failure had nothing to do with a busy session. The throw, verbatim:

```js
RemoteError("session/agent-busy", "prompt rejected", { reason: String(error) })
```

from `<APP_INSTALL>\…\@deepseek-ai\dsh-api-session-controller\lib\index.js:894` (catch at
`891-896`, inside `async prompt(request)` which begins at `index.js:850`). The same string is
duplicated at `…\lib\types\commands.js:347`.

The real cause survives only in `details.reason = String(error)` — semantically wrong, and often
invisible in the UI. Failures that reach this catch-all include attachment/image admission,
`resolvePromptFileReceipts`, the model image-capability check, `ctx.fileUploads.resolve`,
`attachments.admitPromptContent`, file-receipt resolution, agent followup delivery — and, in the
incident that produced this report, an upstream native-module load failure (`ERR_DLOPEN_FAILED` from
`sharp`/libvips) **wrapped into admission**.

Impact: every user-visible error for an existing session — chat send, steer, attachments, followup —
is mislabelled. Clients that treat `session/agent-busy` as transient (busy session, retry) either
retry a permanent failure forever or swallow it as expected noise.

## Root Cause

**A code that names a specific condition was used as the label for "anything unexpected in this
block".**

`session/agent-busy` has four other, legitimate uses in the same host, and every one of them carries
real routing semantics — "session is owned by subagent routing" / "subagent Sessions require their
durable parent address" (`index.js:139`, `index.js:1628`, `lib/types/agent.js:121`,
`lib/types/history.js:354`). So the code is meant for **ownership**, not for generic admission
failure. Reusing it as a catch-all silently converts a routing signal into a junk drawer, and every
downstream consumer that believed the routing semantics is now wrong.

The catch block assembles the failure class itself. The `try` block (`index.js:870-884`) is:

| step inside the guarded block |
|---|
| image capability check |
| `resolvePromptFileReceipts` |
| `ctx.fileUploads.resolve` |
| `attachments.admitPromptContent` |
| `agents.get(agent.id) !== agent` check |
| `fileUploads.bindPrompt` |
| `agent.steer` / `agent.followup` |

Seven unrelated causes, one label.

Two amplifiers:

1. **`String(error)` is the wrong renderer.** On an error without a message it yields only
   `error.name`, so even the hidden reason is useless. The host already exports a chain renderer,
   `errorChain(value)` (`@deepseek-ai/dsh-llm/lib/index.js:196-219`, exported at `:2390`); the
   catch-all simply does not use it.
2. **No log exists on that path**, which is why the incident could not be diagnosed on-site — the
   only artifact was a wrong code.

Adding a code is not free either: `RemoteError` comes from `@deepseek-ai/dsh-typert-protocol`
(imported at `index.js:7`) and is typed as
`ApiSessionAgentError = RemoteError<'session/not-found' | 'session/agent-busy' | 'session/writer-held' | 'gateway/internal'>`
at `lib/typert.host.js:1601`, so a new code has to be added to that union and its details shape to
`RemoteErrorDetailsMap` (`typert.host.js:2017`).

## Solution

### Step 1 — give the catch-all its own code and the full cause chain

Replace the catch-alls at `dsh-api-session-controller/lib/index.js:894` **and**
`lib/types/commands.js:347` (both sites — they are duplicates and must change together):

```js
throw new RemoteError("session/prompt-admission-failed", errorMessage(error), { reason: errorChain(error) });
```

### Step 2 — register the code in the typed surface

- add `"session/prompt-admission-failed"` to the `ApiSessionAgentError` union
  (`lib/typert.host.js:1601`);
- register its details shape in `RemoteErrorDetailsMap` (`typert.host.js:2017`).

### Step 3 — make the reason visible and logged

- surface `details.reason` in the client error view, so the cause is not dropped at the last hop;
- add a server-side `warn` log on that branch including `errorChain(error)` and `requestId` — the
  absence of that line is what made the incident undiagnosable.

### Step 4 — keep the real ownership cases on the ownership code

Only the catch-all changes. `session/agent-busy` keeps its four legitimate uses, and the verification
below is the guard that this refactor did not blur them.

## Verification

- Send a prompt that makes admission throw a non-`AttachmentError`: the client now receives
  `code=session/prompt-admission-failed` with the real cause text (e.g. the `ERR_DLOPEN_FAILED`
  string) instead of `code=session/agent-busy` / `"prompt rejected"`.
- Genuine ownership cases — a subagent-owned session, subagent delivery — **still** return
  `session/agent-busy`. This is the negative control: the new code must not swallow the routing
  signal it used to share.
- The new branch writes a `warn` log line containing the cause chain and the `requestId`.
- The report describes these three checks as the pass criteria; no post-fix run output was reported
  (**报料者未给出，需复现确认**).

## Notes

- The tell for this class of bug is a code whose name is a *condition* (`busy`, `locked`, `conflict`,
  `timeout`) appearing on paths where that condition cannot occur. A single grep for that identifier
  and a read of each call site is the cheapest audit; here it showed four legitimate ownership uses
  and one catch-all.
- A catch-all needs three things to be honest: its own code, its own log line, and the cause chain in
  the payload. Any two of the three still leave the next incident undiagnosable on-site.
- Wrapping is the other half of the problem: an upstream native-module failure was folded into prompt
  admission, so the layer that reported it could not know what it was reporting. If the cause chain is
  carried, the wrapper is harmless; if only `{message, code}` survives, the wrapper destroys the
  evidence.
- Same host, adjacent lesson: a `TRANSPORT` code used for a locally-decided native-module failure —
  identical mistake (a code naming a condition the failure does not have), one layer down.
- Evidence level is E1: reporter-described with verbatim error text and code locations, not
  reproduced in this repository.
