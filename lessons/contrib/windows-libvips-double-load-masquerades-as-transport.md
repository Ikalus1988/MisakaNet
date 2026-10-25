---
domain: "windows"
title: "A Windows libvips DLL loaded twice poisons the bundled sharp and surfaces as TRANSPORT"
tags:
  - "sharp"
  - "libvips"
  - "native-module"
  - "dll-single-load"
  - "err-dlopen-failed"
  - "windows"
  - "restart-required"
  - "dsh"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
source: "intake-3335"
summary_plain: "An older libvips DLL loaded first blocked the bundled sharp, so every turn failed as a transport error until restart."
trigger: "DeepSeek Messages transport failed TRANSPORT in ~13 ms, socketTrace empty, ERR_DLOPEN_FAILED sharp libvips"
verify: "After aligning the profile sharp copies and restarting the host, the sharp probe reports 0.35.5 / vips 8.18.7 and the first turn succeeds with a non-empty socketTrace."
provenance:
  issue: "#3335"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# A Windows libvips DLL loaded twice poisons the bundled sharp and surfaces as TRANSPORT

## Problem

On Windows, a desktop host (Electron + bundled `sharp`) had every turn of an affected session fail
**locally**, within about 13 ms, with:

```
DeepSeek Messages transport failed        code: TRANSPORT
```

The request never left the machine. The error carried no cause, no target URL, no host, no status and
no request id, so it read exactly like a network or proxy fault — which is where diagnosis went first.

Reproduction, as reported:

1. open an existing session and chat normally, to confirm the link works;
2. trigger a checkpoint/recovery-resume path in the host **without restarting the app** (the session
   file has been rewritten and in-process state must be reloaded);
3. send any prompt, with or without an image;
4. every turn fails immediately with `TRANSPORT` and produces no outbound request;
5. quit and restart the app — recovery is immediate and the first post-restart turn succeeds.

The hidden cause, only visible after a forensics plugin was installed, was a native-module load
failure. The incident record (verbatim fields; paths redacted to placeholders, `…` marks the cut):

```json
{"ts":"2026-10-16T05:53:22.956Z","kind":"incident","code":"TRANSPORT","errorName":"LlmError",
 "provider":"deepseek-official","model":"deepseek-flash","adapter":"DeepSeekAdapter",
 "chain":["LlmError[TRANSPORT]: DeepSeek Messages transport failed @ DeepSeekAdapter.generate (… "
          "Could not load the \"sharp\" module using the win32-x64 runtime\n"
          "ERR_DLOPEN_FAILED: The specified procedure could not be found.\r\n"
          "\\?\\<APP_INSTALL>\\resources\\app.asar.unpacked\\dsh\\node_modules\\@img\\sharp-win32-x64\\lib\\sharp-win32-x64-0.35.5.node"],
 "socketTrace":[]}
```

Throw site, verbatim:

```js
throw new LlmError("DeepSeek Messages transport failed", "TRANSPORT", { cause: error });
```

at `@deepseek-ai/dsh-llm-deepseek/lib/index.js:2132` (catch at `2128`; guards at `2129` TIMEOUT,
`2130` ABORTED, `2131` rethrow `LlmError`).

The cause *is* attached to the `Error` object, but never survives to the user: the frozen serializable
failure snapshot carries only `{message, code}` (plus optional `status` / `providerRetryAfterMs` /
`requestId` / `offloadImages`), and `normalizeLlmFailure` further reduces it to
`Object.freeze({message, code})`. Relevant locations named by the reporter:
`@deepseek-ai/dsh-llm/lib/index.js:1629-1638` (snapshot), `:402-410` (`normalizeLlmFailure`),
`:2376-2387` (`adapterFailureChunk`), `:196-219` (`errorChain()`, exported at `:2390` — it can render
the chain, but it is unused for the failure payload).

## Root Cause

**On Windows, `libvips` is a DLL whose module base name — `libvips-42.dll` — can only be loaded once
per process.** Not once per version: once, period.

- A plugin's dependency tree contained an **older nested `sharp`** (`0.34.5`, libvips `8.17.3`) via
  `@huggingface/transformers` (used by a local-embeddings plugin, `@memtensor/memos-local-plugin`).
- That copy loads **first**, at process start.
- The host's bundled **newer** `sharp` (`0.35.5`, libvips `8.18.7`) can then never load. Any request
  that touches `sharp` dies with `ERR_DLOPEN_FAILED: The specified procedure could not be found`.

The physical evidence fits the mechanism exactly: `libvips-42.dll` is the same file everywhere
(19018240 B), while the C++ payload differs by version — `libvips-cpp-8.17.3.dll` (327168 B) survives
only inside backup copies of `@img\sharp-win32-x64`, and the live copies carry
`libvips-cpp-8.18.7.dll` (333312 B). Same loader-visible module name, incompatible contents: the
second one cannot be brought in.

Two consequences that make this expensive to diagnose:

