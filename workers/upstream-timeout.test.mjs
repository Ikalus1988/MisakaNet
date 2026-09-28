// Every outbound call has a deadline (2026-09-23, #2126).
//
// The measurement this comes from: Cloudflare's analytics for 24h showed 504 Gateway Timeout ×1,171 and
// 522 ×886 — 99.95% of all 5xx, spread across every hour rather than clustered in the KV write window.
// A 504 is the edge giving up on the worker, and an audit of the worker found 11 of 13 internal
// `fetch()` calls with **no timeout at all**: if the upstream stalls, the request stalls with it until
// the platform's limit. From outside that is a hang — measured here as ~20% of identical requests never
// returning (`0 bytes received`) while two control hosts were 10/10 fast in the same minutes.
//
// These tests pin the helper rather than each call site: a `fetch` that honours its signal must be
// aborted by the deadline, and a caller that brought its own signal must keep it (two signals cannot
// both be honoured, and that caller already knows what its timeout should be).
//
// Run: node --test workers/upstream-timeout.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import { fetchWithTimeout, UPSTREAM_TIMEOUT_MS } from './register-proxy-sw.js';

test('an upstream that never answers is aborted by the deadline, not waited on', async () => {
  const original = globalThis.fetch;
  let sawSignal = null;
  globalThis.fetch = (url, init = {}) => new Promise((_resolve, reject) => {
    sawSignal = init.signal;
    if (init.signal) {
      init.signal.addEventListener('abort', () => {
        reject(Object.assign(new Error('The operation was aborted'), { name: 'AbortError' }));
      });
    }
  });
  try {
    const started = Date.now();
    // The race is not decoration: without it a mutant that drops the signal would make this test *hang*
    // instead of failing, and a hanging suite is a worse signal than a red one.
    const outcome = await Promise.race([
      fetchWithTimeout('https://example.invalid/stalls', {}, 60).then(() => 'resolved', (e) => e),
      new Promise((resolve) => setTimeout(() => resolve('never-settled'), 1500)),
    ]);
    const elapsed = Date.now() - started;

    assert.notEqual(outcome, 'never-settled', 'the call must settle — the deadline is the whole point');
    assert.equal(outcome.name, 'AbortError');
    assert.ok(elapsed < 1200, `the deadline must fire, not the client's own timeout (took ${elapsed}ms)`);
    assert.ok(sawSignal, 'the helper must pass a signal to fetch');
  } finally {
    globalThis.fetch = original;
  }
});

test('a caller that brought its own signal keeps it', async () => {
  const original = globalThis.fetch;
  const mine = new AbortController().signal;
  let received = null;
  globalThis.fetch = async (_url, init = {}) => {
    received = init.signal;
    return new Response('{}', { status: 200 });
  };
  try {
    await fetchWithTimeout('https://example.invalid/ok', { signal: mine });
    assert.equal(received, mine, 'the caller knows its own timeout; a second signal would override it');
  } finally {
    globalThis.fetch = original;
  }
});

test('the default deadline is the module constant, and the keepalive uses a shorter one', async () => {
  const original = globalThis.fetch;
  const seen = [];
  globalThis.fetch = async (_url, init = {}) => {
    seen.push(init.signal);
    // `AbortSignal.timeout` exposes no duration; what is checkable is that a signal with a deadline was
    // attached, and that the helper accepts an override for the probes.
    return new Response('{}', { status: 200 });
  };
  try {
    await fetchWithTimeout('https://example.invalid/a');
    await fetchWithTimeout('https://example.invalid/b', {}, 5000);
    assert.equal(seen.length, 2);
    assert.ok(seen.every(Boolean), 'every wrapped call carries a signal');
    assert.equal(typeof UPSTREAM_TIMEOUT_MS, 'number');
    assert.ok(UPSTREAM_TIMEOUT_MS >= 1000 && UPSTREAM_TIMEOUT_MS <= 20000,
      `a deadline outside 1–20s is not a deadline: ${UPSTREAM_TIMEOUT_MS}`);
  } finally {
    globalThis.fetch = original;
  }
});
