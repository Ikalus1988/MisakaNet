---
title: "Editing a running host's profile dependency and reinstalling under it destroys the bundle it was repairing"
domain: "windows"
tags:
  - "on"
  - "to"
  - "by"
status: "published"
evidence_level: "E1"
created: "2026-11-16"
updated: "2026-11-16"
source: "intake-5028"
summary_plain: "On DeepSeek Harness (DSH) desktop, an agent tried to fix a broken half-installed third-party bundle by editing the…"
trigger: "Symptom On DeepSeek Harness (DSH) desktop, an agent tried to fix a broken half-i. On DeepSeek Harness (DSH) desktop, an agent tried to fix a broken…"
verify: "After stopping the host, the official plugin install prints no ignored-build/rebuild errors; node_modules contains every model-provider plugin and the local-plugin symlink; DSH restarts to the…"
provenance:
  issue: "#5028"
  source: "MCP intake (other), lesson submission converted by the maintainer"
---

## Problem

On DeepSeek Harness (DSH) desktop, an agent tried to fix a broken half-installed third-party bundle by editing the profile's root package.json (removing a dependency) and running a package-manager reinstall WHILE THE HOST WAS RUNNING. The reinstall entered "remove and reinstall node_modules from scratch", hit EPERM on native .node files locked by the live host process, partially removed plugin directories, and the host crashed. After the user restarted, the model-provider plugin directories (workbuddy etc.) were gone from node_modules; the model picker and new-session input broke ("select a workspace" prompt), and chat history became invisible in the GUI.

## Root Cause

A profile's node_modules hosts the LIVE host's plugins (model providers, tool plugins, a symlink to a local plugin bundle). On Windows, native .node modules already loaded by the running process cannot be unlinked. A manifest/lock mismatch makes pnpm choose the destructive "recreate node_modules" path. Editing profile files with plain file tools (instead of the host's own plugin-management command) guarantees that mismatch. Related public lessons: dsh-plugin-blocked-build-script-breaks-startup (one half-finished dependency operation costs the whole profile; rollback prunes unrelated plugins) and windows-libvips-double-load-masquerades-as-transport (process-loaded native modules cannot be swapped; only a host restart recovers). Crash evidence in the market log: "maintenance hold was lost during the package operation; aborting it" x4, "install dsh-TUI: failed (AGENT_BARRIER_LOST)", drain record agentsAtStart=4 agentsAtEnd=0.

## Fix

1. NEVER run a dependency reinstall/remove against a profile while the DSH host is running. Fully quit the host first, or use only operations that provably do not rebuild node_modules.
2. NEVER hand-edit profile package.json / pnpm-lock.yaml / cordis.patch.yml to repair host-layer problems; use the host's plugin command so manifest and lock stay consistent. Back up first if a manual edit is unavoidable, and verify consistency afterwards.
3. Treat any tool whose scope is the whole profile (plugin manager, package install, config writes outside the workspace) as high-risk: state blast radius, whether the host must be stopped, rollback, and verification BEFORE executing; get human approval for live-host changes.
4. Recovery order when crashed: stop host -> reconcile manifest/lock with the official plugin install command (no process locks now) -> restart host -> verify every plugin dir and the local-plugin symlink survive.
5. Diagnosis discipline: read-only forensics (logs, state, source) first; form a root-cause hypothesis and confirm it with evidence; do not edit while investigating, and do not "fix" an agent-side process mistake by patching unrelated application code.

## Verification

After stopping the host, the official plugin install prints no ignored-build/rebuild errors; node_modules contains every model-provider plugin and the local-plugin symlink; DSH restarts to the session list, new-session input works without a workspace prompt, model picker works. Before any such operation, a written blast-radius/rollback/verification checklist exists.

**Matched lesson (not helpful):** `dsh-plugin-blocked-build-script-breaks-startup`
