// The BM25 index must be maintained without a human or a secret (#1622 follow-up,
// 2026-09-12).
//
// Production reported `GET /api/search-index` → {"available": false}: the index was
// supposed to arrive via scripts/build_worker_index.py + POST /api/search-index with
// an X-Sync-Token, but no workflow ran either script and the repo has no SYNC_TOKEN
// secret — so every search fell back to the naive matcher, which is why external
// queries got unrelated lessons. These tests pin the replacement: the worker builds
// the index itself in its cron, and once it exists, search actually uses it.
//
// Run: node --test workers/bm25-index-refresh.test.mjs
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import worker, { buildBM25Index, refreshSearchIndex, BM25_INDEX_KEY } from './register-proxy-sw.js';

const LESSONS = [
  { id: 'pip-timeout-mirror', title: 'pip install timeout', domain: 'python', tags: ['pip', 'network'],
    path: 'lessons/core/pip-timeout-mirror.md',
    summary: 'pip install times out on slow networks; use a mirror.',
    preview: 'Set index-url to a mirror and raise the timeout when the corporate proxy is slow.' },
  { id: 'dco-signoff', title: 'DCO sign-off failed', domain: 'git', tags: ['github', 'dco'],
    path: 'lessons/core/dco-signoff.md',
    summary: 'GitHub requires DCO sign-off on commits.',
    preview: 'A missing Signed-off-by trailer makes the DCO check fail and block the merge.' },
  { id: 'k8s-137', title: 'Kubernetes CrashLoopBackOff debugging', domain: 'ops', tags: ['k8s'],
    path: 'lessons/contrib/k8s-137.md',
    summary: 'Container terminates with exit code 137 under memory pressure.',
    preview: 'kubectl describe shows OOMKilled; raise the memory limit or fix the leak.' },
];

function createEnv(lessons = LESSONS) {
  const store = new Map([
    ['proxy:lessons', JSON.stringify({ ts: Date.now(), data: lessons })],
  ]);
  return {
    MCP_TOKEN: 'bm25-refresh-test-token',
    MISAKANET_KV: {
      async get(key, type) {
        if (!store.has(key)) return null;
        const raw = store.get(key);
        return type === 'json' ? JSON.parse(raw) : raw;
      },
      async put(key, value) { store.set(key, value); },
      async delete(key) { store.delete(key); },
    },
    _store: store,
  };
}

function searchRequest(query) {
  return new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers: {
      Authorization: 'Bearer bm25-refresh-test-token',
      'Content-Type': 'application/json',
      'MCP-Protocol-Version': '2025-06-18',
      'CF-Connecting-IP': '198.51.100.' + (Math.floor(Math.random() * 200) + 1),
    },
    body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'tools/call',
      params: { name: 'misakanet_search', arguments: { query, top: 3 } } }),
  });
}

async function search(env, query) {
  const resp = await worker.fetch(searchRequest(query), env);
  const body = await resp.json();
  assert.equal(body.error, undefined, JSON.stringify(body.error));
  return JSON.parse(body.result.content[0].text);
}

test('production starts without an index — the state this fixes', async () => {
  const env = createEnv();
  const result = await search(env, 'pip install timeout');
  assert.equal(result.source, 'worker-search', 'the naive fallback is the pre-cron state');
  assert.equal(await env.MISAKANET_KV.get(BM25_INDEX_KEY, 'json'), null);
});

test('the refresh builds and stores a usable index', async () => {
  const env = createEnv();
  const first = await refreshSearchIndex(env);
  assert.equal(first.refreshed, true, JSON.stringify(first));
  assert.equal(first.docCount, LESSONS.length);

  const stored = await env.MISAKANET_KV.get(BM25_INDEX_KEY, 'json');
  assert.equal(stored.version, 1);
  assert.equal(stored.docCount, LESSONS.length);
  assert.ok(stored.built_at, 'built_at makes the next refresh a no-op until it is old');
  assert.equal(stored.docs.length, LESSONS.length);
  // The search contract: terms carry df/idf and per-doc postings.
  const timeout = stored.terms.timeout;
  assert.ok(timeout && timeout.df >= 1 && typeof timeout.idf === 'number');
  assert.ok(timeout.docs[0].doc >= 0 && timeout.docs[0].tf >= 1 && timeout.docs[0].len > 0);
});

test('once built, search uses the BM25 path', async () => {
  const env = createEnv();
  await refreshSearchIndex(env);

  const result = await search(env, 'pip install timeout');
  assert.equal(result.source, 'worker-bm25', 'the cron-built index must be what search uses');
  assert.equal(result.results[0].id, 'pip-timeout-mirror');

  const bodyQuery = await search(env, 'kubectl oomkilled memory limit');
  assert.equal(bodyQuery.source, 'worker-bm25');
  assert.ok(bodyQuery.results.some(r => r.id === 'k8s-137'),
    `body-only text must be findable: ${JSON.stringify(bodyQuery.results)}`);
});

test('a fresh index is not rebuilt', async () => {
  const env = createEnv();
  await refreshSearchIndex(env);
  const again = await refreshSearchIndex(env);
  assert.deepEqual(again, { refreshed: false, reason: 'fresh' });
});

test('an empty corpus is not turned into an empty index', async () => {
  const env = createEnv([]);
  const result = await refreshSearchIndex(env);
  assert.equal(result.refreshed, false);
  assert.equal(result.reason, 'no lessons');
  assert.equal(await env.MISAKANET_KV.get(BM25_INDEX_KEY, 'json'), null);
});

test('the real corpus builds an index that fits KV', async () => {
  const raw = JSON.parse(readFileSync(new URL('../data/lessons.json', import.meta.url), 'utf8'));
  const index = buildBM25Index(raw);
  assert.equal(index.docCount, raw.length);
  assert.ok(Object.keys(index.terms).length > 1000, 'expected a real vocabulary');
  assert.ok(index.avgDocLen > 0);
  const bytes = Buffer.byteLength(JSON.stringify(index));
  // Cloudflare KV caps a value at 25 MiB; leave room for growth.
  assert.ok(bytes < 20 * 1024 * 1024, `index is ${(bytes / 1048576).toFixed(1)} MB`);
  console.log(`# BM25 index over the real corpus: ${index.docCount} docs, ` +
              `${Object.keys(index.terms).length} terms, ${(bytes / 1048576).toFixed(1)} MB`);
});
