// The durable store's lifecycle: what expires is still read correctly, and is eventually reclaimed
// (2026-09-23, #2117).
//
// Two properties that arrived with the KV → D1 migration and had no test until now:
//
// 1. **`storeGet` filters expired rows.** Moving the TTL families (`rate:…`, caches, dedup hashes,
//    pairing codes) out of KV moved the semantics but not KV's housekeeping: nothing deletes them, so
//    without this the store would hand back values that the caller believes expired — and a rate limit
//    that reads a stale window is not a rate limit.
// 2. **The sweeper reclaims them.** An expired row is invisible to readers either way, so this is
//    hygiene rather than correctness — but it is the hygiene that keeps the table, and the scan over
//    it, proportional to live data instead of to everything ever written.
//
// The third test is the one that made the migration worth doing: with **D1 bound and no KV at all**, the
// per-address rate limits still work. Before #2117 those endpoints answered 503 without a KV binding, so
// a deployment that is over the KV budget lost its abuse protection.
//
// Run: node --test workers/kv-store-lifecycle.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import worker, { storeGet, storePut, sweepExpiredStore } from './register-proxy-sw.js';
import { withKvStore } from './_test-kv-store.mjs';
import { testToken } from './_test-token.mjs';

const PAST = new Date(Date.now() - 60_000).toISOString();
const FUTURE = new Date(Date.now() + 3_600_000).toISOString();

// A D1 stand-in that answers the queries this test does not care about (the handler's own lookups) and
// delegates `kv_store` to the shared helper. Without the inner stub the helper *refuses* unknown SQL on
// purpose — which is what turned a permissive stub into a visible failure earlier in this series.
const permissiveD1 = {
  prepare() {
    const stmt = { bind() { return stmt; }, async all() { return { results: [] }; },
                   async run() { return { success: true, meta: { changes: 0 } }; } };
    return stmt;
  },
};

function envWithStore() {
  return { MCP_TOKEN: testToken('kv-store-lifecycle'),
           MISAKANET_D1: withKvStore(permissiveD1) };
}

test('storeGet hides an expired row and returns a live one', async () => {
  const env = envWithStore();
  await storePut(env, 'rate:feedback:203.0.113.1', '9', { expirationTtl: -60 });   // already expired
  await storePut(env, 'rate:feedback:203.0.113.2', '4', { expirationTtl: 3600 });

  assert.equal(await storeGet(env, 'rate:feedback:203.0.113.1', 'text'), null,
    'a reader must not see a value past its TTL');
  assert.equal(await storeGet(env, 'rate:feedback:203.0.113.2', 'text'), '4');

  // Hiding the row is the query's job, and the double reads the predicate out of the SQL rather than
  // assuming it — otherwise deleting the predicate from the worker would leave this green.
  assert.ok(env.MISAKANET_D1.kvStoreSql.some((sql) => /expires_at\s*>\s*datetime\('now'\)/i.test(sql)),
    'the read must ask the database to filter expired rows, not filter them in JavaScript');
});

test('storePut without a TTL has no expiry and is always readable', async () => {
  const env = envWithStore();
  await storePut(env, 'unsolved:stale:some-lesson', JSON.stringify({ days: { '2026-09-23': 1 } }));
  const read = await storeGet(env, 'unsolved:stale:some-lesson', 'json');
  assert.equal(read.days['2026-09-23'], 1);
  assert.equal(env.MISAKANET_D1.kvStore.get('unsolved:stale:some-lesson').expires_at, null);
});

test('the sweeper reclaims expired rows and leaves everything else', async () => {
  const env = envWithStore();
  await storePut(env, 'rate:intake:203.0.113.3', '1', { expirationTtl: -1 });
  await storePut(env, 'rate:connect:203.0.113.4', '1', { expirationTtl: -1 });
  await storePut(env, 'pair:ABC234', JSON.stringify({ status: 'pending' }), { expirationTtl: 3600 });
  await storePut(env, 'gap:index', JSON.stringify(['gap:a']));

  assert.equal(await sweepExpiredStore(env), 2, 'exactly the two expired rows');
  const keys = [...env.MISAKANET_D1.kvStore.keys()];
  assert.deepEqual(keys.sort(), ['gap:index', 'pair:ABC234']);
});

test('the sweeper is a no-op without a durable store, and never throws', async () => {
  assert.equal(await sweepExpiredStore({}), 0);
  assert.equal(await sweepExpiredStore({ MISAKANET_KV: {} }), 0);
});

test('the sweeper respects its limit, so a backlog is reclaimed over several runs', async () => {
  const env = envWithStore();
  for (let i = 0; i < 5; i += 1) {
    await storePut(env, `rate:feedback:198.51.100.${i}`, '1', { expirationTtl: -1 });
  }
  assert.equal(await sweepExpiredStore(env, { limit: 2 }), 2);
  assert.equal(env.MISAKANET_D1.kvStore.size, 3);
  assert.equal(await sweepExpiredStore(env, { limit: 10 }), 3);
  assert.equal(env.MISAKANET_D1.kvStore.size, 0);
});

// The reason the rate family moved (#2117): these limits used to answer 503 without a KV binding.
test('per-address rate limits hold with D1 only and no KV at all', async () => {
  const env = envWithStore();
  const post = (ip) => worker.fetch(new Request('https://misakanet.org/api/feedback', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'CF-Connecting-IP': ip },
    body: JSON.stringify({ query: 'pip install timeout', lesson_id: 'pip-timeout-mirror',
                           feedback: 'irrelevant' }),
  }), env);

  const codes = [];
  for (let i = 0; i < 11; i += 1) codes.push((await post('203.0.113.9')).status);

  assert.ok(codes.slice(0, 10).every((c) => c === 200),
    `the first ten calls are inside the window and must pass: ${JSON.stringify(codes)}`);
  assert.equal(codes[10], 429, 'the eleventh call is over the ten-per-minute limit');

  // A different address has its own window: the limit is per caller, not global.
  assert.equal((await post('203.0.113.10')).status, 200);

  assert.equal(await storeGet(env, 'rate:feedback:203.0.113.9', 'text'), '10',
    'the window counter is durable, so the next isolate sees it too');
});
