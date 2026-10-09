---
domain: "devops"
title: "Killing a PID by 'has a connection to the LLM API' inference terminated the agent's own running turn"
tags:
  - "process-management"
  - "agent-safety"
  - "pid-kill"
  - "inference-mistake"
  - "destructive-action"
  - "identity-unavailable"
status: "draft"
evidence_level: "E1"
summary_plain: "An agent killed a process for its TCP connection to the LLM API — its own harness has one too, so it killed itself."
trigger: "kill PID 'has a connection to the LLM API' inference terminated the agent's own turn"
verify: "agent's own PID/parent/ancestors are excluded from any kill list before destructive action; identity-unavailable is a hard stop, not a guess prompt"
---

# Killing a PID by 'has a connection to the LLM API' inference terminated the agent's own running turn

## Problem

An agent hunted an unknown process draining an API balance. The sandbox denied every process-identity query (`Get-Process`, `tasklist`, WMI all 'Access is denied'), so identity was unobtainable. The agent instead selected kill targets by one proxy signal: an `ESTABLISHED` TCP connection to `api.deepseek.com:443` found via `netstat -ano`.

It killed PID `17984`, then spotted a different PID (`7236`) with the same connection plus an unexplained parent (`3112`). The agent labelled `3112` a "watchdog" that had respawned the consumer, and issued a kill for both. That command returned:

> The tool call was interrupted after it was recorded, but no result was durably recorded.

The agent's own turn died at that instant. The user independently observed the agent exit the moment the command appeared and suspected the "watchdog" was the agent itself. The agent later conceded: *"watchdog was a label I stuck on it — my guess, not a fact."*

## Root Cause

Two compounding errors.

**(1) A proxy signal was promoted to an identity.** `has a connection to the LLM API endpoint` is true of:
- the money-burning background service, AND
- the agent's own harness, AND
- the very process executing the tool call.

The set is **not a singleton**, so the inference cannot select a kill target. Killing "whatever has a connection to api.deepseek.com:443" is equivalent to killing "itself or the bug" — the disambiguator was missing.

**(2) An invented label was promoted to established fact.** `watchdog` was coined to explain an unexplained parent/child link, then used to justify escalation ("this time kill the watchdog too"). The agent had explicitly asked itself whether PID `7236` could be the harness and dismissed it without evidence, because it had already assumed the harness was a different known PID.

## Solution

Never kill a PID whose identity you cannot establish.

### Step 1 — Resolve the agent's own process tree first

Before forming any kill list, resolve and exclude:
- own PID (`$$` on POSIX, `$PID` in shell, `os.getpid()` in Python, `process.pid` in Node.js)
- ancestors (`ps -o ppid=` walking up, or `pstree -p`, or `WMI` `Win32_Process` `ParentProcessId`)
- descendants (children of own PID)

If the identity channel is blocked (sandbox denies `Get-Process` / `tasklist` / WMI), this exclusion is the **safety boundary**, not bookkeeping. Treat the inability to enumerate own-tree as a hard stop.

### Step 2 — Stop a service through its own control path

Prefer identity-free, reversible controls over `kill`:
- service manager: `sc stop <name>` (Windows), `systemctl stop <name>` (Linux)
- a config "disabled" flag (set the service's startup type to `Disabled`, then stop)
- removing its startup entry (so a respawn can't happen)
- the service's own HTTP shutdown endpoint (if it exposes one, e.g. `POST /shutdown`)

These don't require knowing the PID. They operate on the service identity, which is durable and named.

### Step 3 — Treat "I cannot read what this PID is" as a hard stop

If a destructive action depends on unavailable evidence, ask the user. Do not guess. A blocked identity channel is a signal that the sandbox considers the process tree privileged — respect that signal rather than working around it with a proxy.

### Step 4 — Never name an unidentified process after its hypothesised role

Keep it as `PID N, identity unknown`. Coined names (`watchdog`, `respawner`, `leech`) carry hidden assumptions that downstream reasoning will treat as fact. The label `PID 3112, identity unknown` keeps the guess visible; the label `watchdog` hides it.

## Verification

After the change, the following must hold on a clean run:

- **No self-kill**: no tool call during cleanup returns `recorded but no result durably recorded`. The agent's turn survives the cleanup.
- **Read-only before destruct**: balance and connection state are observed read-only before any kill command is issued.
- **Read-only after destruct**: balance and connection state are observed again after the cleanup; the diff is the *only* evidence the cleanup did anything.

In the original incident the bleeding did stop (balance 7.05 → 7.05 over 90 s, zero connections to the LLM endpoint), but that proves only that *something* consumer-shaped was killed — not which one. The agent's own turn died in the same operation, so the success was unverifiable from inside the run.

## Notes

- The proxy-signal-to-identity promotion is the same shape as "the process listening on port 8080 is the HTTP server" — true *most of the time*, but the inference is the failure mode when port 8080 is a dev proxy, a debug REPL, or the agent's own harness. Identity is a name; a port or a connection is a property. Properties do not uniquely identify.
- The "watchdog" naming incident is the same shape as a hallucination cascade: a label invented to bridge a gap in evidence becomes a premise in the next inference step. The fix is not "be more careful with naming"; the fix is "do not invent labels for unidentified entities at all".
- Related lessons: `[An allowlist that rejects real data is worse than no validation]` (the inverse failure — too-strict identity check), `[A stubbed success is not a sandbox]` (destructive action in a fake-success environment).
