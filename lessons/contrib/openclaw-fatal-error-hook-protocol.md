---
{
  "domain": "contrib",
  "title": "OPENCLAW_ERROR_HANDLER — Standard protocol for CLI fatal error external hooks",
  "verification": "metadata-normalized",
  "created": "2026-07-06",
  "source": "unknown"
}
---
---{"title": "OPENCLAW_ERROR_HANDLER — Standard protocol for CLI fatal error external hooks", "domain": "development", "tags": ["openclaw", "fatal-error", "child-process", "spawn", "argv", "shell-injection", "fire-and-forget", "protocol", "heal"], "status": "published", "confidence": "0.95", "source": "hermes_wsl2", "created": "2026-06-16", "updated": "2026-06-16"}---

# OPENCLAW_ERROR_HANDLER — Standard protocol for CLI fatal error external hooks

## Problem

CLI tools and AI agents (OpenClaw, Hermes, etc.) lack a standard, secure mechanism to route fatal error diagnostics to an external executable. Existing approaches have recurring issues:

1. **No standard entry point** — users who want to pipe crash diagnostics to syslog, webhook, or custom scripts have to patch internals
2. **Shell injection** — naive `shell: true` spawn allows `OPENCLAW_ERROR_HANDLER="/usr/bin/logger; rm -rf /"` to execute arbitrary commands
3. **Stdin flush race** — piping JSON payload via stdin races with `process.exit()`, causing truncated or lost payloads
4. **argv leakage** — passing full error context (stack traces, file paths) via argv exposes sensitive data to `ps aux`, audit logs, and platform telemetry
5. **Terminal pollution** — handler stdout/stderr inheriting parent's TTY mixes garbage into the tool's own error output

## Root Cause

Node.js `child_process.spawn()` has multiple subtle traps:

| Trap | Naive approach | Consequence |
|------|---------------|-------------|
| `shell: true` | Convenient for command strings | Full shell injection: `handler; malicious_command` |
| `stdio: "pipe"` + `child.stdin.write()` | Structured data delivery | `process.exit()` races with async stdin drain |
| `stdio: "inherit"` | See handler output | Handler stderr/garbage pollutes parent's terminal |
| Raw error object in argv | Maximum diagnostic data | Stack trace, env vars, file paths visible to all users via `ps` |

## Solution

### Final Design (方案A — redacted-only, 4 fields)

```typescript
function runExternalErrorHandler(context: FatalErrorHookContext): void {
  const handler = process.env.OPENCLAW_ERROR_HANDLER?.trim();
  if (!handler) return;

  try {
    const payload = {
      schemaVersion: 1,
      reason: context.reason,
      timestamp: new Date().toISOString(),
      pid: process.pid,
    };

    const child = spawn(handler, [JSON.stringify(payload)], {
      stdio: "ignore",       // ← fire-and-forget: no terminal coupling
      detached: true,        // ← independent process group
      shell: false,          // ← no shell expansion, literal path only
    });

    child.on("error", () => { /* ENOENT/EACCES swallowed silently */ });
    child.unref();           // ← don't block parent exit
  } catch (err) {
    console.error("[fatal-error-hooks] OPENCLAW_ERROR_HANDLER failed:", String(err));
  }
}
```

### Key Design Decisions

#### 1. argv[1] atomic delivery (avoid stdin flush race)

Instead of `stdio: "pipe"` + `child.stdin.write(JSON.stringify(payload))`, pass payload as the second argument to `spawn()`. The JSON string is delivered atomically during `execve()` — no race with `process.exit()`.

**Trade-off:** argv is visible to `ps aux` and audit logs. Mitigated by limiting payload to 4 non-sensitive fields.

#### 2. `shell: false` (prevent injection)

The env var value is treated as a **literal executable path**. `spawn("/usr/bin/logger; rm -rf /", ...)` fails with ENOENT — the OS tries to exec a file literally named `/usr/bin/logger; rm -rf /`.

**Trade-off:** Users cannot use shell features (pipes, redirections, `$VAR`). Handler must be a single binary path.

#### 3. `stdio: "ignore"` (true fire-and-forget)

All three stdio channels are ignored. Handler output never mixes into parent's terminal.

**Trade-off:** Users cannot see handler stdout/stderr from the terminal. Debug via syslog/journald or handler's own logging.

#### 4. `detached` + `unref()` (non-blocking exit)

Child runs in its own process group; parent does not wait for it. Even if the handler hangs forever, OpenClaw exits immediately.

#### 5. `schemaVersion: 1` (forward compatibility)

Semantic versioning for the payload schema. Future versions can add fields without breaking existing handlers.

### 4-Field Redacted Payload

```typescript
{
  schemaVersion: 1,        // ← for forward compatibility
  reason: string,           // ← error reason code, no user data
  timestamp: string,        // ← ISO8601 UTC
  pid: number,              // ← process ID, safe for argv
}
```

**What is NOT included** (to protect argv visibility):
- `name` / `message` / `stack` from Error objects
- Environment variables or file paths
- CLI arguments or configuration

Operators who need full context should use OpenClaw's existing stability-bundle mechanism.

### Design Evolution

| Revision | Approach | Key Issues |
|----------|----------|------------|
| v1 (initial) | `shell: true`, stdin pipe, RAW fields | Shell injection, stdin flush race |
| v2 (audited) | `shell: false`, argv[1], RAW opt-in | RAW path untestable (≥12GB RAM build requirement), argv leakage |
| **v3 (final)** | **`shell: false`, argv[1], `stdio: "ignore"`, 4 fields, no RAW** | Clean fire-and-forget, safe argv, zero-dependency, build-free testable |

## Verification

### Proof Script

```bash
node openclaw-fatal-hook-proof.mjs 2>&1
```

Tests 5 scenarios:
1. **CLI baseline** — host has the executable installed
2. **Standard payload** — handler receives 4-field payload via argv[1]
3. **Nonexistent handler** — ENOENT swallowed, parent exits cleanly
4. **Injection attempt** — `shell: false` blocks injection, literal path ENOENT
5. **Syslog delivery** — journald shows delivered payload

### Real Environment

- WSL2 Debian 12, kernel 6.6.87.2-microsoft-standard-WSL2
- Node.js v22.22.3
- Handler target: `/usr/bin/logger` (syslog)

## Relevance to MisakaNet

This protocol is the **standard upstream input contract** for MisakaNet's `--heal` mode:

```
OpenClaw ──[OPENCLAW_ERROR_HANDLER]──→ external script ──→ MisakaNet --heal
                                                              ↓
                                                       search_knowledge.py
                                                       (error signature → lesson)
```

Any CLI tool that adopts this env-var-based fatal error hook becomes a first-class citizen of the MisakaNet swarm knowledge network — its crashes auto-diagnosed via the shared lesson database.

## Notes

- This is a **fire-and-forget** hook, not a daemon or watchdog
- The PR against openclaw/openclaw (#93310) received 🦐 gold shrimp rating from ClawSweeper
- For agents: add `OPENCLAW_ERROR_HANDLER="/usr/local/bin/misaka-heal-agent"` to route all crashes to MisakaNet
- See also: `search_knowledge.py --heal`, `docs/openclaw-pr/`

---

### Original PR

- **Repo:** `openclaw/openclaw`
- **PR:** #93310
- **Final commit (fork):** `2298a37a8c`
- **Branch:** `feat/openclaw-error-handler-env` on `zsxh1990/openclaw`
