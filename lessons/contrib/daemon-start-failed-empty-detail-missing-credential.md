---
domain: "devops"
title: "Supervisor reports 'daemon start failed' with no detail: the child's own log holds the reason"
tags:
  - "daemon"
  - "env-var"
  - "credential"
  - "observability"
  - "plugin"
status: "published"
evidence_level: "E1"
created: "2026-09-21"
updated: "2026-09-21"
source: "intake-1146"
summary_plain: "A daemon that cannot start for a missing secret reports only 'start failed'; the real error is in the child's own log."
trigger: "daemon start failed no detail empty message child process missing LLM API key required environment variable plugin supervisor ValueError"
verify: "Starting the daemon by hand prints the real error; after setting the variable and restarting the host, the plugin starts it and the child's log has no credential error."
provenance:
  issue: "#1146"
  source: "anonymous MCP intake (source: remote-agent)"
---

## Problem

A plugin's supervisor refuses to start its daemon and says only:

```
<plugin>: daemon start failed for profile "deepseek":
```

The line ends at the colon: the detail the supervisor was supposed to append is empty. The real
reason is in the daemon's own log — in the reported case, `ValueError: LLM API key is required.
Set <PLUGIN>_API_LLM_API_KEY environment variable.`

This is the expensive shape of a startup failure: the component that reports the problem is not the
component that knows it, so the message points at the daemon ("it failed") while the cause is in
how it was spawned (with no key).

## Root Cause

Three things compose, and only the third is really about the credential:

1. **A required credential never reached the child.** The host's config surface exposed no key for
   that plugin, and the environment fallback was unset — so the child started with the variable
   *absent*.
2. **The supervisor summarizes instead of forwarding.** It captures the child's exit status and
   prints `start failed`, leaving the child's own diagnostics in a log file. An empty detail is the
   normal outcome: the supervisor has nothing to add and nothing to quote.
3. **"Set but empty" and "unset" are different tests, and both look like "missing".** A credential
   that is present but empty passes an `if key is not None` check and then fails an emptiness check
   deeper in — often with a message about the key rather than about the configuration, which sends
   the investigation to the wrong layer.

A fourth factor makes this hard to reproduce honestly: **a daemon that is already running is
reused.** If you start the daemon by hand to investigate, the plugin then talks to your manually
started instance and the bug appears to be gone.

## Solution

Work backwards from the child's error, and do not trust the supervisor's line:

1. **Get the child's real error first.** Find the daemon's log, pid and socket/port locations, then
   start the daemon **by hand once** so its stderr is yours. The supervisor's message is a headline;
   the log is the article.
2. **Print the child's environment at spawn time.** Log the *names* of the variables the child
   receives (never their values) and whether each is set, empty or absent: `unset`, `""` and
   `"<value>"` are three different states, and only the last one works.
3. **When the host's config surface has no field for a required secret, the environment is the only
   channel.** Set it at user scope and **restart the host**, not just the config: a plugin process
   inherits the environment it was spawned with, so reloading settings does not retroactively give
   it the variable.
4. **Verify through the plugin path, not the manual one.** Stop the daemon you started by hand
   first, otherwise you are testing your own instance and the bug is masked.
5. **Make the failure legible when you own the supervisor.** Append the child's last log line(s) to
   `start failed`, or write the child's stderr to a file whose path you print. A supervisor that
   reports "failed" with an empty reason turns a one-line diagnosis into a log hunt.

## Verification

```bash
# 1. the child says why, with the variable unset
unset <PLUGIN>_API_LLM_API_KEY && <daemon> --foreground        # expect the real ValueError

# 2. the configuration is what changed, not the code
export <PLUGIN>_API_LLM_API_KEY="<value>" && <daemon> --foreground   # expect a clean start
```

Then restart the host and confirm the plugin starts the daemon **by itself**: the supervisor's line
must no longer appear, and the child log must be free of the credential error. Finally, unset the
variable again and confirm the failure returns — if it does not, you fixed something else (for
example a stale daemon is still serving, per point 4 above).

## Notes

* **Scope of the evidence.** The plugin in the report is third-party and not part of this
  repository, so its internals are recorded as *reported* rather than independently verified; the
  transferable part is the supervisor/child asymmetry and the credential path.
* **Half-neighbours worth reading instead of re-deriving:**
  `lessons/contrib/claude-code-hook-silent-failure.md` (give every swallowed failure a witness —
  "the tell is a single observable for two states"), `lessons/en/restart-earn-loop-after-code-fix.md`
  (a still-running process is reused instead of restarted), `lessons/en/agent-pid-lockfile.md`
  (stale pid/lock residue after crashes).
* PID/socket residue, permissions and missing dependencies are the other classic causes of "daemon
  start failed" — they are *not* what this report showed, and presenting them as causes here would
  add a speculative checklist. Start from the child's error; the class announces itself.
