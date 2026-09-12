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
import { testToken } from './_test-token.mjs';

// One token for the file: createEnv() hands it to the worker, the requests below
// send it back in the Authorization header.
const TOKEN = testToken('bm25-refresh');

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
    MCP_TOKEN: TOKEN,
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
      Authorization: `Bearer ${TOKEN}`,
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

// Regression (2026-09-12): the internal lesson load called fetchLessonsFromD1()
// with no filters, so its `parseInt(filters.limit, 10) || 100` fallback applied
// and search only ever saw the 100 most recently updated lessons. Production's
// own index reported docCount 100 against a 384-lesson corpus, and lessons
// outside that window were unfindable over MCP while a local search over the
// full corpus found them. These two tests fail if the limit comes back.
function createLimitedD1(rows) {
  const ordered = [...rows].sort((a, b) => String(b.updated).localeCompare(String(a.updated)));
  return {
    prepare(sql) {
      const limit = Number(/LIMIT (\d+)/.exec(sql)?.[1] || 100);
      const stmt = {
        bind() { return stmt; },
        async all() {
          return {
            results: ordered.slice(0, limit).map(r => ({ ...r, tags: JSON.stringify(r.tags || []) })),
          };
        },
        async run() { return { success: true }; },
      };
      return stmt;
    },
  };
}

// 150 lessons: the newest 100 are filler, the 3 oldest carry unique vocabulary
// that only exists below the old 100-row cut.
const NEWEST = 'zulu';
const OLDEST = 'quokka';
const MANY = [
  ...Array.from({ length: 147 }, (_, i) => ({
    id: `filler-${i}`, title: `filler lesson ${i}`, domain: 'python', status: 'published',
    tags: ['filler'], path: `lessons/core/filler-${i}.md`,
    summary: `filler body ${NEWEST}`, updated: `2026-08-${String((i % 28) + 1).padStart(2, '0')}`,
    created: 'c',
  })),
  {
    id: 'old-quokka-lesson', title: 'obscure quokka failure', domain: 'ops', status: 'published',
    tags: ['obscure'], path: 'lessons/contrib/old-quokka-lesson.md',
    summary: `the ${OLDEST} symptom only appears in this ancient note`,
    updated: '2024-01-01', created: 'c',
  },
];

function createD1Env(rows, d1 = createLimitedD1(rows)) {
  const env = createEnv([]);
  env.MISAKANET_D1 = d1;
  env._store.clear(); // start with a cold proxy cache so the D1 path is exercised
  return env;
}

// D1 stand-in that only accepts the columns it really has and only returns the
// columns a query asked for — the same way the deployed table behaves, so a lean
// SELECT cannot accidentally leak the body text a rich test depends on.
const D1_COLUMNS = ['id', 'title', 'domain', 'status', 'tags', 'path', 'summary',
                    'problem', 'root_cause', 'solution', 'verification', 'updated', 'created'];
function createColumnAwareD1(rows, { columns = D1_COLUMNS } = {}) {
  const ordered = [...rows].sort((a, b) => String(b.updated || '').localeCompare(String(a.updated || '')));
  return {
    prepare(sql) {
      const selected = (/^SELECT (.+?)\s+FROM/s.exec(sql)?.[1] || '')
        .split(',').map(c => c.trim()).filter(Boolean);
      const missing = selected.filter(c => !columns.includes(c));
      const stmt = {
        bind() { return stmt; },
        async all() {
          if (missing.length) throw new Error(`D1_ERROR: no such column: ${missing[0]}`);
          const limit = Number(/LIMIT (\d+)/.exec(sql)?.[1] || 100);
          return {
            results: ordered.slice(0, limit).map(r => {
              const out = {};
              for (const c of selected) {
                out[c] = c === 'tags' ? JSON.stringify(r.tags || []) : (r[c] ?? '');
              }
              return out;
            }),
          };
        },
        async run() { return { success: true }; },
      };
      return stmt;
    },
  };
}

// The body text lives in the D1 sections the lean projection never selected.
const BODY_ONLY = 'OOMKilled';
const RICH = [
  { id: 'rich-k8s', title: 'pod keeps restarting', domain: 'ops', status: 'published',
    tags: ['k8s'], path: 'lessons/contrib/rich-k8s.md', summary: 'a container restarts over and over',
    problem: 'the pod shows CrashLoopBackOff within a minute of starting',
    root_cause: `the container is killed as ${BODY_ONLY}; the limit is too low`,
    solution: 'raise resources.limits.memory or fix the leak', verification: 'watch the pod for an hour',
    updated: '2026-09-01', created: 'c' },
  { id: 'rich-other', title: 'unrelated lesson', domain: 'git', status: 'published',
    tags: ['git'], path: 'lessons/core/rich-other.md', summary: 'about rebasing',
    problem: 'rebase conflicts', root_cause: 'diverged branches', solution: 'rebase onto the upstream',
    verification: 'push again', updated: '2026-09-02', created: 'c' },
];

