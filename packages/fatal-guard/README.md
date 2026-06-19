# @misaka-net/fatal-guard

> Zero-dependency non-invasive fatal error guard for Node.js CLIs.  
> Capture uncaught exceptions, unhandled rejections, and non-zero exits — route a structured 4-field payload to any external handler.

```bash
npm i @misaka-net/fatal-guard
FATAL_HANDLER=/usr/bin/logger node -r @misaka-net/fatal-guard/register ./app.js
```

One env var. No source code changes.

---

## Quick start

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
