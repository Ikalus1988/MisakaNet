// A KV write failure must be classified even when its global row cannot be read (2026-10-17).
//
// Measured live during the D1 outage: `/api/health` reported
// `kv writes failing: 5/5 attempts, no successful write` with `global_error_kind: "unknown"` and no
// error code. The global row lives in D1, whose reads were quota-refused, so `healthStatus` classified
// `undefined` and a condition we understand completely — KV's daily write allowance — read as
// unexplained. The isolate's own last message was available the whole time.
//
// Run: node --test workers/kv-health-local-error.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import { healthStatus, kvErrorKind } from './register-proxy-sw.js';

const localFailing = (lastError) =>
  healthStatus({ hasKV: true, attempts: 5, failures: 5, global: null, lastError });

test('the isolate message classifies the daily write allowance as a quota', () => {
  const health = localFailing('KV put() limit exceeded for the day.');
  assert.equal(health.status, 'degraded');
  assert.equal(health.kv_error_kind, 'quota');
  assert.match(health.reason, /quota/);
});

test('Cloudflare\'s coded form classifies the same way', () => {
  const health = localFailing(
    'put: your account has reached the free usage limit for this operation for today [code: 10048]');
  assert.equal(health.kv_error_kind, 'quota');
  assert.equal(health.kv_error_code, '10048');
});

test('a throttle stays a throttle, and an unreadable message stays unknown', () => {
  assert.equal(localFailing('KV PUT failed: 429 Too Many Requests').kv_error_kind, 'throttle');
  const unknown = localFailing('');
  assert.equal(unknown.kv_error_kind, 'unknown');
  assert.equal(unknown.status, 'degraded', 'degraded does not depend on knowing why');
  assert.doesNotMatch(unknown.reason, /\(unknown\)/, 'an unknown kind adds no detail to the sentence');
});

test('the global row still wins when it is readable', () => {
  const health = healthStatus({
    hasKV: true, attempts: 5, failures: 5,
    global: { lastErrorAt: new Date().toISOString(), error: 'KV put() limit exceeded for the day.' },
    lastError: '429 Too Many Requests',
  });
  assert.equal(health.kv_error_kind, 'quota', 'the fleet-wide row describes the fleet, not this isolate');
});

test('the classifier still separates the three responses on its own', () => {
  assert.equal(kvErrorKind('KV put() limit exceeded for the day.').kind, 'quota');
  assert.equal(kvErrorKind('KV PUT failed: 10009 not found').kind, 'binding');
  assert.equal(kvErrorKind('429 Too Many Requests').kind, 'throttle');
  assert.equal(kvErrorKind('socket hang up').kind, 'unknown');
});
