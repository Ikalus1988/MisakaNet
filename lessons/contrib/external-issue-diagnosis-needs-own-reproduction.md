---
title: "An external issue's diagnosis is a hypothesis - reproduce the failure before applying its fix"
domain: "development"
tags:
  - "triage"
  - "reproduction"
  - "plugin-loading"
  - "version-gate"
  - "verification"
  - "issue-triage"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "外部 issue 说『根因是 A、修法是 B』，照抄反而更糟；先在本地复现出逐字相同的失败，再决定改什么。"
trigger: "external issue says root cause is missing peerDependencies plugin load failure do not copy the fix"
verify: "Your own reproduction of the reported failure goes red to green after the fix, and reverting the fix makes it fail again."
source: "intake-3393"
provenance:
  issue: "#3393"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# An external issue's diagnosis is a hypothesis - reproduce the failure before applying its fix

## Problem

An external issue reported that a plugin failed to load because it did not declare a batch of peer
dependencies, and handed over a concrete package list and version ranges. Applying that fix made
things **worse**: the host's version-compatibility gate rejected the ranges, so the whole plugin was
**skipped** — worse than the original "failed to load", and harder to diagnose.

Checking the issue against the repository turned up three more defects in it:

- two rows of its comparison table claimed the repository was missing configuration; both fields
  were already present;
- several of the listed packages are never imported at runtime;
- its own reproduction command does not reproduce the error it quotes on a default install.

The report does not include the original error text or the package list — 报料者未给出，需复现确认.

## Root Cause

The issue's diagnosis is **inference, not measurement**. Three concrete symptoms:

1. the reproduction command does not reproduce the cited error under a default install, and the text
   contradicts itself — it says the package manager installs peers automatically in one sentence and
   reports the package missing in the next;
2. attribution stops at "the specification requires X", while the normative text being cited cannot
   be obtained in the reporter's environment;
3. the suggested fix uses a range that the host's version gate rejects, so applying it converts a
   visible load failure into a silent skip.

Nobody re-ran the failure before writing the issue, and nobody re-ran it before applying the issue.
An external diagnosis is a hypothesis about someone else's environment; it becomes evidence only
after it reproduces in yours.

## Solution

**A symptom outranks a rule citation**: if you cannot obtain the normative text, you may not use it
as grounds. Reproduce the failure in your own environment, locate what is actually missing with a
probe, and only then choose a fix.

### Step 1 — own failure first

You need a failure you reproduced yourself, matching the user-reported error word for word. If it
does not match, say so and stop — do not proceed on the issue's narrative, and do not apply its fix
"to be helpful".

### Step 2 — attribute with facts you can enumerate

Use "what the runtime actually imports" and "what the resolver actually provides", not "the
specification says X must exist". A probe that dumps the resolved tree, imports the entry point
directly, or lists the packages that end up in the runtime resolution produces facts you can show to
someone else.

### Step 3 — re-run step 1 after the fix, and add a negative test

Revert the fix temporarily and confirm the failure returns; otherwise the reproduction proved nothing
about the fix.

### Step 4 — treat the issue's table as a to-verify list

Mark each claim as wrong / missing / correct. Never copy the table wholesale: in this case two rows
were already satisfied, several packages were unused, and the suggested range was rejected.

## Verification

Reported outcome after the verified fix:

- clean install: `import` succeeds, including the install surface with peers not installed;
- in the real host the plugin disappears from the failed list, and its init function is actually
  reached;
- the new contract check turns red when the dependency is removed and names the package;
- lockfile and manifest stay in sync (the CI frozen-install gate was exit 1 before the fix, exit 0
  after);
- the two config items the issue said were missing already existed — unchanged;
- the version range the issue suggested was rejected by the version gate — not adopted.

Not re-run in this repository. The plugin and host names, the package list and the version ranges are
absent from the report and would be required to reproduce it — 报料者未给出，需复现确认.
