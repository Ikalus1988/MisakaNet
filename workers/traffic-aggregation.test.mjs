// The daily traffic roll-up reads the same store the flush writes (2026-09-22, #1890).
//
// Traffic counts moved from KV to the counter store, so the aggregator had to move with them —
// otherwise it would keep reading four keys that nothing writes any more and roll up zeros every
// night while the endpoint reported real numbers.
//
// The legacy `traffic:<class>:<day>` key is still read, deliberately: on the day this shipped (and if
// it is ever rolled back) those keys hold the only copy of the day's counts, and a roll-up that
// silently loses a day is worse than one that reads two stores.
//
// Run: node --test workers/traffic-aggregation.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import { aggregateDailyTraffic } from './register-proxy-sw.js';
import { withKvStore } from './_test-kv-store.mjs';

function createFakeKV(seed = {}) {
  const store = new Map(Object.entries(seed));
  return {
    async get(key, type) {
      if (!store.has(key)) return null;
      const raw = store.get(key);
      return type === 'json' ? JSON.parse(raw) : raw;
    },
    async put(key, value, opts) {
      store.set(key, value);
    },
    async delete(key) {
      store.delete(key);
    },
    _store: store,
  };
}

/** Minimal D1 stand-in answering exactly the counters SELECT (cf. counters-d1.test.mjs). */
function createCountersD1(seed = {}) {
  const rows = new Map(Object.entries(seed)); // `${scope}|${bucket}|${period}` -> count
  return {
    rows,
    prepare(sql) {
      const stmt = {
        _bound: [],
        bind(...args) { stmt._bound = args; return stmt; },
        async all() {
          if (/SELECT count FROM counters/i.test(sql)) {
            const [scope, bucket, period] = stmt._bound;
            const value = rows.get(`${scope}|${bucket}|${period}`);
            return value === undefined ? { results: [] } : { results: [{ count: value }] };
          }
          return { results: [] };
        },
        async run() { return { success: true }; },
      };
      return stmt;
    },
  };
}

const TODAY = new Date().toISOString().slice(0, 10);
const MONTH = TODAY.slice(0, 7);

test('aggregateDailyTraffic sums D1 counters into monthly keys', async () => {
  const kv = createFakeKV();
  const d1 = createCountersD1({
    [`traffic|mcp|${TODAY}`]: 100,
    [`traffic|agent|${TODAY}`]: 50,
    [`traffic|crawler|${TODAY}`]: 10,
    [`traffic|pageview|${TODAY}`]: 200,
  });

  const store = withKvStore(d1);
  const result = await aggregateDailyTraffic({ MISAKANET_KV: kv, MISAKANET_D1: store });
  assert.equal(result.aggregated, 360);
  assert.equal(result.month, MONTH);
  assert.equal(result.date, TODAY);

  // The monthly roll-up is a durable-store row since #2120 (D1 first, KV as the fallback), so these read
  // through the same helper the worker reads through. Asserting against the KV stub described the
  // fallback, and would have passed while the totals were stored somewhere the assertion never looked.
  const monthly = (cls) => store.kvStore.get(`traffic-month:${cls}:${MONTH}`)?.value;
  assert.equal(monthly('mcp'), '100');
  assert.equal(monthly('agent'), '50');
  assert.equal(monthly('crawler'), '10');
  assert.equal(monthly('pageview'), '200');
});

test('the legacy KV traffic keys are still read (transition and rollback)', async () => {
  // Before 2026-09-22 the flush wrote `traffic:<class>:<day>`. Anything written before the switch
  // lives only there, and a rollback lands there again.
  const kv = createFakeKV({ [`traffic:mcp:${TODAY}`]: '100', [`traffic:agent:${TODAY}`]: '50' });
  const result = await aggregateDailyTraffic({ MISAKANET_KV: kv });
  assert.equal(result.aggregated, 150);
  assert.equal(kv._store.get(`traffic-month:mcp:${MONTH}`), '100');
  assert.equal(kv._store.get(`traffic-month:agent:${MONTH}`), '50');
});

test('the KV counter fallback shape is read too (D1 unhappy, KV carrying the counts)', async () => {
  // `bumpCounter` falls back to `counters:<scope>:<bucket>:<period>` when D1 is unavailable, so a day
  // spent in fallback must still roll up.
  const kv = createFakeKV({ [`counters:traffic:mcp:${TODAY}`]: '70' });
  const result = await aggregateDailyTraffic({ MISAKANET_KV: kv });
  assert.equal(result.aggregated, 70);
  assert.equal(kv._store.get(`traffic-month:mcp:${MONTH}`), '70');
});

test('aggregateDailyTraffic is idempotent (skips if marker exists)', async () => {
  const kv = createFakeKV({ [`traffic-agg-marker:${TODAY}`]: '1' });
  const d1 = createCountersD1({ [`traffic|mcp|${TODAY}`]: 100 });

  const result = await aggregateDailyTraffic({ MISAKANET_KV: kv, MISAKANET_D1: d1 });
  assert.equal(result.skipped, true);
  assert.equal(result.date, TODAY);
  assert.equal(kv._store.get(`traffic-month:mcp:${MONTH}`), undefined,
    'a skipped run must not write a monthly key');
});

test('aggregateDailyTraffic accumulates with existing monthly totals', async () => {
  const kv = createFakeKV({ [`traffic-month:mcp:${MONTH}`]: '200' }); // existing monthly total
  const d1 = createCountersD1({ [`traffic|mcp|${TODAY}`]: 50 });

  const store = withKvStore(d1);
  const result = await aggregateDailyTraffic({ MISAKANET_KV: kv, MISAKANET_D1: store });
  assert.equal(result.aggregated, 50);
  // The KV-era total is still read (storeGet falls back to KV), and the accumulated one is durable.
  assert.equal(store.kvStore.get(`traffic-month:mcp:${MONTH}`)?.value, '250');
});

test('aggregateDailyTraffic handles zero daily counts gracefully', async () => {
  const kv = createFakeKV({});
  const d1 = createCountersD1({});

  const store = withKvStore(d1);
  const result = await aggregateDailyTraffic({ MISAKANET_KV: kv, MISAKANET_D1: store });
  assert.equal(result.aggregated, 0);
  assert.equal(store.kvStore.get(`traffic-month:mcp:${MONTH}`), undefined);
  assert.equal(kv._store.get(`traffic-month:mcp:${MONTH}`), undefined);
});
