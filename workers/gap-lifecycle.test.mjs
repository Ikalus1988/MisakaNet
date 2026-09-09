import assert from 'node:assert/strict';
import test from 'node:test';
import { cleanupCoveredGaps } from './register-proxy-sw.js';

function createFakeKV(seed = {}) {
  const store = new Map(Object.entries(seed));
  return {
    async get(key, opts) {
      if (!store.has(key)) return null;
      const raw = store.get(key);
      const type = typeof opts === 'string' ? opts : opts?.type;
      if (type === 'json') {
        try { return JSON.parse(raw); } catch { return raw; }
      }
      return raw;
    },
    async put(key, value) {
      store.set(key, value);
    },
    async delete(key) {
      store.delete(key);
    },
    _store: store,
  };
}

// Minimal BM25 index with one doc matching "dco signoff" (via bm25Tokenize expansion)
const MOCK_BM25_INDEX = {
  version: 1,
  docCount: 1,
  avgDocLen: 10,
  terms: {
    dco: { idf: 1.5, docs: [{ doc: 0, tf: 2, len: 10 }] },
    signoff: { idf: 1.2, docs: [{ doc: 0, tf: 1, len: 10 }] },
    sign: { idf: 1.0, docs: [{ doc: 0, tf: 1, len: 10 }] },
    off: { idf: 0.8, docs: [{ doc: 0, tf: 1, len: 10 }] },
  },
  docs: [{ id: 'dco-signoff-force-push-pitfall', title: 'DCO Signoff Force Push Pitfall', domain: 'git', path: 'lessons/core/dco-signoff-force-push-pitfall.md' }],
};

// Note: loadBM25Index has a 5-min global cache. Tests run sequentially; the first
// test that loads the index will cache it. We test "no BM25 index" via empty gap
// index (short-circuits before loadBM25Index), and test matching with a fresh KV
// that has the index key.

test('cleanupCoveredGaps does nothing when gap index is empty', async () => {
  const kv = createFakeKV({
    'gap:index': JSON.stringify([]),
  });

  const result = await cleanupCoveredGaps({ MISAKANET_KV: kv });
  assert.equal(result.cleaned, 0);
});

test('cleanupCoveredGaps removes gaps that now have matching lessons', async () => {
  const kv = createFakeKV({
    'gap:index': JSON.stringify(['gap:dco sign-off', 'gap:unrelated topic']),
    'gap:dco sign-off': JSON.stringify({ query: 'dco sign-off', count: 3 }),
    'gap:unrelated topic': JSON.stringify({ query: 'unrelated topic', count: 1 }),
    'worker_search_index': JSON.stringify(MOCK_BM25_INDEX),
  });

  const result = await cleanupCoveredGaps({ MISAKANET_KV: kv });
  assert.equal(result.cleaned, 1);
  assert.equal(result.remaining, 1);
  assert.equal(result.details[0].query, 'dco sign-off');
  // Gap key for matched query should be deleted
  assert.equal(kv._store.has('gap:dco sign-off'), false);
  // Gap key for unmatched query should remain
  assert.equal(kv._store.has('gap:unrelated topic'), true);
  // Index should be updated
  const newIndex = JSON.parse(kv._store.get('gap:index'));
  assert.deepEqual(newIndex, ['gap:unrelated topic']);
});