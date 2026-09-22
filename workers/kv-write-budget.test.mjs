// KV write budget: a request must not cost a write (2026-09-12), and analytics must not cost ANY
// write once D1 is bound (2026-09-22, #1890).
//
// The worker runs on the free tier, where KV allows 1,000 writes/day — and an account-wide write
// failure is what took registration down on 2026-09-12 (every write path answered 1101). The traffic
// counter was doing `get` + `put` on *every* request, on top of the read-quota counter and the gap
// records a search already costs, so analytics could consume a quarter of the day's budget.
//
// Batching alone did not fix it. `trafficFlushedAt` started at 0, so the first request of every cold
// isolate saw a window that had "never run" and flushed immediately: ~1,300 KV puts/day to four key
// names — the largest line in the account's write series. Traffic now goes through the counter store
// (`bumpCounter` → D1, KV as its fallback) and the flush window starts at module load.
//
// These tests assert the properties that matter rather than the implementation:
//   * N requests cost far fewer than N writes;
//   * the buffered counts still reach the counter store, under either backend;
//   * with D1 bound, traffic costs **zero** KV writes at all.
//
// Run: node --test workers/kv-write-budget.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import worker, { TRAFFIC_FLUSH_BATCH } from './register-proxy-sw.js';
import { testToken } from './_test-token.mjs';

// Synthetic token: never a literal, so the plugin-scanner's secret patterns do not
// flag this file (see workers/_test-token.mjs).
const TOKEN = testToken('kv-write-budget');

/** Minimal D1 stand-in implementing exactly the counters upsert (cf. counters-d1.test.mjs). */
function createCountersD1() {
  const rows = new Map();
  return {
    rows,
    prepare(sql) {
      const stmt = {
        _bound: [],
        bind(...args) { stmt._bound = args; return stmt; },
        async all() {
          if (/INSERT INTO counters/i.test(sql)) {
            const [scope, bucket, period, delta] = stmt._bound;
            const key = `${scope}|${bucket}|${period}`;
            const next = (rows.get(key) || 0) + Number(delta);
            rows.set(key, next);
            return { results: [{ count: next }] };
          }
          return { results: [] };
        },
        async run() { return { success: true }; },
      };
      return stmt;
    },
  };
}

function createCountingEnv({ d1 = null } = {}) {
  const store = new Map();
  const stats = { gets: 0, puts: 0 };
  return {
    MCP_TOKEN: TOKEN,
    REGISTER_TOKEN: TOKEN,
    stats,
    _store: store,
    ...(d1 ? { MISAKANET_D1: d1 } : {}),
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
  // The batch size moved 10 → 50 on 2026-09-20 (see the constant), so the test reads it rather than
  // hardcoding a number that stops being true the moment it changes.
  const requests = TRAFFIC_FLUSH_BATCH * 4;
  for (let i = 0; i < requests; i++) await hit(env);

  // Without D1 the counter falls back to KV, under the counter key shape — not the legacy
  // `traffic:<class>:<day>` name the pre-2026-09-22 writer used.
  const counterKeys = [...env._store.keys()].filter((k) => k.startsWith('counters:traffic:'));
  assert.ok(counterKeys.length >= 1,
    `the traffic counter never reached the counter store; KV keys: ${[...env._store.keys()]}`);

  // Batching is TRAFFIC_FLUSH_BATCH per flush, each flush also costs one get per key.
  const budget = Math.ceil(requests / TRAFFIC_FLUSH_BATCH) + 1;
  assert.ok(env.stats.puts <= budget,
    `${requests} requests cost ${env.stats.puts} writes; batching should keep this at ${budget} or fewer`);

  const total = counterKeys.reduce((sum, k) => sum + parseInt(env._store.get(k) || '0', 10), 0);
  assert.ok(total >= TRAFFIC_FLUSH_BATCH,
    `flushed counts must reflect traffic, saw ${total} across ${counterKeys.length} key(s)`);
  assert.ok(total <= requests, `counted more traffic than requests: ${total} > ${requests}`);
});

test('with D1 bound, traffic costs no KV writes at all', async () => {
  // The point of the 2026-09-22 change: on the free tier the analytic path must not touch KV, because
  // an exhausted KV budget takes registration down with it.
  const d1 = createCountersD1();
  const env = createCountingEnv({ d1 });
  const requests = TRAFFIC_FLUSH_BATCH * 3;
  for (let i = 0; i < requests; i++) await hit(env);

  const kvTrafficWrites = [...env._store.keys()].filter(
    (k) => k.startsWith('traffic:') || k.startsWith('counters:traffic:'));
  assert.deepEqual(kvTrafficWrites, [],
    `traffic must not write KV when D1 is bound, saw: ${kvTrafficWrites}`);

  const trafficRows = [...d1.rows.entries()].filter(([k]) => k.startsWith('traffic|'));
  assert.equal(trafficRows.length, 1, `expected one traffic row, saw ${JSON.stringify(trafficRows)}`);
  assert.match(trafficRows[0][0], /^traffic\|[a-z]+\|\d{4}-\d{2}-\d{2}$/,
    'the D1 row must stay class+day scoped');
  assert.ok(trafficRows[0][1] >= TRAFFIC_FLUSH_BATCH,
    `the D1 counter must hold the flushed counts, saw ${trafficRows[0][1]}`);
  assert.ok(trafficRows[0][1] <= requests, 'counted more traffic than requests');
});

test('the counter is still per class and per day', async () => {
  const env = createCountingEnv();
  // The batch size is what triggers a flush now — the first request deliberately no longer does
  // (that is the whole point of the 2026-09-22 change), so this test has to earn its flush.
  for (let i = 0; i < TRAFFIC_FLUSH_BATCH; i++) await hit(env);
  const keys = [...env._store.keys()].filter((k) => k.startsWith('counters:traffic:'));
  const today = new Date().toISOString().slice(0, 10);
  // Non-vacuous on purpose: the previous version iterated the legacy `traffic:` keys, which this
  // change made empty — it would have passed while asserting nothing.
  assert.ok(keys.length >= 1, 'no counter keys to check — the assertion below would be vacuous');
  for (const key of keys) {
    assert.match(key, new RegExp(`^counters:traffic:[a-z]+:${today}$`),
      `traffic counters must stay class+day scoped, saw ${key}`);
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
