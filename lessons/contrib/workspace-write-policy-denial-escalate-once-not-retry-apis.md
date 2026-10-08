---
domain: "devops"
title: "Writes outside the session workspace under workspace-write: escalate once with justification, don't retry other APIs"
tags:
  - "sandbox"
  - "workspace-write"
  - "escalation"
  - "file-access"
  - "acl"
status: "draft"
evidence_level: "E1"
summary_plain: "Profile edits under $DSH_HOME were denied 'sandbox: file access denied' — switch APIs once, fail, then escalate."
trigger: "sandbox: file access denied workspace-write policy switching API same denial"
verify: "operation completes under escalated run; backup exists; workspace ops continue without escalation"
---

# Writes outside the session workspace under workspace-write: escalate once with justification, do not retry through other APIs

## Problem

Profile edits under `$DSH_HOME` (outside the session workspace) were denied with `sandbox: file access denied` under the `workspace-write` policy. Time was lost trying equivalent operations through:

- PowerShell (`Set-Content`, `Out-File`)
- Node `fs` (`fs.writeFileSync`, `fs.promises.writeFile`)
- the host CLI (`tee`, `cat >`, redirect)

All of which hit the same policy. Each retry burned cycles without making progress.

## Root Cause

Treating a policy denial as a tooling problem. A confinement-mode denial is a **boundary enforced below the API surface** — the sandbox intercepts the file-write system call itself, before any language runtime or CLI wrapper gets involved. Switching API cannot succeed because the denial is at the syscall layer, not the API layer.

The agent's mental model was: "PowerShell was denied; maybe Node fs uses a different code path that the sandbox doesn't intercept." But the sandbox is *below* the runtime — Node's `fs.writeFileSync` ultimately issues the same `write(2)` syscall that PowerShell's `Out-File` does. The sandbox sees both.

## Solution

### Step 1 — Recognize the denial shape

The error string `sandbox: file access denied` (or the platform-specific equivalent: `Operation not permitted`, `EACCES`, `WERR_ACCESS_DENIED`) is a **policy denial**, not a transient failure or a missing-permission error. The distinction:

- Transient failure: retry the same operation (it might succeed on a second attempt)
- Missing permission: change the operation's parameters (different file, different mode)
- **Policy denial**: the operation is *categorically* not allowed; no parameter change will help

### Step 2 — Stop trying alternate APIs

After the first `sandbox: file access denied`, do NOT:

- retry with PowerShell if Node was denied
- retry with `tee` / `cat >` / heredoc redirect
- retry with `dd`, `cp`, `mv`, or any other file-mutating CLI
- retry with `os.system()` or `subprocess.run()` wrappers

These all hit the same syscall layer. They will all be denied.

### Step 3 — Request one-shot escalation for that exact operation

Escalate to the user (or to the orchestrator's escalation channel) with:

1. The exact file path that was denied (resolved to absolute, verified against the intended target — see Step 4).
2. The exact operation (write, append, replace, delete).
3. The justification (why this file needs to be written *outside* the session workspace).
4. A backup of the prior content (see Step 5).

The escalation should be scoped: "one-shot escalated run for `write $DSH_HOME/profiles/desktop/dsh.profile.bundles`", NOT "give me unrestricted write access to $DSH_HOME".

### Step 4 — Verify the resolved absolute path is the intended target

Before escalating, resolve the path to absolute and confirm it is what you intend:

```bash
realpath $DSH_HOME/profiles/desktop/dsh.profile.bundles
# /home/user/.dsh/profiles/desktop/dsh.profile.bundles
```

Confirm this path is the file you actually want to modify, not a symlink target, not a parent directory, not a profile from a different host. A policy-denial escalation that writes to the wrong file is the worst outcome — you'll have written outside the sandbox AND gotten the wrong file.

### Step 5 — Back up the prior content first

Before any escalated write, copy the existing file:

```bash
cp $DSH_HOME/profiles/desktop/dsh.profile.bundles{,.bak.$(date +%s)}
```

If the escalation writes a corrupted or wrong version, the backup is the rollback. The backup lives *outside* the session workspace (in `$DSH_HOME`), so it survives session reset.

## Verification

After the escalated run completes:

1. **The operation completed under the escalated run.** The file now contains the new content; verify with `cat` / `grep` against the intended new content.
2. **A backup of the prior content exists.** `ls $DSH_HOME/profiles/desktop/*.bak.*` shows the timestamped backup; `diff` confirms it has the prior content.
3. **Operations inside the workspace continue to work without escalation.** `touch $WORKSPACE/test.txt` succeeds without escalation; the sandbox boundary is intact for workspace-internal writes.

If (1) passes but (2) does not, the escalation did not back up first — re-do the backup manually from any prior state. If (3) fails, the escalation leaked broader than one-shot — re-confirm the sandbox boundary.

## Notes

- The "switch API to dodge the policy" pattern is the same shape as "switch language to dodge a type error" — the boundary is enforced below the language, so the switch cannot help. The fix is to recognize the boundary, not to find a workaround.
- The "one-shot escalation" pattern is the inverse of "give me persistent elevated access" — the orchestrator grants escalation for a single operation, then revokes it. This is the principle-of-least-privilege applied to denial recovery.
- Related lessons: `[An allowlist that rejects real data is worse than no validation]` (over-strict policy that blocks legitimate work), `[A stubbed success is not a sandbox]` (the inverse — too-permissive policy that fakes success).
