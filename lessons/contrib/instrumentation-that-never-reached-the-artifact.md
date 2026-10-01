---
domain: "development"
title: "Instrumentation that never reached the artifact: a silent probe is not evidence"
tags:
  - "instrumentation"
  - "root-cause"
  - "verification"
  - "build-artifacts"
  - "silent-failure"
  - "debugging"
status: "published"
evidence_level: "E1"
created: "2026-10-01"
updated: "2026-10-01"
source: "intake #2566 — remote agent; measured 2026-10-01, corroborated by the maintainer's receipt"
summary_plain: "A probe proves nothing if the runtime loads a prebuilt bundle: check the artifact changed before reading its silence."
trigger: "probe produced no output / web boot: 1 entry did not activate / source edited but the served bundle is unchanged / stale merged batch"
verify: "After a probe edit, the served artifact's byte size or hash must change, and a control probe on a path that always runs must print. If either fails, the probe was never in the running code."
provenance:
  issue: "#2566"
  source: "remote-agent MCP intake"
  related: "#2575"
evidence_refs:
  - "issue:#2566"
---

# Instrumentation that never reached the artifact: a silent probe is not evidence

## Problem

A web plugin failed to boot, and the host said so in one line:

```text
web boot: 1 entry did not activate / misakanet: failed
```

To find out how far the plugin got, the investigator instrumented the plugin's **source** with three
layers of probes — one at module scope, one around the factory, one inside the apply path. Nothing
printed. From that silence they concluded the file had been evaluated but its factory never ran, leaving
the activation fiber in FAILED.

**That conclusion was wrong.** The probes were never in the code the browser executed, so their absence
said nothing about the plugin. A wrong-but-confident root cause is worse than no root cause: it sends the
next hour of work into the wrong half of the system, and it arrives with the authority of a measurement.

## Root Cause

The host serves the browser-side plugins as **one prebuilt merged combo**, not as per-plugin source files.
At the time, that combo covered 58 plugins and measured **10,468,804 bytes**. Editing a plugin's source
file does not change the combo; the artifact must be rebuilt and the host restarted (or the plugin
toggled) before an edit is what a page actually loads.

The tell was available before any conclusion was drawn: the merged artifact's byte size **did not
change** after an edit that added probe statements. A probe adds bytes. If the artifact's size is
identical after the edit, the probe is not in the artifact — and the artifact is what runs. Silence from
a probe that never shipped is evidence about the build pipeline, not about the plugin.

The trap runs in both directions. After the actual defect (a child slot registered before its parent
declared it, fixed in #2575) was addressed, the per-row bundle URL served the new file — **48,267 bytes**,
revision recomputed — while the page kept loading the stale batch. So the artifact under test and the
artifact the runtime loaded were different files both times, in the two opposite ways they can differ.

## Solution

Treat "the probe reached the artifact" as a precondition of any probe-based conclusion, and check it
before interpreting any output.

1. **Diff the artifact across the edit.** Record the byte size (or a content hash) of the artifact the
   runtime actually loads, make the probe edit, then record it again. An unchanged artifact means the
   probe is not in the running code: fix the pipeline before reading silence as a signal.
2. **Prefer the path that shows your edit.** During development, load the plugin through its per-row
   artifact URL instead of the merged batch. A per-row artifact (new size, recomputed revision) turns
   "did my code ship?" into a direct observation rather than an inference.
3. **Keep a control probe on a path that must run.** Put one probe where execution is certain — module
   top level, or a function known to be called. If the control is silent too, the probe mechanism is
   broken; that is a different finding from "the code did not run", and it is the finding this session
   actually had.
4. **Name the artifact in the probe result.** Log the artifact identity (size, hash, or revision)
   alongside the probe's output, so a probe that does fire can be attributed to the bytes that produced
   it.

```console
# The cheap check, before interpreting anything:
$ stat -c%s dist/plugin-batch.js
10468804
# ...add probe statements to the plugin source, rebuild as the host does...
$ stat -c%s dist/plugin-batch.js
10468804        # unchanged: the edit is not in this artifact, so the probe cannot run
```

## Verification

A probe-based conclusion is admissible only when **both** hold:

- the artifact the runtime loads changed after the probe edit — its byte size or hash differs from the
  pre-edit value; and
- a control probe on a path that always executes produced output.

Falsify it by reverting the probe edit alone: if the apparent signal survives the removal, or the control
stays silent, the observation was never about the code under investigation. Applied to this case the
check fails immediately — the merged artifact's size is identical before and after the edit, which is
exactly why the original conclusion was wrong. The same check passing on the other side is the
confirmation: after the fix, the per-row bundle URL served a new file (48,267 bytes, revision
recomputed), so an edit to the artifact under test was directly observable there.

## Notes

- The real defect behind this failure was a child slot registered before its parent declared it, fixed
  in #2575. It is named here only to keep the record straight: this lesson is about instrumentation that
  never reached the artifact, not about slot declaration order.
- Both measurements — the 10,468,804-byte merged batch and the 48,267-byte per-row bundle with a
  recomputed revision — were taken on 2026-10-01 and corroborated by the host maintainer, who hit the
  same trap from the opposite direction while verifying the fix.
- General shape for this corpus: whenever a build step sits between your edit and the runtime, every
  conclusion drawn from runtime silence has to include a check that the build carried the edit. A check
  that reads the source instead of the served bytes cannot distinguish "my code did not run" from "my
  code is not here".
