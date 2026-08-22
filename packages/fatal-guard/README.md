# @misaka-net/fatal-guard

> Zero-dependency non-invasive fatal error guard for Node.js CLIs.  
> Capture uncaught exceptions, unhandled rejections, and non-zero exits — route a structured 4-field payload to any external handler.

```bash
npm i @misaka-net/fatal-guard
FATAL_HANDLER=/usr/bin/logger node -r @misaka-net/fatal-guard/register ./app.js
```

For handlers that need an explicit executable plus arguments (useful on
Windows where a `.js` file is not directly spawnable), set
`FATAL_HANDLER_ARGS` to a JSON string array. The payload is appended as the
last argument and the child is still started with `shell: false`:

```bash
FATAL_HANDLER=node \
FATAL_HANDLER_ARGS='["/opt/bin/record-fatal.js"]' \
node -r @misaka-net/fatal-guard/register ./app.js
```

One env var. No source code changes.

---

## Quick start

### CLI flags and exit codes

The wrapper provides deterministic CLI behavior:

```text
0  wrapped command completed successfully
1  wrapped command failed or could not be started
2  invalid usage
3  wrapped command exceeded --timeout
```

```bash
fatal-guard --help
fatal-guard --version
fatal-guard --timeout 5000 -- node app.js
```

`--timeout` defaults to `0` (disabled). A missing executable, malformed option,
or missing `FATAL_HANDLER` on a crash produces an actionable stderr message.

### Wrapper mode (no code changes needed)

```bash
# Wrap any Node.js CLI — automatically detects crashes via stderr + exit code
FATAL_HANDLER=/usr/bin/logger npx @misaka-net/fatal-guard -- node app.js

# Works with any CLI tool — Vite, E2B, OpenClaw, tsdown, etc.
FATAL_HANDLER=/usr/bin/logger npx @misaka-net/fatal-guard -- ./node_modules/.bin/vite build
```

### Preload mode (`node -r`)

```bash
npm i @misaka-net/fatal-guard
FATAL_HANDLER=/usr/bin/logger node -r @misaka-net/fatal-guard/register ./app.js
```

Both modes produce identical payloads in syslog on crash (7 fields since v0.3):

```json
{
  "schemaVersion": 1,
  "reason": "uncaught_exception",
  "timestamp": "2026-07-24T...",
  "pid": 12345,
  "errorName": "TypeError",
  "message": "Cannot read properties of undefined",
  "stackSnippet": "TypeError: Cannot read properties...\n    at app.js:42:3"
}
```

All diagnostic fields (`errorName`, `message`, `stackSnippet`) are automatically redacted to prevent secret leakage.

```bash
# 1. Install
npm i @misaka-net/fatal-guard

# 2. Run any Node.js CLI with the guard preloaded
FATAL_HANDLER=/usr/bin/logger node -r @misaka-net/fatal-guard/register ./your-cli.js

# 3. Trigger a fatal error — watch syslog light up
#    (uncaught exceptions, unhandled rejections, non-zero exits all captured)
```

**Real syslog output after an uncaught exception:**

```
Jun 19 08:38:26 hostname logger[180739]:
  {"schemaVersion":1,"reason":"uncaught_exception",
   "timestamp":"2026-06-19T08:38:26.091Z","pid":180739}

Jun 19 08:38:26 hostname logger[180739]:
  {"schemaVersion":1,"reason":"exit_code",
   "timestamp":"2026-06-19T08:38:26.096Z","pid":180739}
```

---

## How it works

`register.js` hooks into three process-level fatal signals:

| Signal | Trigger | Behavior |
|--------|---------|----------|
| `uncaughtException` | Synchronous throw not caught by any try/catch | Fires handler, prints to stderr, exits with code 1 |
| `unhandledRejection` | Async promise rejection with no `.catch()` | Fires handler, prints warning |
| `exit_code` / `SIGTERM` / `SIGINT` | Non-zero exit or termination signal | Fires handler |

On each signal, the handler executable is spawned with a single JSON argv argument:

```json
{
  "schemaVersion": 1,
  "reason": "uncaught_exception",
  "timestamp": "2026-06-19T04:20:00.000Z",
  "pid": 12345
}
```

**4 fields only.** No stack traces, no environment variables, no secrets. Designed to be redacted by default — the handler decides what to enrich.

---

## Handler examples

| Handler | Command | Effect |
|---------|---------|--------|
| syslog | `FATAL_HANDLER=/usr/bin/logger` | Writes to systemd journal / syslog |
| HTTP webhook | `FATAL_HANDLER=/usr/bin/curl` | Receives JSON as argv[1] — pair with a small wrapper script for HTTP POST |
| Custom script | `FATAL_HANDLER=/opt/alert-to-slack.sh` | Write your own alert pipeline |

---

## Design principles

| Principle | Implementation |
|-----------|---------------|
| **Zero dependencies** | `require('node:child_process')` only |
| **Non-blocking** | `spawn` + `detached: true` + `unref()` — handler never blocks shutdown |
| **Injection-safe** | `shell: false` — no shell interpretation of env var or payload |
| **Fire-and-forget** | Handler failure is silently swallowed — process continues |
| **Redacted by default** | 4 fields only — no stack, no env vars, no secrets |

---

## Security notes

### CodeQL alert dismissal (shell-command-injection-from-environment)

Alerts #46, #47, #48 were dismissed as "won't fix" with the following rationale:

- **`shell: false`** is used in all `spawn()` calls — no shell interpretation
- Command/handler paths come from **user-controlled inputs** (CLI args or env vars like `FATAL_HANDLER`), not from untrusted external sources
- On Windows, `.cmd`/`.bat` files require routing through `ComSpec` (`cmd.exe`) — this is a Windows platform requirement, not a security issue
- There is no external attacker who can inject commands — the user explicitly provides the command to wrap

### Windows `.cmd`/`.bat` handling

The `spawn-command.js` module routes only `.cmd`/`.bat` files through `ComSpec` on Windows. Normal executables are spawned directly without shell involvement. See `packages/fatal-guard/src/lib/spawn-command.js` for the implementation.

---

## API

```js
const { buildPayload, runHandler } = require('@misaka-net/fatal-guard');

buildPayload('uncaught_exception');
// → '{"schemaVersion":1,"reason":"uncaught_exception","timestamp":"...","pid":12345}'

runHandler('uncaught_exception');
// → spawns FATAL_HANDLER with payload as argv[1], or no-op if FATAL_HANDLER is unset
```

---

## Related

- [GitHub](https://github.com/Ikalus1988/MisakaNet/tree/main/packages/fatal-guard)
- npm: `@misaka-net/fatal-guard`
