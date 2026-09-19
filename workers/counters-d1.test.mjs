// Counters on D1, KV as the fallback (issue #1648).
//
// Why: KV's free tier charges per *distinct key written per day*, so the paths that need a
// new key per request die first. On 2026-09-12 registration failed with
// `KV put() limit exceeded for the day.` while the cron's index rewrite kept succeeding —
// a same-key rewrite is exempt. The anonymous read quota had the same shape: one new
// `rate:read:<ip>:<date>` key per visitor per day, on the request path of every read.
//
// These tests pin the migration from both sides: with D1 bound the quota works and creates
// no KV keys at all; without D1 the legacy KV behaviour — and the legacy key names — are
// preserved, because a rollback must see the same counters it wrote before.
//
// Run: node --test workers/counters-d1.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import worker from './register-proxy-sw.js';
import { testToken } from './_test-token.mjs';

const TOKEN = testToken('counters-d1');
const LESSONS = [
  { id: 'pip-timeout-mirror', title: 'pip install timeout', domain: 'python', tags: ['pip'],
    path: 'lessons/core/pip-timeout-mirror.md', summary: 'pip install times out' },
];

/** Minimal D1 stand-in that implements exactly the counters upsert. */
function createCountersD1({ fail = false, failCountersOnly = false } = {}) {
  const rows = new Map();
  return {
    rows,
    prepare(sql) {
      const stmt = {
        _bound: [],
        bind(...args) { stmt._bound = args; return stmt; },
        async all() {
          // `failCountersOnly` reproduces the interesting case: the counters table is
          // broken while lessons still read fine. (A fake that fails *everything* makes the
          // lesson load fail first, which is a different scenario.)
          if (fail || (failCountersOnly && /counters/i.test(sql))) {
            throw new Error('D1_ERROR: counters table unavailable');
          }
          if (/INSERT INTO counters/i.test(sql)) {
            const [scope, bucket, period, delta] = stmt._bound;
            const key = `${scope}|${bucket}|${period}`;
            const next = (rows.get(key) || 0) + Number(delta);
            rows.set(key, next);
            return { results: [{ count: next }] };
          }
          if (/SELECT count FROM counters/i.test(sql)) {
            const [scope, bucket, period] = stmt._bound;
            const value = rows.get(`${scope}|${bucket}|${period}`) || 0;
            return { results: [{ count: value }] };
          }
          return { results: [] };
        },
        async run() { return { success: true }; },
      };
      return stmt;
    },
  };
}

function createEnv({ d1 = null } = {}) {
  const store = new Map([
    ['proxy:lessons', JSON.stringify({ ts: Date.now(), data: LESSONS })],
  ]);
  const kvWrites = [];
  return {
    MCP_TOKEN: TOKEN,
    ...(d1 ? { MISAKANET_D1: d1 } : {}),
    kvWrites,
    MISAKANET_KV: {
      async get(key, type) {
        if (!store.has(key)) return null;
        const raw = store.get(key);
        return type === 'json' ? JSON.parse(raw) : raw;
      },
      async put(key, value) { kvWrites.push(key); store.set(key, value); },
      async delete(key) { store.delete(key); },
    },
  };
}

function readRequest(ip, query = 'pip install timeout') {
  return new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers: {
      // No Authorization header: the anonymous quota only applies to anonymous callers —
      // an authenticated token is exempt by design, which is why the first version of
      // these tests never reached the counter at all.
      'Content-Type': 'application/json',
      'MCP-Protocol-Version': '2025-06-18', 'Origin': 'https://misakanet.org',
      'CF-Connecting-IP': ip,
    },
    body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'tools/call',
      params: { name: 'misakanet_search', arguments: { query, top: 1 } } }),
  });
}

async function readResult(env, ip) {
  const response = await worker.fetch(readRequest(ip), env);
  const body = await response.json();
  return JSON.parse(body.result.content[0].text);
}

test('with D1 bound the read burst limit holds and no KV key is written', async () => {
  const env = createEnv({ d1: createCountersD1() });
  // The burst limit is what refuses now (not a day): fill the window first.
  const limit = 20;
  for (let i = 1; i <= limit; i++) {
    const result = await readResult(env, '203.0.113.7');
    assert.equal(result.error, undefined, `read ${i} must succeed: ${JSON.stringify(result)}`);
  }
  const sixth = await readResult(env, '203.0.113.7');
  // The daily cap is gone (2026-09-18 policy): reads are unlimited, what is left is a speed
  // limit — and the message says so, because "register to get more" would now be a lie.
  assert.match(String(sixth.error || ''), /Too many requests: max \d+ reads per \d+s/);
  assert.match(String(sixth.error || ''), /Reads are unlimited/, 'the refusal must not read as a quota');
  assert.match(String(sixth.hint || ''), /retry after|no registration needed/,
    'the hint must not send the reader to register — registration is no longer the way to read more');
  assert.equal(env.kvWrites.filter((key) => key.startsWith('rate:')).length, 0,
    `D1 counters must not create per-IP KV keys, saw: ${env.kvWrites.join(', ')}`);
  assert.equal(env.MISAKANET_D1.rows.get(`rate_read|203.0.113.7|burst-${new Date().toISOString().slice(0, 16).replace(':', '-')}`), limit + 1);
});

