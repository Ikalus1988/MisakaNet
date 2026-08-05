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

const { spawn } = require('node:child_process');
const { redact } = require('./src/lib/redact');

/** Payload builder with diagnostic fields */
function buildPayload(reason, error) {
  const payload = {
    schemaVersion: 1,
    reason,
    timestamp: new Date().toISOString(),
    pid: process.pid,
  };
  if (error) {
    const err = typeof error === 'string' ? { message: error } : error;
    payload.errorName = err.name || 'Error';
    payload.message = redact(String(err.message || '')).slice(0, 500);
    if (err.stack) {
      payload.stackSnippet = redact(String(err.stack)).slice(0, 1000);
    }
  }
  return JSON.stringify(payload);
}

/** Fire-and-forget external handler invocation (supports env var fallback chain) */
function runHandler(reason, error) {
  const handler = (
    process.env.FATAL_HANDLER ||
    process.env.MISAKANET_ERROR_HANDLER ||
    process.env.VITE_ERROR_HANDLER ||
    process.env.E2B_ERROR_HANDLER ||
    process.env.OPENCLAW_ERROR_HANDLER ||
    ''
  ).trim();
  if (!handler) return;

  try {
    const payload = buildPayload(reason, error);
    const child = spawn(handler, [payload], {
      stdio: 'ignore',
      detached: true,
      shell: false,
    });
    child.on('error', () => { /* swallow — handler failure must not block */ });
    child.unref();
  } catch (_) {
    /* swallow all */
  }
}

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