test('the internal load asks D1 for the lesson body, not just the summary', async () => {
  const env = createD1Env(RICH, createColumnAwareD1(RICH));
  const result = await refreshSearchIndex(env);
  assert.equal(result.refreshed, true, JSON.stringify(result));
  assert.equal(result.textMode, 'rich',
    'the index is built from summary-only text without the rich projection');

  const stored = await env.MISAKANET_KV.get(BM25_INDEX_KEY, 'json');
  assert.equal(stored.textMode, 'rich');

  const hit = await search(env, `${BODY_ONLY} memory limit too low`);
  assert.ok(hit.results.some(r => r.id === 'rich-k8s'),
    `root_cause text must be searchable: ${JSON.stringify(hit.results)}`);
});

test('the public lesson list keeps the lean projection', async () => {
  const env = createD1Env(RICH, createColumnAwareD1(RICH));
  const resp = await worker.fetch(new Request('https://misakanet.org/api/lessons'), env);
  assert.equal(resp.status, 200);
  const payload = await resp.json();
  const body = JSON.stringify(payload);
  assert.ok(!body.includes(BODY_ONLY),
    'the public API must not start shipping whole lesson bodies to anonymous callers');
  assert.ok(!body.includes('indexText'),
    'indexText is internal: it feeds the index and the matcher, not responses');
  const row = payload.find(r => r.id === 'rich-k8s');
  assert.equal(row.description, String(RICH[0].summary).slice(0, 400),
    'the listing keeps the summary even when the body is loaded for search');
});

test('a lean index is rebuilt once body text is available', async () => {
  const env = createD1Env(RICH, createColumnAwareD1(RICH));
  const leanIndex = buildBM25Index(RICH.map(l => ({
    id: l.id, title: l.title, domain: l.domain, tags: l.tags,
    description: String(l.summary || '').slice(0, 400),
  })), { textMode: 'lean' });
  await env.MISAKANET_KV.put(BM25_INDEX_KEY, JSON.stringify({
    ...leanIndex, built_at: new Date().toISOString(),
  }));

  const result = await refreshSearchIndex(env);
  assert.equal(result.refreshed, true,
    `a lean-text index must not be trusted once the body is available: ${JSON.stringify(result)}`);
  assert.equal(result.textMode, 'rich');
});

test('a D1 deployment without the body columns still builds an index', async () => {
  const leanColumns = D1_COLUMNS.filter(c => !['root_cause', 'solution', 'verification'].includes(c));
  const env = createD1Env(RICH, createColumnAwareD1(RICH, { columns: leanColumns }));
  const result = await refreshSearchIndex(env);
  assert.equal(result.refreshed, true,
    `the rich query must degrade instead of failing the build: ${JSON.stringify(result)}`);
  assert.equal(result.docCount, RICH.length);
  assert.equal(result.textMode, 'lean');
});

test('GET /api/search-index reports the text mode it built with', async () => {
  const env = createD1Env(RICH, createColumnAwareD1(RICH));
  await refreshSearchIndex(env);
  const resp = await worker.fetch(new Request('https://misakanet.org/api/search-index'), env);
  const data = await resp.json();
  assert.equal(data.available, true);
  assert.equal(data.textMode, 'rich');
  assert.equal(data.docCount, RICH.length);
});


test('the internal lesson load asks D1 for the whole corpus, not one page', async () => {
  const env = createD1Env(MANY);
  const result = await refreshSearchIndex(env);
  assert.equal(result.refreshed, true, JSON.stringify(result));
  assert.equal(result.docCount, MANY.length,
    'a 100-row limit silently shrank the index to the newest 100 lessons');

  const stored = await env.MISAKANET_KV.get(BM25_INDEX_KEY, 'json');
  assert.equal(stored.docCount, MANY.length);
  assert.equal(stored.docs.length, MANY.length);
});

test('a lesson outside the newest-100 window is still findable', async () => {
  const env = createD1Env(MANY);
  await refreshSearchIndex(env);

  const hit = await search(env, `${OLDEST} symptom ancient lesson`);
  assert.equal(hit.source, 'worker-bm25');
  assert.ok(hit.results.some(r => r.id === 'old-quokka-lesson'),
    `the oldest lesson must be indexed too: ${JSON.stringify(hit.results)}`);
});

