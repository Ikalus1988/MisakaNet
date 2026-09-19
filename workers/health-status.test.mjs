// The /api/health top-level status (issue #1822, 2026-09-18).
//
// What went wrong: the endpoint answered `ok` while every KV write failed —
// `kv_writes: {attempts: 5, failures: 5, last_ok_at: ""}` sat next to `status: "ok"`, so the single
// field a monitoring check reads said "fine". Storage falls back to D1 (PR #1804), which is exactly
// why a dead subsystem could hide: nothing depended on it, so nothing complained.
import assert from 'node:assert/strict';
import test from 'node:test';
import { healthStatus } from './register-proxy-sw.js';

test('an isolate whose every KV write failed is not "ok"', () => {
  const health = healthStatus({ hasKV: true, attempts: 5, failures: 5 });
  assert.equal(health.status, 'degraded', 'the live condition on 2026-09-18 must not read as ok');
  assert.match(health.reason, /kv writes failing: 5\/5/, health.reason);
});

test('no KV binding is a configuration, not a failure', () => {
  assert.deepEqual(healthStatus({ hasKV: false, attempts: 9, failures: 9 }), { status: 'ok' });
});

test('one transient failure does not colour the endpoint', () => {
  assert.deepEqual(healthStatus({ hasKV: true, attempts: 1, failures: 1 }), { status: 'ok' });
  assert.deepEqual(healthStatus({ hasKV: true, attempts: 10, failures: 1 }), { status: 'ok' });
});

test('no attempts yet is not evidence of a problem', () => {
  assert.deepEqual(healthStatus({ hasKV: true, attempts: 0, failures: 0 }), { status: 'ok' });
});