1. **The failure is per-process, not per-session.** It is established when the process starts, so it
   outlives retries, new sessions and session resume; only an app restart clears it. Re-running an
   alignment script at 13:33 did nothing for the already-running process — a loaded DLL cannot be
   swapped — and only the 13:54 restart recovered.
2. **`TRANSPORT` is decided locally but presents as a network fault.** A poisoned process state was
   reported as a transport failure, so the user retries a permanent condition and investigates the
   network, the proxy and the provider instead of the native module.

Also worth recording: the trigger was an ordinary install. Any plugin whose tree contains
`@huggingface/transformers` with an older nested `sharp` is enough — the user did nothing wrong. And
`pnpm-lock.yaml` still references **both** `@img/sharp-darwin-arm64@0.34.5` and `@0.35.5`, so a
re-install can restore the clashing copy even after it has been aligned.

## Solution

### Step 1 — recover the session now: align, then restart

Align the profile's `sharp` / libvips copies to the bundled build (`0.35.5` / `8.18.7`) and **restart
the host**, because a DLL already loaded in the process cannot be replaced. On the reporting machine a
re-runnable PowerShell script did the alignment (re-run it after any `pnpm install`, since a lockfile
that still mentions the older build can restore it).

### Step 2 — prove the clash and the fix with load-order probes

Two probes decide pass/fail without needing the failure to happen again:

- an **order probe** that loads the plugin's nested `sharp` first and then the bundled one (order A),
  then the reverse (order B), printing `PASS`/`FAIL` for each;
- an **alignment probe** that prints
  `RESULT: CLASH STILL PRESENT — first-loaded sharp poisons DSH bundled sharp` while an old copy is
  present.

After alignment both orders report `PASS`.

### Step 3 — durable fixes, in the host (not available to the user)

The reporter lists them; they are a design contract worth copying into any host that bundles a native
module:

1. Carry `cause` — rendered with the already-existing `errorChain()` — plus the transport target
   URL/host, the failing phase and elapsed ms in the failure snapshot
   (`dsh-llm/lib/index.js:1631-1638`), and stop dropping it in `normalizeLlmFailure` (`:402-410`).
2. Emit a **distinct code/message** when the failure happened before any socket work (empty
   `socketTrace`, ~13 ms), e.g. "native module load failed, restart required", instead of implying a
   network fault.
3. Run a **startup self-check** that loads the bundled `sharp` and reports the libvips clash with a
   concrete remedy.
4. **Warn at install time** when a profile copy of a native module conflicts with the bundled one,
   and/or stop plugin-side `@huggingface/transformers` from pre-loading a different libvips on
   Windows.
5. **Persist the cause chain (with stack) to the session log by default**, so no after-the-fact
   forensics plugin is required to see it.

## Verification

- Alignment + restart, then the env-check reports `SHARP_OK` with
  `{"ok":true,"path":"<APP_INSTALL>\\resources\\app.asar\\dsh\\node_modules\\sharp","sharp":"0.35.5","vips":"8.18.7"}`
  (observed `2026-10-16T05:54:08.437Z`), and the **first turn succeeds** (observed
  `2026-10-16T05:54:16Z`).
- **No** `kind:"incident"` `TRANSPORT` records appear in the incident log after the restart. The
  pre-fix file held 22 records, 13 ms apart, **all** with `"socketTrace":[]`; the rotated current file
  held 29 records with 0 incidents — i.e. `socketTrace` empty is the marker of "never left the
  machine".
- Resolution probe through the host's own runtime (`ELECTRON_RUN_AS_NODE=1 "<APP_INSTALL>\\<host>.exe"`,
  `createRequire` from the profile's `package.json`) prints:
  `OK sharp version=0.35.5 vips=8.18.7`, `OK @huggingface/transformers version=4.2.0`, and
  `memos-resolved sharp: 0.35.5 vips=8.18.7`.
- Load-order probe: both orders `PASS` after alignment; the align probe stops printing
  `CLASH STILL PRESENT`.
- The names and command lines of the forensics selftest / env-check were **not given in the report
  (报料者未给出，需复现确认)**; the pass criteria above are the reported observations, not a
  reproduction in this repository.

## Notes

- **Restart is the tell.** If turning the process off and on again fixes a "network" error, the error
  was never about the network. A failure that clears with a restart is a state problem in the process,
  and the right next question is "which module/table/handle was loaded once and never reloaded".
- **Never nest two versions of a library whose native payload has a fixed module name.** On Windows
  the loader keys the DLL by base name; "two versions side by side" is not available for libvips, so
  dependency duplication in a plugin tree silently breaks the host's own copy.
- Generic `TRANSPORT`/`NETWORK` codes are the cheapest possible fix and the most expensive possible
  diagnosis: they are correct for "we do not know" and wrong for "we decided locally".
- Related direction (same host, different symptom): an admission catch-all that reports every
  unexpected prompt failure as `session/agent-busy` — the same "the code names a condition the failure
  does not have" mistake, one layer up.
- Evidence level is E1: reporter-described with verbatim records, file sizes and timestamps, not
  reproduced in this repository.
