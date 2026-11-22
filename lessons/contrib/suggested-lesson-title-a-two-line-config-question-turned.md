---
title: "Suggested lesson title: \"A two-line config question turned into asar archaeology"
domain: "dsh"
tags:
  - "suggested"
  - "lesson"
  - "title"
status: "published"
evidence_level: "E1"
created: "2026-11-22"
updated: "2026-11-22"
source: "intake-4210"
summary_plain: "Suggested lesson title: \"A two-line config question turned into asar archaeology: answer from the profile config…"
trigger: "Suggested lesson title: \"A two-line config question turned into asar archaeology. answer from the profile config before unpacking the bundle\"."
verify: "Re-run the question: the profile patch (agent-default-model.reasoningEffort: low; ui-settings-account.developerTools: false) explains both facts — effort was never high (the UI shows the model…"
provenance:
  issue: "#4210"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

Suggested lesson title: "A two-line config question turned into asar archaeology: answer from the profile config before unpacking the bundle". Two incidents in one day, same pattern. (1) User asked why new DSH sessions appear to default reasoning effort to "high" and why the agent-preset picker shows only two presets. Instead of reading the profile config, the agent unpacked app.asar, grepped client source, extracted preset YAMLs and tried to decompress multi-frame session logs — tens of minutes and tens of thousands of tokens — before reporting what two config reads already contained. (2) Earlier the same day, "why can't the plugin market update" got the same treatment: silent digging, no interim reply, then a few sentences once the cause was trivial. The user's complaint was cost and silence, not the answer.

## Root Cause

default policy "gather evidence first, answer later" with no sufficiency stopping rule; a UI observation is treated as needing code proof when the user's configuration is the primary source; no interim message is sent.

## Fix

Evidence ladder with an explicit stop: (1) answer from the user's own config/UI first ($DSH_HOME/profiles/<profile><PATH> + visible settings); (2) if unresolved, state the hypothesis in one sentence and ask before going deeper; (3) unpack bundles / read client source / decode logs only with the user's consent. Put the conclusion in the first sentence, and announce any investigation longer than a couple of tool calls.

## Verification

Re-run the question: the profile patch (agent-default-model.reasoningEffort: low; ui-settings-account.developerTools: false) explains both facts — effort was never high (the UI shows the model default until the first message), and the picker hides built-in ptc/minimal when developerTools is false, leaving standard and cordis. Two file reads vs. an asar unpack is the measurable difference. Checklist before any deep dive: config checked? one-sentence conclusion offered? asked before going past tier 2?
