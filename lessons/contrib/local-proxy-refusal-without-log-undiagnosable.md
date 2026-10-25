---
domain: "dsh"
title: "A local proxy that refuses without a reason or a log makes the innocent component the suspect"
tags:
  - "local-proxy"
  - "diagnostics"
  - "observability"
  - "missing-log"
  - "misdiagnosis"
  - "session-ownership"
  - "error-message"
  - "dsh"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
source: "intake-3336"
summary_plain: "The local proxy refused prompts with a generic error and wrote no log at all, so the innocent host component was blamed."
trigger: "bili/bili-proxy generic refusal, no bili.log, session ownership stale or unknown"
verify: "A stale/unknown-ownership request through the bili lane returns the deciding component, reasonCode, session id and a remedy, and writes a log record at the documented proxy log path."
provenance:
  issue: "#3336"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# A local proxy that refuses without a reason or a log makes the innocent component the suspect

## Problem

A local proxy lane (a third-party local proxy, `billion-context` 0.1.197, `bin` entries `bili` and
`bili-proxy` → `./dist/index.js`, repo `https://github.com/ranxianglei/billion-context`) refuses
requests whose **session-ownership state is stale or unknown** — and does it with an error that
names neither the deciding component nor the staleness/unknown criterion. It also leaves **no local
log** for that path.

Reproduction, as reported:

1. run the local proxy lane;
2. let a session's ownership state go stale or unknown (long idle, host restart/recovery,
   checkpoint-resume);
3. send a prompt through the lane;
4. observe a generic refusal with no identifying fields, and no proxy-side log record.

The observable end state on the machine was the absence of a file:
`<USER_HOME>\.dsh\bili.log absent; <USER_HOME>\.bili.log absent`.

That absence is what turned a bug into a **two-hour misdiagnosis**: the proxy was blamed, the host's
image-admission logic was patched and later reverted, while the real fault was host-local in-process
state. With no proxy-side record, the caller cannot tell "proxy refusal" from "host-local failure" —
so the blame goes to the last component in the chain rather than the correct one.

## Root Cause

Three facts combine into an undiagnosable refusal:

1. **The refusal happens before the transport hook**, so the one logging side effect that would
   normally fire never runs. The decision is invisible by construction, not by misconfiguration.
2. **The error text carries none of the discriminator fields** — not the judging component/stage,
   not the criterion (which table/state entry, expected vs actual), not the session id, not an
   actionable remedy (rebuild ownership / restart / rebind).
3. **No log path is documented**, so "no log exists" is not distinguishable from "the log path moved"
   or "logging is off". A missing log is indistinguishable from a healthy quiet run.

A refusal is only actionable if the caller can tell *who* decided and *against what*. The reporter's
own positive counter-example proves the proxy *can* do this — its compaction refusal explains itself
and gives the opt-in, verbatim:

```json
{"type":"error","error":{"type":"invalid_request_error","message":"dsh native compaction call refused by billion-context: bili owns compression on this lane (#1729, cf. #1772/#1206). A landed dsh compaction checkpoint durably shadows the raw conversation history, which destroys the proxy's compression substrate. To run dsh native compaction on this lane anyway, opt in explicitly: \"allowDshCompaction\": true in the bili config or env BILI_ALLOW_DSH_COMPACTION=1"}}
```

That surfaced as `LlmError[INVALID_REQUEST]` — a component, a reason, a lane, and a remedy. The
session-ownership refusal path should follow the same style; it currently produces none of it.

## Solution

The fix belongs in the third-party proxy (`billion-context`), not in the host that calls it:

1. **Structured refusal fields** — `component`, `reasonCode`, `sessionId`, expected vs actual
   ownership state, and a `remedy` — reusing the compaction-refusal style shown above.
2. **Rebuild, or explicitly prompt to rebuild**, stale/unknown session ownership instead of refusing
   outright. A refusal that the caller can repair automatically should not be terminal.
3. **Always write a local log for refusals**, including refusals that happen before the transport
   hook, containing request id, session id and the criterion snapshot.
4. **Ship and document a default log path**, so that "no log exists" is itself a detectable
   misconfiguration rather than a silent default.

Host-side mitigations that would have shortened this incident:

- When a turn fails with an empty `socketTrace` and **no proxy record**, mark the failure as
  host-local in the error text, so nobody chases the proxy.
- Surface the proxy's structured refusal reason in the `LlmError` payload instead of dropping it.

Diagnostic procedure that produced the negative evidence above (reusable for any "is the proxy even
seeing my request?" question):

1. Enumerate the profile directory recursively for `bili*`. It returned only launcher stubs
   (`.bin\bili`, `.CMD`, `.ps1`, 1189 B) and the plugin package — **no** `bili*.log` and no
   `bili*.json` state file anywhere under `<USER_HOME>\.dsh` or the install root.
2. Read the proxy's identity from
   `<USER_HOME>\.dsh\profiles\desktop\node_modules\billion-context\package.json`
   (`"name":"billion-context"`, `"version":"0.1.197"`, `"bin":{"bili":"./dist/index.js","bili-proxy":"./dist/index.js"}`),
   so the report names a version rather than "the proxy".
3. Split the failing turns by *where they were recorded*: the failing turns at
   `2026-10-16T05:53:15Z`–`05:53:30Z` carry a host-local `ERR_DLOPEN_FAILED` with `socketTrace: []`
   and produce **no proxy record at all** — i.e. the proxy never saw them. In this incident the proxy
   was innocent; the complaint is that a genuine proxy-side refusal would have been equally
   invisible.

## Verification

- Trigger a stale/unknown-ownership request through the bili lane and confirm (a) the returned error
  contains the judging component, `reasonCode`, session id and a concrete remedy, and (b) a log
  record appears at the documented proxy log path for that refusal.
- **Negative control**: a healthy lane produces no such refusal, and the refusal log stays empty for
  healthy turns.
- **Pre-fix baseline** (observed): neither a structured error nor any log file —
  `<USER_HOME>\.dsh\bili.log` absent.
- The post-fix state was **not observed by the reporter (报料者未给出，需复现确认)**: the fix belongs
  upstream in `billion-context`, so the two bullets above are pass criteria to reproduce, not a
  reported result.

## Notes

- This is a lesson about **diagnosability**, not about ownership logic. A correct refusal that cannot
  be attributed costs more than a wrong answer that can: the misattribution here reverted a real fix.
- The general criterion: for every pre-transport rejection path in a middleware/proxy, ask "if this
  fires at 3 a.m., which file does the operator open?" If the answer is "none", the path is not done.
- The reporter filed this against the host because the missing diagnostics were load-bearing in the
  misdiagnosis, while explicitly attributing the code fix to the third-party repository.
- Evidence level is E1: reporter-described, with verbatim error text and a documented directory
  enumeration, but not reproduced in this repository.
