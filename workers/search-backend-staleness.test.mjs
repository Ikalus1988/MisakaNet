// A stale BM25 index must not answer for a corpus it does not contain (2026-10-17).
//
// Measured live, after the D1 quota fallback rebuilt the index from a 192-row snapshot while the
// corpus had 501: "pip install timeout" and "permission denied" answered normally, "docker" and
// "macos" answered `no_match` — the corpus had them, the index did not. From outside that is
// indistinguishable from a knowledge gap, which is the one thing a failure-memory search must not
// fake. The same run is why the index rebuild now refuses to run from a fallback corpus.
//
// Run: node --test workers/search-backend-staleness.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import { pickSearchBackend, refreshSearchIndex, readStoredIndex } from './register-proxy-sw.js';

const QUOTA = new Error(
  "D1_ERROR: Your account has exceeded D1's free tier daily row read limit. Upgrade to a paid plan or "
  + 'wait until tomorrow (midnight UTC) to continue.',
);

function d1That(handler) {
  const stmt = { bind() { return stmt; }, all: handler, run: handler, first: handler, raw: handler };
  return { prepare() { return stmt; }, exec: handler, batch: handler };
}

const index = (docs) => ({ version: 1, built_at: new Date().toISOString(), docs: new Array(docs).fill({}), terms: {} });

test('an index covering the corpus answers', () => {
  assert.equal(pickSearchBackend(index(501), new Array(501).fill({})), 'bm25');
});

test('an index covering part of it does not', () => {
  // 192/501 = 38%: the exact shape the quota fallback produced.
  assert.equal(pickSearchBackend(index(192), new Array(501).fill({})), 'naive');
  // 90% is the line: 449 of 500 still answers, 448 does not.
  assert.equal(pickSearchBackend(index(450), new Array(500).fill({})), 'bm25');
  assert.equal(pickSearchBackend(index(449), new Array(500).fill({})), 'naive');
});

test('no index, or no corpus, degrades in the safe direction', () => {
  assert.equal(pickSearchBackend(null, new Array(501).fill({})), 'naive');
  assert.equal(pickSearchBackend(index(0), new Array(501).fill({})), 'naive');
  assert.equal(pickSearchBackend(index(10), []), 'bm25', 'an index over an unknown corpus is still usable');
});

test('a failing D1 keeps the previous index instead of rebuilding from the fallback', async () => {
  const writes = [];
  const env = {
    MISAKANET_D1: d1That(async () => { throw QUOTA; }),
  };
  // The store layer writes through `storePut`; nothing may land there on this path.
  env.MISAKANET_KV = {
    get: async () => null,
    put: async (key) => { writes.push(key); },
    delete: async () => {},
    list: async () => ({ keys: [] }),
  };
  const result = await refreshSearchIndex(env);
  assert.equal(result.refreshed, false);
  assert.match(String(result.reason), /d1 unavailable/);
  assert.deepEqual(writes.filter((k) => String(k).includes('worker_search_index')), [],
    'a rebuild must not write an index built from a fallback corpus');
  assert.equal(await readStoredIndex(env), null);
});
