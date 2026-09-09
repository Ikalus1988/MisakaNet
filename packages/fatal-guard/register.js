#!/usr/bin/env node
/**
 * @misaka-net/fatal-guard/register
 *
 * Non-invasive fatal error guard.  Load via `node -r @misaka-net/fatal-guard/register`.
 * Hooks process.uncaughtException and process.unhandledRejection, routes
 * structured 4-field payload to the external handler defined in FATAL_HANDLER.
 *
 * Usage:
 *   FATAL_HANDLER=/usr/bin/logger node -r @misaka-net/fatal-guard/register ./app.js
 *
 * Payload (4 fields, JSON via argv[1]):
 *   schemaVersion — always 1
 *   reason        — "uncaught_exception" | "unhandled_rejection" | "exit_code"
 *   timestamp     — ISO 8601
 *   pid           — process.pid
 *
 * Design principles:
 *   - Zero dependencies (stdlib only)
 *   - Non-blocking: spawn + unref, handler failure never blocks shutdown
 *   - Injection-safe: shell=false, no env passthrough
 *   - Fire-and-forget: detached child, no wait
 */

const { runHandler } = require('./index.js');

// ── Register hooks ──────────────────────────────────────────────

/** uncaughtException — fatal, process must exit after this */
process.on('uncaughtException', (err) => {
  runHandler('uncaught_exception', err);
  process.stderr.write(`[fatal-guard] uncaughtException: ${err?.stack || err?.message || err}\n`);
  // Exit explicitly — having a listener makes Node think the error is handled
  setImmediate(() => process.exit(1));
});

/** unhandledRejection — may or may not be fatal, depending on Node version */
process.on('unhandledRejection', (reason) => {
  const err = reason instanceof Error ? reason : new Error(String(reason));
  runHandler('unhandled_rejection', err);
});

/** beforeExit — capture non-zero exit codes */
const _origExit = process.exit;
process.exit = function exit(code) {
  if (code !== 0 && code !== undefined) {
    runHandler('exit_code');
  }
  _origExit(code);
};
// Also catch signal exits
process.on('SIGTERM', () => runHandler('exit_code'));
process.on('SIGINT', () => runHandler('exit_code'));

// Self-identify
if (process.env.FATAL_HANDLER) {
  const handler = process.env.FATAL_HANDLER.trim();
  process.stderr.write(`[fatal-guard] active · handler=${handler}\n`);
} else {
  process.stderr.write(`[fatal-guard] loaded · set FATAL_HANDLER to enable\n`);
}
