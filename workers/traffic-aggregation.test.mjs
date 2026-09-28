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
import { aggregateDailyTraffic, readMonthlyTraffic, storePut } from './register-proxy-sw.js';
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
          // `bumpCounter` upserts with `RETURNING count` and binds (scope, bucket, period, delta). A stub
          // that accepts the write and forgets it makes every later read describe the past, which is how
          // a migration test passes while nothing is stored.
          if (/INSERT INTO counters/i.test(sql)) {
            const [scope, bucket, period, delta] = stmt._bound;
            const key = `${scope}|${bucket}|${period}`;
            const next = (rows.get(key) || 0) + Number(delta || 0);
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

const TODAY = new Date().toISOString().slice(0, 10);
const MONTH = TODAY.slice(0, 7);

test('aggregateDailyTraffic sums D1 counters into monthly rows', async () => {
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

  // The monthly total is a `counters` row since #2120 — `scope='traffic-month'`, one bucket per class.
  // These read it through the worker's own reader, because asserting against whichever store happened to
  // hold it is how a test passes while the value is somewhere the assertion never looks.
  const env = { MISAKANET_KV: kv, MISAKANET_D1: store };
  assert.equal(await readMonthlyTraffic(env, 'mcp', MONTH), 100);
  assert.equal(await readMonthlyTraffic(env, 'agent', MONTH), 50);
  assert.equal(await readMonthlyTraffic(env, 'crawler', MONTH), 10);
  assert.equal(await readMonthlyTraffic(env, 'pageview', MONTH), 200);

  // And it is queryable like any other counter, which is the point of the move.
  assert.equal(d1.rows.get(`traffic-month|mcp|${MONTH}`), 100, 'the row is in the counters table');
});

test('the legacy KV traffic keys are still read (transition and rollback)', async () => {
  // Before 2026-09-22 the flush wrote `traffic:<class>:<day>`. Anything written before the switch
  // lives only there, and a rollback lands there again.
  const kv = createFakeKV({ [`traffic:mcp:${TODAY}`]: '100', [`traffic:agent:${TODAY}`]: '50' });
  const env = { MISAKANET_KV: kv };
  const result = await aggregateDailyTraffic(env);
  assert.equal(result.aggregated, 150);
  // No D1 here, so the roll-up lands in the counter-key shape `bumpCounter` falls back to.
  assert.equal(await readMonthlyTraffic(env, 'mcp', MONTH), 100);
  assert.equal(await readMonthlyTraffic(env, 'agent', MONTH), 50);
});

test('the KV counter fallback shape is read too (D1 unhappy, KV carrying the counts)', async () => {
  // `bumpCounter` falls back to `counters:<scope>:<bucket>:<period>` when D1 is unavailable, so a day
  // spent in fallback must still roll up.
  const kv = createFakeKV({ [`counters:traffic:mcp:${TODAY}`]: '70' });
  const env = { MISAKANET_KV: kv };
  const result = await aggregateDailyTraffic(env);
  assert.equal(result.aggregated, 70);
  assert.equal(await readMonthlyTraffic(env, 'mcp', MONTH), 70);
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

test('aggregateDailyTraffic accumulates onto an existing monthly row', async () => {
  const d1 = withKvStore(createCountersD1({
    [`traffic|mcp|${TODAY}`]: 50,
    [`traffic-month|mcp|${MONTH}`]: 200,     // the month so far
  }));
  const env = { MISAKANET_KV: createFakeKV(), MISAKANET_D1: d1 };

  const result = await aggregateDailyTraffic(env);
  assert.equal(result.aggregated, 50, 'the run reports the day it aggregated');
  assert.equal(await readMonthlyTraffic(env, 'mcp', MONTH), 250);
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


// ── #2120: the monthly total is a `counters` row, not a key ──────────────────────

test('the monthly roll-up writes a counters row and no KV-era key', async () => {
  const kv = createFakeKV();
  const d1 = withKvStore(createCountersD1({ [`traffic|mcp|${TODAY}`]: 100 }));
  const env = { MISAKANET_KV: kv, MISAKANET_D1: d1 };

  const result = await aggregateDailyTraffic(env);
  assert.equal(result.aggregated, 100);
  assert.equal(await readMonthlyTraffic(env, 'mcp', MONTH), 100);

  assert.equal(kv._store.get(`traffic-month:mcp:${MONTH}`), undefined,
    'the key is not written any more — nothing read it, and a second store is a second answer');
});

test('a pre-move monthly total is carried over once, then the key is deleted', async () => {
  // The transition, and the only place this can go wrong in two ways: seeding without deleting counts
  // the old total again on the next run, and deleting without seeding loses the month.
  const env = { MISAKANET_KV: createFakeKV(), MISAKANET_D1: withKvStore(createCountersD1({})) };
  await storePut(env, `traffic-month:mcp:${MONTH}`, '200', { expirationTtl: 3600 });

  const d1WithDaily = withKvStore(createCountersD1({ [`traffic|mcp|${TODAY}`]: 50 }));
  const env2 = { MISAKANET_KV: createFakeKV(), MISAKANET_D1: d1WithDaily };
  await storePut(env2, `traffic-month:mcp:${MONTH}`, '200');   // the same pre-move total

  const result = await aggregateDailyTraffic(env2);
  assert.equal(result.aggregated, 50, 'the run reports today\'s daily count, not the carried total');
  assert.equal(await readMonthlyTraffic(env2, 'mcp', MONTH), 250, 'carried once: 200 + 50');
  assert.equal(d1WithDaily.kvStore.has(`traffic-month:mcp:${MONTH}`), false,
    'and the key is gone, so a later run cannot count the carried total twice');
});

test('with D1 absent the roll-up still happens, in the durable store', async () => {
  // The no-D1 deployment must keep working: `bumpCounter` falls back to its KV path and the reader
  // checks the store second.
  const kv = createFakeKV();
  const env = { MISAKANET_KV: kv, MISAKANET_D1: withKvStore(undefined) };
  await storePut(env, `traffic-month:mcp:${MONTH}`, '7');
  await aggregateDailyTraffic(env);
  assert.ok(await readMonthlyTraffic(env, 'mcp', MONTH) >= 7,
    'the pre-existing total is still visible where a deployment without D1 keeps it');
});
