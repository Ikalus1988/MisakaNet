# Node Hardening — @misaka-net/fatal-guard

> How to harden any Node.js CLI process with zero-dependency fatal error monitoring.
> Two modes: **wrapper** (no code changes) and **preload** (`node -r`).

## Why

Node.js processes crash silently. `uncaughtException` fires but by the time your monitoring picks it up, the PID is gone, stderr is lost, and you have no trace.

fatal-guard solves this by capturing the fatal signal and routing a structured 4-field JSON payload to any external handler (syslog, webhook, custom script) before the process disappears.

## Mode 1: Wrapper (recommended for production)

Wrap any existing CLI command — zero source code changes:

```bash
# Basic usage
FATAL_HANDLER=/usr/bin/logger npx @misaka-net/fatal-guard -- node app.js

# With any Node.js CLI tool
FATAL_HANDLER=/usr/bin/logger npx @misaka-net/fatal-guard -- ./node_modules/.bin/vite build

# In a systemd service file
ExecStart=/usr/bin/env FATAL_HANDLER=/usr/bin/logger /usr/bin/npx @misaka-net/fatal-guard -- /usr/bin/node /opt/app/server.js
```

**How it works:** The wrapper spawns the command as a child process, monitors stderr for error patterns, and fires the handler when the process exits non-zero with error output. The handler receives the standard 4 fields plus a `snippet` of the last stderr lines.

## Mode 2: Preload (`node -r`)

For projects where you control the entry point:

```bash
npm i @misaka-net/fatal-guard
FATAL_HANDLER=/usr/bin/logger node -r @misaka-net/fatal-guard/register ./app.js
```

This hooks into `process.on('uncaughtException')`, `process.on('unhandledRejection')`, and non-zero `process.exit()` calls — no source changes needed.

## Env var reference

| Variable | Priority | Used by |
|----------|----------|---------|
| `FATAL_HANDLER` | 1st | Any |
| `MISAKANET_ERROR_HANDLER` | 2nd | MisakaNet nodes |
| `VITE_ERROR_HANDLER` | 3rd | Vite wrapper |
| `E2B_ERROR_HANDLER` | 4th | E2B wrapper |
| `OPENCLAW_ERROR_HANDLER` | 5th | OpenClaw wrapper |

The first non-empty variable wins. This means one `FATAL_HANDLER` covers everything, but you can set project-specific overrides.

## Payload format

```json
{
  "schemaVersion": 1,
  "reason": "uncaught_exception",
  "timestamp": "2026-06-19T08:38:26.091Z",
  "pid": 180739
}
```

Wrapper mode adds a `snippet` field with the last 4 lines of stderr (truncated to 500 chars).

## Example: systemd integration

```ini
[Service]
ExecStart=/usr/bin/env FATAL_HANDLER=/usr/bin/logger /usr/bin/npx @misaka-net/fatal-guard -- /usr/bin/node /opt/app/server.js
Restart=on-failure
RestartSec=5
```

Journalctl will show both the app's stdout/stderr and the fatal-guard crash payload:

```
Jun 19 08:38:26 hostname logger[180739]:
  {"schemaVersion":1,"reason":"uncaught_exception",
   "timestamp":"2026-06-19T08:38:26.091Z","pid":180739,
   "snippet":"Error: connection refused\n    at Socket._onTimeout (...)"}
```

## Related

- `npx @misaka-net/fatal-guard --help`
- [GitHub](https://github.com/Ikalus1988/MisakaNet/tree/main/packages/fatal-guard)
- npm: `@misaka-net/fatal-guard`
