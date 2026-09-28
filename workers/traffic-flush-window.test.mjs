// A cold isolate must not flush the traffic buffer on its first request (2026-09-22, #1890).
//
// `trafficFlushedAt` started at 0, so `Date.now() - trafficFlushedAt > TRAFFIC_FLUSH_MS` was true on
// the very first request of every isolate: a buffer holding one count was flushed immediately, one KV
// `get` + one `put` per cold start. Against the live namespace that is ~1,300 puts/day to four key
// names — the largest single line in the account's write series — while the family panel presented it
// as "1,342 distinct keys" and issue #1890 was read as "there are 1,000+ different keys".
//
// This lives in its own file on purpose: the buffer and the flush clock are module state, so in a file
// that has already made requests the first-request property cannot be observed at all.
//
// Run: node --test workers/traffic-flush-window.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import worker from './register-proxy-sw.js';
import { testToken } from './_test-token.mjs';

const TOKEN = testToken('traffic-flush-window');

test('the first request of a fresh isolate writes no traffic counter', async () => {
  const store = new Map();
  const puts = [];
  const env = {
    MCP_TOKEN: TOKEN,
    REGISTER_TOKEN: TOKEN,
    MISAKANET_KV: {
      async get(key) { return store.has(key) ? store.get(key) : null; },
      async put(key, value) { puts.push(key); store.set(key, value); },
      async delete(key) { store.delete(key); },
    },
  };

  const response = await worker.fetch(new Request('https://misakanet.org/api/health'), env);
  assert.equal(response.status, 200);

  const trafficWrites = puts.filter(
    (k) => k.startsWith('traffic:') || k.startsWith('counters:traffic:'));
  assert.deepEqual(trafficWrites, [],
    `one request flushed the traffic buffer; the window must start at module load. All writes: ${puts}`);
});
