# @misaka-net/fatal-guard

> Non-invasive fatal error guard for Node.js CLIs — no third-party dependencies (Node built-ins only, Node ≥ 18).  
> Capture uncaught exceptions, unhandled rejections, and non-zero exits — route a structured payload to any external handler.

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

The arguments may also be part of `FATAL_HANDLER` itself — both entry points
tokenize it the same way, so `FATAL_HANDLER="node /opt/bin/record-fatal.js"`
works in wrapper mode and in preload mode:

```bash
FATAL_HANDLER="node /opt/bin/record-fatal.js" \
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

Both modes produce the same payload, and the payload carries the **error
text**, not just "exit code: 1":

```json
{
  "schemaVersion": 1,
  "reason": "uncaught_exception",
  "timestamp": "2026-07-24T...",
  "pid": 12345,
  "errorName": "TypeError",
  "message": "Cannot read properties of undefined",
  "stackSnippet": "TypeError: Cannot read properties...\n    at app.js:42:3",
  "exit_code": 1
}
```

All diagnostic fields (`errorName`, `message`, `stackSnippet`) are automatically redacted to prevent secret leakage.

### The payload fields

| Field | Meaning |
|-------|---------|
| `schemaVersion` | Payload format version (always 1) |
| `reason` | `uncaught_exception` / `unhandled_rejection` / `exit_code` / `process_crash` / `timeout` / `killed_by_<SIGNAL>` |
| `timestamp` | ISO 8601 |
| `pid` | Process id |
| `errorName` | Error constructor name |
| `message` | **The error text.** In wrapper mode this is the line that names the failure (`Error: EACCES: permission denied, …`); in preload mode it is `err.message` |
| `stackSnippet` | Redacted stack trace snippet (preload mode) / the tail of stderr (wrapper mode) |
| `snippet` | Wrapper mode only: the error line and the crash site around it — the part of stderr the old tail-only excerpt dropped |
| `exit_code` | The process exit code, when the payload reports the process exiting |

One crash produces **one** report. The preload mode used to report the crash
twice — once for the exception and once for the `process.exit(1)` that follows
it — and the second, empty report overwrote the first in any handler that
writes every payload to one file.

### Where the crash lands: `FATAL_CRASH_OUT`

The handler is started detached with `stdio: 'ignore'`, so **whatever it
prints never reaches your terminal**. The payload is therefore also written to
a file, and the path is printed on stderr:

```text
fatal-guard: crash payload written to /path/to/project/.misakanet/last-crash.json
```

- default: `.misakanet/last-crash.json` under the current directory
- `FATAL_CRASH_OUT=/some/path.json` — write somewhere else
- `FATAL_CRASH_OUT=` (empty) — do not write a file at all

That file is the delivery channel for an agent: it can read the error text and
search the corpus with it, e.g.

```bash
python3 scripts/tombstone_to_draft.py --from-file .misakanet/last-crash.json
```

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
  {"schemaVersion":1,"reason":"uncaught_exception","timestamp":"2026-06-19T08:38:26.091Z",
   "pid":180739,"errorName":"TypeError","message":"Cannot read properties of undefined",…}
```

---

## How it works

`register.js` hooks into three process-level fatal signals:

| Signal | Trigger | Behavior |
|--------|---------|----------|
| `uncaughtException` | Synchronous throw not caught by any try/catch | Fires handler, prints to stderr, exits with code 1 |
| `unhandledRejection` | Async promise rejection with no `.catch()` | Fires handler, prints warning |
| `exit_code` / `SIGTERM` / `SIGINT` | Non-zero exit or termination signal | Fires handler |

On each signal, the handler executable is spawned with the JSON payload as its
**last** argument:

```json
{
  "schemaVersion": 1,
  "reason": "uncaught_exception",
  "timestamp": "2026-06-19T04:20:00.000Z",
  "pid": 12345
}
```

**No environment variables, no secrets.** The diagnostic fields are redacted
before they are handed over — the handler decides what to enrich.

The first fatal report wins: an uncaught exception is reported once, and the
`process.exit(1)` that follows it does not produce a second, empty report that
would overwrite the first one.

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
| **No third-party dependencies** | `require('node:child_process')` only |
| **Non-blocking** | `spawn` + `detached: true` + `unref()` — handler never blocks shutdown |
| **Injection-safe** | `shell: false` — no shell interpretation of env var or payload |
| **Fire-and-forget** | Handler failure is silently swallowed — process continues |
| **Redacted by default** | Every diagnostic field passes the redactor before it leaves the process |
| **One crash, one report** | The first fatal report is the one that is delivered |
| **One timeout budget** | A handler gets 5 s on Windows, in both entry points |

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

### How `FATAL_HANDLER` is tokenized

`FATAL_HANDLER` may carry the program *and* its arguments
(`node /opt/bin/handler.js`). The command is split into program + arguments
first (`splitCommand`), and the **program** is then checked by
`sanitizeCommand`, which refuses shell metacharacters and shell interpreters.
No token ever reaches a shell — every spawn is `shell: false`.

---

## API

```js
const { buildPayload, runHandler } = require('@misaka-net/fatal-guard');

buildPayload('uncaught_exception');
// → '{"schemaVersion":1,"reason":"uncaught_exception","timestamp":"...","pid":12345}'

buildPayload('exit_code', undefined, 3);
// → the same payload plus "exit_code":3

runHandler('uncaught_exception');
// → spawns FATAL_HANDLER with payload as the last argument, or no-op if FATAL_HANDLER is unset
```

---

## Related

- [GitHub](https://github.com/Ikalus1988/MisakaNet/tree/main/packages/fatal-guard)
- npm: `@misaka-net/fatal-guard`
