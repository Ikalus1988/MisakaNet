// Which search implementation answered (#2121) — observability only, no ranking change.
//
// Two implementations serve the same queries: the BM25 index (built from the rich D1 projection) and the
// naive matcher over the same rows when that index is unavailable. They rank differently, and before this
// counter there was no way from outside the worker to say which one produced a given answer — so "search
// gave me bad results" could not be attributed, and the question #2121 asks ("which of the two should be
// deleted?") had no data behind it.
//
// What this file pins: a search records exactly one backend, the two branches are distinguishable, and the
// counter costs no extra write per query (it rides the traffic buffer).
//
// Run: node --test workers/search-backend-attribution.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import worker, {
  refreshSearchIndex, TRAFFIC_FLUSH_BATCH, SEARCH_BACKEND_BUCKET_PREFIX, SEARCH_BACKENDS,
} from './register-proxy-sw.js';
import { testToken } from './_test-token.mjs';

const TOKEN = testToken('search-backend');

const LESSONS = [
  { id: 'pip-timeout-mirror', title: 'pip install timeout', domain: 'python', tags: ['pip'],
    path: 'lessons/core/pip-timeout-mirror.md', summary: 'pip install times out on slow networks.',
    preview: 'Set index-url to a mirror and raise the timeout when the corporate proxy is slow.' },
  { id: 'k8s-137', title: 'Kubernetes CrashLoopBackOff', domain: 'ops', tags: ['k8s'],
    path: 'lessons/contrib/k8s-137.md', summary: 'Container exits with code 137 under memory pressure.',
    preview: 'kubectl describe shows OOMKilled; raise the memory limit or fix the leak.' },
];

function createEnv() {
  const store = new Map([['proxy:lessons', JSON.stringify({ ts: Date.now(), data: LESSONS })]]);
  return {
    MCP_TOKEN: TOKEN,
    MISAKANET_KV: {
      async get(key, type) { return store.has(key) ? (type === 'json' ? JSON.parse(store.get(key)) : store.get(key)) : null; },
      async put(key, value) { store.set(key, String(value)); },
      async delete(key) { store.delete(key); },
    },
    _store: store,
  };
}

function searchRequest(query) {
  return new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers: { Authorization: `Bearer ${TOKEN}`, 'Content-Type': 'application/json',
               'MCP-Protocol-Version': '2025-06-18',
               'CF-Connecting-IP': `198.51.100.${Math.floor(Math.random() * 200) + 1}` },
    body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'tools/call',
      params: { name: 'misakanet_search', arguments: { query, top: 2 } } }),
  });
}

function buckets(env) {
  return [...env._store.keys()].filter(k => k.includes(`traffic:${SEARCH_BACKEND_BUCKET_PREFIX}`));
}

/** `{backend: count}` straight out of the KV fallback the counter writes to. */
function counts(env) {
  const out = {};
  for (const key of buckets(env)) {
    const name = key.split(SEARCH_BACKEND_BUCKET_PREFIX)[1].split(':')[0];
    out[name] = (out[name] || 0) + Number(env._store.get(key) || 0);
  }
  return out;
}

const countFor = (env, backend) => counts(env)[backend] || 0;

async function searchTimes(env, n, query = 'pip install timeout') {
  for (let i = 0; i < n; i += 1) {
    const resp = await worker.fetch(searchRequest(query), env);
    assert.equal(resp.status, 200);
  }
}

test('a search with no index is recorded as the fallback', async () => {
  const env = createEnv();
  await searchTimes(env, TRAFFIC_FLUSH_BATCH);
  const found = buckets(env);
  assert.ok(found.some(k => k.includes('searchbackend:fallback')), found.join(', '));
  assert.ok(!found.some(k => k.includes('searchbackend:bm25')), `no BM25 build happened: ${found}`);
});

test('a search with an index is recorded as bm25', async () => {
  const env = createEnv();
  await refreshSearchIndex(env);           // publishes the index into the durable store
  await searchTimes(env, TRAFFIC_FLUSH_BATCH);
  const found = buckets(env);
  assert.ok(found.some(k => k.includes('searchbackend:bm25')), found.join(', '));
  assert.ok(countFor(env, 'bm25') >= TRAFFIC_FLUSH_BATCH / 2,
    `most of the batch should be bm25: ${JSON.stringify(counts(env))}`);
});

test('every search is attributed exactly once, to one of the two backends', async () => {
  // The invariant that matters: no search is unattributed and none is double-counted. Asserting the
  // *split* instead would encode an implementation accident (the index memo is per isolate, and the
  // traffic buffer flushes on a timer as well as on size, so the first search of a process may take
  // either branch).
  const env = createEnv();
  await refreshSearchIndex(env);
  const n = TRAFFIC_FLUSH_BATCH * 2;
  await searchTimes(env, n);
  const total = SEARCH_BACKENDS.reduce((sum, b) => sum + countFor(env, b), 0);
  // The buffer holds a tail until the next flush (size *or* timer), so "attributed == n" is only true
  // once the process has stopped searching. What must hold: nothing is over-counted, and the gap is
  // smaller than one batch — i.e. the counts are buffered, not dropped.
  assert.ok(total <= n, `over-counted: ${total} > ${n}`);
  assert.ok(n - total < TRAFFIC_FLUSH_BATCH,
    `attributed ${total} of ${n} with a tail larger than one batch: ${JSON.stringify(counts(env))}`);
  for (const key of Object.keys(counts(env))) {
    assert.ok(SEARCH_BACKENDS.includes(key), `unknown backend recorded: ${key}`);
  }
});

test('the endpoint reports the split once an index exists', async () => {
  const env = createEnv();
  await refreshSearchIndex(env);
  await searchTimes(env, TRAFFIC_FLUSH_BATCH);
  const body = await (await worker.fetch(new Request('https://misakanet.org/api/search-index'), env)).json();
  assert.equal(body.available, true, JSON.stringify(body).slice(0, 200));
  // Without a D1 binding the enumeration cannot run, so the honest answer is an empty map — the keys are
  // still present so a reader can tell "no data" from "old deploy".
  assert.deepEqual(body.servedBy, {}, `no D1 binding, so no enumeration: ${JSON.stringify(body.servedBy)}`);
  assert.deepEqual(SEARCH_BACKENDS, ['bm25', 'fallback'], 'the export the endpoint enumerates moved');
});

test('the counter rides the traffic buffer instead of writing per query', async () => {
  // One write per query is what exhausted the free tier before (#1890). The buffer also flushes on a timer,
  // so the assertable property is "far fewer writes than queries", not "no write at all".
  const env = createEnv();
  const n = TRAFFIC_FLUSH_BATCH * 3;
  await searchTimes(env, n);
  assert.ok(buckets(env).length <= 2, `a per-query write slipped back in: ${buckets(env)}`);
});
