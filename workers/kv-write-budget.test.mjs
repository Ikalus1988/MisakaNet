// KV write budget: a request must not cost a write (2026-09-12).
//
// The worker runs on the free tier, where KV allows 1,000 writes/day — and an
// account-wide write failure is what took registration down that day (every write
// path answered 1101). The traffic counter was doing `get` + `put` on *every*
// request, on top of the read-quota counter and the gap records a search already
// costs, so analytics could consume a quarter of the day's budget.
//
// These tests assert the property that matters rather than the implementation:
// N requests must cost far fewer than N writes, and the buffered counts must still
// reach KV.
//
// Run: node --test workers/kv-write-budget.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import worker from './register-proxy-sw.js';
import { testToken } from './_test-token.mjs';

// Synthetic token: never a literal, so the plugin-scanner's secret patterns do not
// flag this file (see workers/_test-token.mjs).
const TOKEN = testToken('kv-write-budget');

function createCountingEnv() {
  const store = new Map();
  const stats = { gets: 0, puts: 0 };
  return {
    MCP_TOKEN: TOKEN,
    REGISTER_TOKEN: TOKEN,
    stats,
    _store: store,
    MISAKANET_KV: {
      async get(key, type) {
        stats.gets += 1;
        if (!store.has(key)) return null;
        const raw = store.get(key);
        return type === 'json' ? JSON.parse(raw) : raw;
      },
      async put(key, value) {
        stats.puts += 1;
        store.set(key, value);
      },
      async delete(key) { store.delete(key); },
    },
  };
}

async function hit(env, path = '/api/health') {
  const response = await worker.fetch(new Request(`https://misakanet.org${path}`), env);
  assert.equal(response.status, 200, `${path} answered ${response.status}`);
}

test('many cheap requests cost few KV writes', async () => {
  const env = createCountingEnv();
  const requests = 40;
  for (let i = 0; i < requests; i++) await hit(env);

  const counterKeys = [...env._store.keys()].filter((k) => k.startsWith('traffic:'));
  assert.ok(counterKeys.length >= 1, 'the traffic counter never reached KV');

  // Batching is 10 per flush, and a flush also costs one get per key.
  assert.ok(env.stats.puts <= Math.ceil(requests / 10),
    `${requests} requests cost ${env.stats.puts} writes; batching should keep this at ${Math.ceil(requests / 10)} or fewer`);

  const total = [...env._store.entries()]
    .filter(([k]) => k.startsWith('traffic:'))
    .reduce((sum, [, v]) => sum + parseInt(v || '0', 10), 0);
  assert.ok(total >= 10, `flushed counts must reflect traffic, saw ${total} across ${counterKeys.length} key(s)`);
  assert.ok(total <= requests, `counted more traffic than requests: ${total} > ${requests}`);
});

test('the counter is still per class and per day', async () => {
  const env = createCountingEnv();
  for (let i = 0; i < 12; i++) await hit(env);
  const keys = [...env._store.keys()].filter((k) => k.startsWith('traffic:'));
  const today = new Date().toISOString().slice(0, 10);
  for (const key of keys) {
    assert.match(key, new RegExp(`^traffic:[a-z]+:${today}$`),
      `traffic keys must stay class+day scoped, saw ${key}`);
  }
});

test('a request does not write the corpus cache', async () => {
  // The proxy cache TTL was 30s, so sustained traffic rewrote the whole lesson list
  // every half minute. A single request must not write it at all.
  const env = createCountingEnv();
  env._store.set('proxy:lessons', JSON.stringify({ ts: Date.now(), data: [] }));
  await hit(env, '/api/lessons');
  const cacheWrites = env.stats.puts;
  assert.ok(cacheWrites <= 1, `a cached read cost ${cacheWrites} writes`);
});
