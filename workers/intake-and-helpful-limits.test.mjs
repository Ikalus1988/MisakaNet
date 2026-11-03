// The two anonymous write paths #2939 measured as unbounded.
//
// Both were reachable without a token, one of them wrote to GitHub, and the other wrote a count
// that `me_events` reads as an E3 hint. Neither had a rate limit; the HTTP route next door had one
// since 2026-10-07, and the `/api/feedback` route next to `/api/helpful` had both a limit and an
// atomic counter. These are the cases that would have caught the gap.

import test from 'node:test';
import assert from 'node:assert/strict';

import worker from './register-proxy-sw.js';

/** KV-only env: `bumpCounter` falls back to KV when no D1 binding exists, which is enough for the
 *  limits under test and keeps this file independent of the D1 fake in `counters-d1.test.mjs`. */
function createEnv() {
  const store = new Map();
  return {
    MCP_TOKEN: 'test-token',
    REGISTER_TOKEN: 'test-register-token',
    // The intake path reads lessons through the KV snapshot and posts to GitHub; neither is under
    // test here, and the limit fires before either, so the calls below stop at the refusal.

    kvWrites: [],
    MISAKANET_KV: {
      async get(key, type) {
        if (!store.has(key)) return null;
        const raw = store.get(key);
        return type === 'json' ? JSON.parse(raw) : raw;
      },
      async put(key, value) { store.set(key, value); },
      async delete(key) { store.delete(key); },
    },
  };
}

const INTAKE = (ip, n = 1) => new Request('https://misakanet.org/mcp', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'MCP-Protocol-Version': '2025-06-18',
    Origin: 'https://misakanet.org',
    'CF-Connecting-IP': ip,
  },
  body: JSON.stringify({
    jsonrpc: '2.0', id: n, method: 'tools/call',
    params: { name: 'misakanet_submit_intake', arguments: { problem: `probe ${n} — the build fails on a clean checkout` } },
  }),
});

test('the MCP intake tool shares the HTTP route\'s hourly budget', async () => {
  const env = createEnv();
  // Only a *rate-limit* answer counts as the refusal: this env has no GitHub token, so each call
  // that gets past the limit fails later with "Bad credentials" — an error, but not this one.
  let refused = null;
  for (let i = 1; i <= 25 && !refused; i++) {
    const response = await worker.fetch(INTAKE('198.51.100.44', i), env);
    const body = await response.json();
    const payload = JSON.parse(body.result?.content?.[0]?.text || '{}');
    if (/Rate limited/.test(String(payload.error || ''))) refused = payload;
  }
  assert.ok(refused, '25 submissions from one address all went through — the tool advertises '
    + '"open, rate-limited" and the HTTP route caps at 10/hour');
  assert.match(String(refused.error || ''), /Rate limited \(10\/hour\)/);
});

test('a garbage Authorization header does not exempt a read from the burst window', async () => {
  // The bypass: the burst gate was `!authToken`, and `authToken` was the raw header. So
  // `Authorization: x` made it non-empty, skipped the limit, and proved nothing — a client could
  // read without bound by sending one character.
  const read = (n) => new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'MCP-Protocol-Version': '2025-06-18',
      Origin: 'https://misakanet.org',
      'CF-Connecting-IP': '198.51.100.55',
      Authorization: 'Bearer x',
    },
    body: JSON.stringify({
      jsonrpc: '2.0', id: n, method: 'tools/call',
      params: { name: 'misakanet_search', arguments: { query: 'pip install timeout', top: 1 } },
    }),
  });

  const env = createEnv();
  let refused = null;
  for (let i = 1; i <= 80 && !refused; i++) {
    const body = await (await worker.fetch(read(i), env)).json();
    const payload = JSON.parse(body.result?.content?.[0]?.text || '{}');
    if (/Too many requests/.test(String(payload.error || ''))) refused = payload;
  }
  assert.ok(refused, '80 reads with a one-character bearer were all served — the header must not '
    + 'be what exempts a caller from the burst window');
  assert.match(String(refused.error || ''), /Too many requests/);
});

test('/api/helpful is rate limited per address and lesson', async () => {
  const env = createEnv();
  const vote = (n) => new Request('https://misakanet.org/api/helpful', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'CF-Connecting-IP': '198.51.100.66' },
    body: JSON.stringify({ lesson_id: 'curl-lesson', n }),
  });

  let refused = null;
  for (let i = 1; i <= 30 && !refused; i++) {
    const response = await worker.fetch(vote(i), env);
    if (response.status === 429) refused = await response.json();
  }
  assert.ok(refused, '30 anonymous votes for one lesson all counted — that count is published as '
    + 'an E3 hint by me_events, so an unlimited write is an unlimited evidence claim');
});
