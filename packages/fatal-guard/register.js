#!/usr/bin/env node
/**
 * @misaka-net/fatal-guard/register
 *
 * Non-invasive fatal error guard.  Load via `node -r @misaka-net/fatal-guard/register`.
 * Hooks process.uncaughtException and process.unhandledRejection, routes
 * structured payload to the external handler defined in FATAL_HANDLER.
 *
 * Usage:
 *   FATAL_HANDLER=/usr/bin/logger node -r @misaka-net/fatal-guard/register ./app.js
 *
 * Payload (JSON, passed as the last argv entry):
 *   schemaVersion — always 1
 *   reason        — "uncaught_exception" | "unhandled_rejection" | "exit_code"
 *   timestamp     — ISO 8601
 *   pid           — process.pid
 *   errorName     — error constructor name (diagnostic fields, v0.3+)
 *   message       — redacted error message (v0.3+)
 *   stackSnippet  — redacted stack trace snippet (v0.3+)
 *   exit_code     — process exit code, when the process is the one exiting (#3645)
 *
 * Design principles:
 *   - Zero dependencies (stdlib only)
 *   - Non-blocking: spawn + unref, handler failure never blocks shutdown
 *   - Injection-safe: shell=false, no env passthrough
 *   - Fire-and-forget: detached child, no wait
 *   - One crash, one report: the first fatal report is never overwritten
 */

const { buildPayload, runHandler } = require('./index.js');

// ── Register hooks ──────────────────────────────────────────────

// One crash, one report.
//
// The uncaughtException handler exits the process explicitly, and the wrapped
// process.exit() below fired a *second* report for the same crash. That second
// payload carries no error text at all, and a handler that writes every payload
// to one file therefore ends up holding the second one — the crash reason and
// the error message were gone by the time anyone read the file (#3645).
//
// The first fatal report wins: whichever fatal signal the process hits first is
// the one that is delivered, and no later report can overwrite it.
let crashReported = false;

/** uncaughtException — fatal, process must exit after this */
process.on('uncaughtException', (err) => {
  crashReported = true;
  runHandler('uncaught_exception', err, buildPayload('uncaught_exception', err, 1));
  process.stderr.write(`[fatal-guard] uncaughtException: ${err?.stack || err?.message || err}\n`);
  // Exit explicitly — having a listener makes Node think the error is handled
  setImmediate(() => process.exit(1));
});

/** unhandledRejection — may or may not be fatal, depending on Node version */
process.on('unhandledRejection', (reason) => {
  const err = reason instanceof Error ? reason : new Error(String(reason));
  crashReported = true;
  runHandler('unhandled_rejection', err, buildPayload('unhandled_rejection', err));
});

/** beforeExit — capture non-zero exit codes */
const _origExit = process.exit;
process.exit = function exit(code) {
  if (!crashReported && code !== 0 && code !== undefined) {
    runHandler('exit_code', undefined, buildPayload('exit_code', undefined, code));
  }
  _origExit(code);
};
// Also catch signal exits
process.on('SIGTERM', () => { if (!crashReported) runHandler('exit_code'); });
process.on('SIGINT', () => { if (!crashReported) runHandler('exit_code'); });

// Self-identify
if (process.env.FATAL_HANDLER) {
  const handler = process.env.FATAL_HANDLER.trim();
  process.stderr.write(`[fatal-guard] active · handler=${handler}\n`);
} else {
  process.stderr.write(`[fatal-guard] loaded · set FATAL_HANDLER to enable\n`);
}
