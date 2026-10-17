// A failing D1 must not turn a thin corpus into a thin index (2026-10-17).
//
// Measured: after the quota fallback served a 192-row snapshot, `refreshSearchIndex` rebuilt the stored
// index from it — `/api/search-index` then reported `docCount: 192, textMode: "lean"` against a 501-row
// corpus, and `docker` / `macos` answered `no_match` for lessons the corpus contained. From outside that
// is indistinguishable from a knowledge gap, which a failure-memory search must never fake.
//
// Run: node --test workers/index-rebuild-guard.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import { readStoredIndex, refreshSearchIndex } from './register-proxy-sw.js';

const QUOTA = new Error(
  "D1_ERROR: Your account has exceeded D1's free tier daily row read limit. Upgrade to a paid plan or "
  + 'wait until tomorrow (midnight UTC) to continue.',
);

const refusingD1 = () => {
  const refused = async () => { throw QUOTA; };
  const stmt = { bind() { return stmt; }, all: refused, run: refused, first: refused, raw: refused };
  return { prepare() { return stmt; }, exec: refused, batch: refused };
};

test('a bound-but-failing D1 keeps the previous index instead of rebuilding from the fallback', async () => {
  const writes = [];
  const env = {
    MISAKANET_D1: refusingD1(),
    MISAKANET_KV: {
      get: async () => null,
      put: async (key) => { writes.push(String(key)); },
      delete: async () => {},
      list: async () => ({ keys: [] }),
    },
  };
  const result = await refreshSearchIndex(env);
  assert.equal(result.refreshed, false);
  assert.match(String(result.reason), /d1 unavailable/);
  assert.deepEqual(writes.filter((k) => k.includes('worker_search_index')), [],
    'an index built from a fallback corpus must not be written');
  assert.equal(await readStoredIndex(env), null);
});

test('no D1 binding at all still builds from the snapshot (the case that never had an index)', async () => {
  const realFetch = globalThis.fetch;
  const rows = [{ id: 'a', title: 'pip install timeout', domain: 'python', tags: ['pip'], summary: 'pip times out' }];
  globalThis.fetch = async (url) => {
    // Without D1 the corpus comes from the GitHub proxy (`fetchFromGitHub` → contents API); answer that
    // shape, which is what this path has always read.
    assert.match(String(url), /contents\/lessons\.json/, 'the corpus in this case is the repo snapshot');
    return new Response(JSON.stringify({ content: Buffer.from(JSON.stringify(rows)).toString('base64'), encoding: 'base64' }),
      { status: 200, headers: { 'Content-Type': 'application/json' } });
  };
  try {
    const env = { MISAKANET_KV: { get: async (k) => store.get(k) ?? null, put: async (k, v) => { store.set(k, v); }, delete: async () => {}, list: async () => ({ keys: [] }) } };
    const store = new Map();
    const result = await refreshSearchIndex(env);
    assert.equal(result.refreshed, true, JSON.stringify(result));
    const index = await readStoredIndex(env);
    assert.ok(index && index.docs && index.docs.length === 1, 'the snapshot became the index');
  } finally {
    globalThis.fetch = realFetch;
  }
});