test('a stored index built from a truncated corpus is rebuilt, not trusted', async () => {
  const env = createD1Env(MANY);
  // Simulate the state production was in: a "fresh" index whose docCount does
  // not match the corpus, which the age check alone would have kept for 20h.
  const stale = buildBM25Index(MANY.slice(0, 100));
  await env.MISAKANET_KV.put(BM25_INDEX_KEY, JSON.stringify({
    ...stale, built_at: new Date().toISOString(),
  }));

  const result = await refreshSearchIndex(env);
  assert.equal(result.refreshed, true, `docCount mismatch must force a rebuild: ${JSON.stringify(result)}`);
  assert.equal(result.docCount, MANY.length);
});

test('a fresh index is not rebuilt', async () => {
  const env = createEnv();
  await refreshSearchIndex(env);
  const again = await refreshSearchIndex(env);
  assert.deepEqual(again, { refreshed: false, reason: 'fresh' });
});

test('a rebuild drops the isolate-level index memo', async () => {
  // loadBM25Index memoizes the index for 5 minutes in the isolate. That memo
  // made this file's own tests disagree with each other (a search after a
  // rebuild kept seeing the previous corpus), which is exactly what a
  // docCount-triggered rebuild would do to production.
  const envA = createEnv();
  await refreshSearchIndex(envA);
  const before = await search(envA, 'pip install timeout');
  assert.ok(before.results.some(r => r.id === 'pip-timeout-mirror'), 'sanity: corpus A');

  const envB = createEnv([LESSONS[1]]); // a different corpus, same isolate
  await refreshSearchIndex(envB);
  const after = await search(envB, 'pip install timeout');
  const ids = (after.results || []).map(r => r.id);
  assert.ok(!ids.includes('pip-timeout-mirror'),
    `the rebuilt index must replace the memoized one: ${JSON.stringify(ids)}`);
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

test('the searchable text keeps a term that sits late in a section', async () => {
  // The rich projection used to slice four sections separately (problem 2000,
  // root_cause 1200, solution 1200, verification 600). The caps compounded into a
  // coverage hole: kubernetes-crashloopbackoff-debugging.md says "kubectl" four
  // times, all of them in the tail of its 1849-char Solution section, so every one
  // of them was dropped and "kubectl crashloopbackoff" could only ever match half
  // the query — the lesson lost to unrelated documents that happened to contain both
  // words (found 2026-09-12 while calibrating the coverage floor). One budget for the
  // whole body fixes it.
  const late = {
    id: 'late-term-lesson', title: 'pod keeps restarting', domain: 'ops', status: 'published',
    tags: ['ops'], path: 'lessons/contrib/late-term-lesson.md',
    summary: 'a container restarts in a loop',
    problem: 'the pod never becomes ready',
    root_cause: 'the container is killed by the runtime',
    solution: `${'filler '.repeat(300)}kubectl describe pod shows the reason`,
    verification: 'watch the pod',
    updated: '2026-09-01', created: 'c',
  };
  const env = createD1Env([late, LESSONS[1]], createColumnAwareD1([late, LESSONS[1]]));
  await refreshSearchIndex(env);

  const stored = await env.MISAKANET_KV.get(BM25_INDEX_KEY, 'json');
  assert.ok(stored.terms.kubectl, 'the late term never reached the index');

  const hit = await search(env, 'kubectl describe pod');
  assert.ok(hit.results.some(r => r.id === 'late-term-lesson'),
    `a term past the old per-section cap must still be searchable: ${JSON.stringify(hit.results)}`);
});

test('a stored index built from older searchable text is rebuilt, not trusted', async () => {
  // docCount and textMode describe *how much* and *which projection kind* — not the
  // shape of the text. When the projection rule changed (four per-section caps → one
  // budget for the body) both stayed equal, so without a text version the gate would
  // have served the old text for up to 20h.
  const env = createEnv();
  const stale = buildBM25Index(LESSONS);
  await env.MISAKANET_KV.put(BM25_INDEX_KEY, JSON.stringify({
    ...stale, built_at: new Date().toISOString(), textVersion: 1,
  }));

  const result = await refreshSearchIndex(env);
  assert.equal(result.refreshed, true,
    `a text-version change must force a rebuild: ${JSON.stringify(result)}`);
  const stored = await env.MISAKANET_KV.get(BM25_INDEX_KEY, 'json');
  assert.notEqual(stored.textVersion, 1, 'the rebuilt index must carry the current text version');
});