test('reads do not share a quota across IPs on D1', async () => {
  const env = createEnv({ d1: createCountersD1() });
  for (let i = 0; i < 5; i++) await readResult(env, '203.0.113.11');
  const other = await readResult(env, '203.0.113.12');
  assert.equal(other.error, undefined, 'a different IP has its own quota');
});

test('without D1 the fallback counter is used, with a parseable key', async () => {
  const env = createEnv();
  // The window is a minute now, and the key must stay unambiguous: `scope:bucket:period` is split on
  // ":" by anything reading it back, so the period is colon-free (`burst-YYYY-MM-DDTHH-MM`). This test
  // caught that when the first version used `burst:YYYY-MM-DDTHH:MM`.
  const burst = `burst-${new Date().toISOString().slice(0, 16).replace(':', '-')}`;
  const result = await readResult(env, '203.0.113.20');
  assert.equal(result.error, undefined);
  assert.ok(env.kvWrites.includes(`rate:read:203.0.113.20:${burst}`),
    `the fallback key must be the one a reader can parse: ${env.kvWrites.join(', ')}`);
});

test('a D1 counter failure fails open and is reported', async () => {
  const env = createEnv({ d1: createCountersD1({ failCountersOnly: true }) });
  const before = (await (await worker.fetch(new Request('https://misakanet.org/api/health'), env)).json()).counters;
  const result = await readResult(env, '203.0.113.30');
  assert.equal(result.error, undefined,
    'a counter problem must not block reads (fail open)');
  const after = (await (await worker.fetch(new Request('https://misakanet.org/api/health'), env)).json()).counters;
  // Deltas, not absolutes: the backend stats are module-level and shared by every test in
  // this process, so an absolute assertion here would depend on test order.
  assert.ok(after.failures > before.failures,
    `health must report the counter failure: ${JSON.stringify(after)}`);
  assert.ok(after.last_failure_at);
  assert.ok(after.kv > before.kv, `the KV fallback should have taken over: ${JSON.stringify(after)}`);
});

test('health reports which backend served the counters', async () => {
  const env = createEnv({ d1: createCountersD1() });
  const before = (await (await worker.fetch(new Request('https://misakanet.org/api/health'), env)).json()).counters;
  await readResult(env, '203.0.113.40');
  const after = (await (await worker.fetch(new Request('https://misakanet.org/api/health'), env)).json()).counters;
  assert.ok(after.d1 > before.d1, `D1 must serve the counters: ${JSON.stringify(after)}`);
  assert.equal(after.kv, before.kv, 'and no KV counter write may happen while D1 is bound');
  assert.equal(env.kvWrites.filter((key) => key.startsWith('rate:')).length, 0, env.kvWrites.join(', '));
});

test('the signal limiter also counts in D1', async () => {
  const env = createEnv({ d1: createCountersD1() });
  const response = await worker.fetch(new Request('https://misakanet.org/api/search-signal', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'CF-Connecting-IP': '203.0.113.50' },
    body: JSON.stringify({ query: 'unanswered thing', reason: 'no_match' }),
  }), env);
  assert.equal(response.status, 200);
  assert.equal(env.kvWrites.filter((key) => key.startsWith('rate:signal')).length, 0,
    `the signal limiter must not create KV keys on the D1 path: ${env.kvWrites.join(', ')}`);
  const minute = new Date().toISOString().slice(0, 16);
  assert.ok(env.MISAKANET_D1.rows.get(`signal_rate|203.0.113.50|${minute}`) >= 1);
});

test('a no-match search records a gap row instead of a KV key (#1649)', async () => {
  const env = createEnv({ d1: createCountersD1() });
  const day = new Date().toISOString().slice(0, 10);
  const pending = [];
  await worker.fetch(new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'MCP-Protocol-Version': '2025-06-18',
               'Origin': 'https://misakanet.org', 'CF-Connecting-IP': '203.0.113.60' },
    body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'tools/call',
      params: { name: 'misakanet_search',
                arguments: { query: 'zzz nothing matches this query zzz', top: 1 } } }),
  }), env, { waitUntil: (promise) => pending.push(promise) });
  await Promise.all(pending);

  assert.equal(env.MISAKANET_D1.rows.get(`gap|zzz nothing matches this query zzz|${day}`), 1,
    `the gap must be a counter row: ${JSON.stringify([...env.MISAKANET_D1.rows.keys()])}`);
  assert.equal(env.kvWrites.filter((key) => key.startsWith('gap:')).length, 0,
    `no gap:* KV key may be created on the D1 path: ${env.kvWrites.join(', ')}`);
});

test('the gap counter accumulates per query and day', async () => {
  const env = createEnv({ d1: createCountersD1() });
  const day = new Date().toISOString().slice(0, 10);
  for (let i = 0; i < 3; i++) {
    const pending = [];
    await worker.fetch(new Request('https://misakanet.org/mcp', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'MCP-Protocol-Version': '2025-06-18',
                 'Origin': 'https://misakanet.org', 'CF-Connecting-IP': '203.0.113.61' },
      body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'tools/call',
        params: { name: 'misakanet_search',
                  arguments: { query: 'another unmatched query qqq', top: 1 } } }),
    }), env, { waitUntil: (promise) => pending.push(promise) });
    await Promise.all(pending);
  }
  assert.equal(env.MISAKANET_D1.rows.get(`gap|another unmatched query qqq|${day}`), 3);
});
