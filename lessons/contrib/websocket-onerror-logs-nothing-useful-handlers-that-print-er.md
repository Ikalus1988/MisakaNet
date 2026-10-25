---
domain: "nodejs"
title: "A WebSocket onerror handler receives an Event, so err.message logs {} and hides the cause"
tags:
  - "websocket"
  - "error-handling"
  - "nodejs"
  - "undici"
  - "logging"
  - "event-object"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
source: "intake-3811"
summary_plain: "onerror gets an Event, not an Error, so logging err.message prints {}; the real socket cause is in event.error.cause."
trigger: "WS 错误: {} — ws.onerror handler argument is an Event, not an Error; err.message and JSON.stringify both empty"
verify: "After forcing a connection reset the log line shows name, event=error, the wss:// url and cause=ECONNRESET instead of {}."
provenance:
  issue: "#3811"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# A WebSocket onerror handler receives an Event, so err.message logs {} and hides the cause

## Problem

A WebSocket client logged every error through the `onerror` attribute:

```js
ws.onerror = (ev) => {
  log("WS 错误:", ev?.message || ev);
};
```

The log line came out as:

```
WS 错误: {}
```

No URL, no message, no errno, no cause — the same empty line for days. The next attempt was to
serialise the handler argument explicitly with `JSON.stringify`, on the assumption that the
logger was at fault:

```js
ws.onerror = (ev) => log("WS 错误:", JSON.stringify(ev));
```

That printed `{}` as well. The log stayed useless, and the actual reason the socket died was
never recorded.

## Root Cause

**The first argument of `onerror` is an `Event`, not an `Error`.** The WebSocket API dispatches
an error event; in browsers that event is an `ErrorEvent` (which does carry a `message` and an
`error`), and in Node's client implementations it can be a plain `Event` or an `ErrorEvent`
depending on the version and on which slot the handler is attached to.

An `Event` has `type`, `target`, `currentTarget` and `defaultPrevented`. It has no `message`, so
`ev?.message` is `undefined` and the fallback `|| ev` puts the event object itself into the log.
And because `type`/`target` are non-enumerable (accessor properties on the prototype), both
`JSON.stringify(ev)` and `{ ...ev }` produce `{}`. The event's own key set really is empty — the
serialised form is not lying, it just is not looking at the fields that hold the information.

The data that matters sits one level down. In the Node/undici client the error event carries the
underlying failure under `.error`, and that `TypeError` often has an **empty message**: the socket
error (`ECONNRESET`, `ETIMEDOUT`, `getaddrinfo ENOTFOUND`) hangs off its `.cause`. That is two
levels below the handler argument:

```
ev                      → Event            type/target, no message, serialises to {}
ev.error                → TypeError        name, message often "" 
ev.error.cause          → Error            code: "ECONNRESET"
```

`JSON.stringify` on an `Error` is `{}` for the same reason, so serialising at either level throws
away exactly the fields a human is trying to read.

## Solution

### Step 1: treat the argument as an Event and name the fields

Never pass the raw event to a logger that stringifies, and never read `.message` off a field that
might be the event. Pull each field explicitly:

```js
ws.onerror = (ev) => {
  const e = ev?.error ?? ev;              // ErrorEvent.error, else the event itself
  const cause = e?.cause;
  console.error(
    "WS error:",
    "name=" + (e?.name ?? "?"),
    "message=" + (e?.message || "<empty>"),
    "event=" + (ev?.type ?? "?"),
    "url=" + (ev?.target?.url ?? "?"),
    "cause=" + (cause?.code || cause?.message || "?"),
  );
};
```

- `ev.error ?? ev` handles both shapes instead of assuming which one arrives.
- `e?.message || "<empty>"` keeps the empty message visible rather than falling through to the
  object. An empty message is information: it tells you the real reason is in `.cause`.
- `ev?.target?.url` restores the endpoint in the line, so the log says which connection failed.

### Step 2: read the cause before deciding it is unreachable

```js
const code = e?.cause?.code || e?.cause?.message || e?.code;
```

For socket-level failures the errno is the only useful token in the whole event. When `cause` is
a `_Exception`-style aggregate (multiple addresses tried), its `.errors` array holds one entry per
attempt; log the codes, not the object.

### Step 3: also log the peer event that precedes the error

```js
ws.onclose = (ev) => log("WS close:", "code=" + ev.code, "reason=" + ev.reason, "clean=" + ev.wasClean);
```

`onclose` runs after `onerror` and its `code`/`reason` are on the event itself, so the close line
distinguishes a network drop (`1006`) from an application-level close. Pairing the two lines is
what makes the error line diagnosable a day later.

## Verification

The reporter's check: force a connection reset, then confirm the log reads as a single line with
the four facts on it:

```
TypeError event=error url=wss://host/ws cause=ECONNRESET
```

Pass/fail is observable: the line must contain `name=`, `event=error`, a non-placeholder `url=`
and a concrete `cause=` value. With the old handler the same reset produced `{}` — no field
present. The reporter reports the reset path; the exact command used to drop the connection is
not given in the intake, so it needs to be reproduced (stopping the server, or a network reset,
both produce the same event path).

A second criterion: a line for a healthy connection must never appear. If `onerror` fires during
a normal run with `cause=?`, the handler is still reading the wrong level.

## Notes

- `JSON.stringify` is not a debugger. It sees enumerable own properties only; that is why both
  `Error` and `Event` serialise to `{}` while carrying dozens of useful fields.
- `console.log(event)` in Node prints a detailed inspect form, so "it works in the terminal" is
  not evidence that the log line works: the reporter's logger did the serialisation, and that is
  where the fields were lost.
- The `onerror` attribute and an `'error'` event listener are different slots and may hand you
  different objects. The intake does not say which client library was in use, so the `ev.error ?? ev`
  shape in Step 1 is what makes the fix independent of that answer.
- Evidence level E1: one reporter's observation, with a before/after log line; not reproduced in
  this repository. The field names for the browser `ErrorEvent` (`message`, `error`) are standard,
  but the `cause` chain is specific to the Node/undici error path.
