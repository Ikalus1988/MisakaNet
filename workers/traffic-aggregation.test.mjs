import assert from 'node:assert/strict';
import test from 'node:test';
import { aggregateDailyTraffic } from './register-proxy-sw.js';

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

test('aggregateDailyTraffic sums daily counts into monthly keys', async () => {
  const today = new Date().toISOString().slice(0, 10);
  const month = today.slice(0, 7);
  const kv = createFakeKV({
    [`traffic:mcp:${today}`]: '100',
    [`traffic:agent:${today}`]: '50',
    [`traffic:crawler:${today}`]: '10',
    [`traffic:pageview:${today}`]: '200',
  });

  const result = await aggregateDailyTraffic({ MISAKANET_KV: kv });
  assert.equal(result.aggregated, 360);
  assert.equal(result.month, month);
  assert.equal(result.date, today);

  // Verify monthly keys were created
  assert.equal(kv._store.get(`traffic-month:mcp:${month}`), '100');
  assert.equal(kv._store.get(`traffic-month:agent:${month}`), '50');
  assert.equal(kv._store.get(`traffic-month:crawler:${month}`), '10');
  assert.equal(kv._store.get(`traffic-month:pageview:${month}`), '200');
});

test('aggregateDailyTraffic is idempotent (skips if marker exists)', async () => {
  const today = new Date().toISOString().slice(0, 10);
  const kv = createFakeKV({
    [`traffic-agg-marker:${today}`]: '1',
    [`traffic:mcp:${today}`]: '100',
  });

  const result = await aggregateDailyTraffic({ MISAKANET_KV: kv });
  assert.equal(result.skipped, true);
  assert.equal(result.date, today);
});

test('aggregateDailyTraffic accumulates with existing monthly totals', async () => {
  const today = new Date().toISOString().slice(0, 10);
  const month = today.slice(0, 7);
  const kv = createFakeKV({
    [`traffic:mcp:${today}`]: '50',
    [`traffic-month:mcp:${month}`]: '200', // existing monthly total
  });

  const result = await aggregateDailyTraffic({ MISAKANET_KV: kv });
  assert.equal(result.aggregated, 50);
  // Should accumulate: 200 + 50 = 250
  assert.equal(kv._store.get(`traffic-month:mcp:${month}`), '250');
});

test('aggregateDailyTraffic handles zero daily counts gracefully', async () => {
  const today = new Date().toISOString().slice(0, 10);
  const month = today.slice(0, 7);
  const kv = createFakeKV({});

  const result = await aggregateDailyTraffic({ MISAKANET_KV: kv });
  assert.equal(result.aggregated, 0);
  // No monthly keys should be created for zero counts
  assert.equal(kv._store.get(`traffic-month:mcp:${month}`), undefined);
});