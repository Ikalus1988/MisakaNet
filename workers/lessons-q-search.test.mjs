// GET /api/lessons?q= — the HTTP search surface, served by the ONE remaining search
// implementation (issue #2121).
//
// This replaces workers/d1-fts-search.test.mjs, which tested the `lessons_fts MATCH` path
// (source: "d1-fts5"). What the deletion must not lose is pinned here instead:
//
//   1. the ranking is the production one (`worker-bm25`), not a third matcher;
//   2. the rows carry the union of both old paths' fields — `description`/`rank` are the names
//      the FTS5 rows used and docs/search/index.html still reads, while `evidence_level`/`fix`/
//      `root_cause` are the fields the FTS5 rows dropped even though D1 stores them (#2080's
//      drift made user-visible on the site search page);
//   3. operator-looking input answers 200, not 502 — the contract `buildFtsMatch` existed for;
//   4. a query that matches nothing is an answer (`no_match`), not a service error;
//   5. no lesson source at all answers with a hint, not a 5xx.
//
// Run: node --test workers/lessons-q-search.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import worker, { buildBM25Index } from './register-proxy-sw.js';

const LESSONS = [
  {
    id: 'pip-timeout-ssl', title: 'pip install timeout with SSL', domain: 'python',
    status: 'published', tags: JSON.stringify(['pip', 'ssl']),
    path: 'lessons/core/pip-timeout-ssl.md',
    problem: 'pip install fails with ReadTimeoutError behind a corporate proxy',
    root_cause: 'the proxy intercepts TLS and the default timeout is too short',
    solution: 'Raise --default-timeout or use a mirror',
    summary: 'pip install times out with an SSL error',
    updated: '2026-09-01', created: '2026-08-01',
    frontmatter: JSON.stringify({ evidence_level: 'E3' }),
  },
  {
    id: 'dco-signoff', title: 'DCO sign-off failed', domain: 'git',
    status: 'published', tags: JSON.stringify(['dco']),
    path: 'lessons/core/dco-signoff.md',
    problem: 'GitHub requires DCO sign-off on commits',
    root_cause: 'the commit was amended without --signoff',
    solution: 'git reset --soft and re-commit with --signoff',
    summary: 'DCO sign-off missing on the commit',
    updated: '2026-09-02', created: '2026-08-02',
    frontmatter: JSON.stringify({ evidence_level: 'E4' }),
  },
  {
    id: 'compose-port', title: 'Docker compose port is already allocated', domain: 'devops',
    status: 'draft', tags: JSON.stringify(['docker']),
    path: 'lessons/core/compose-port.md',
    problem: 'Run docker compose up for a second project and the port bind fails',
    root_cause: 'another compose project still holds the port',
    solution: 'docker compose down the other project',
    summary: 'compose port already allocated',
    updated: '2026-09-03', created: '2026-08-03',
    frontmatter: JSON.stringify({ evidence_level: 'E1' }),
  },
];

// One index for the file: `loadBM25Index` memoizes per isolate for 5 minutes, so a second,
// different index built mid-file would be ignored and the test would assert against the wrong
// corpus.
function createEnv() {
  const index = buildBM25Index(LESSONS, { textMode: 'rich' });
  const store = new Map([
    ['worker_search_index', JSON.stringify(index)],
    ['proxy:lessons', JSON.stringify({ ts: Date.now(), data: LESSONS })],
  ]);
  return {
    MISAKANET_KV: {
      async get(key, type) {
        if (!store.has(key)) return null;
        const raw = store.get(key);
        return type === 'json' ? JSON.parse(raw) : raw;
      },
      async put(key, value) { store.set(key, value); },
      async delete(key) { store.delete(key); },
    },
  };
}

function apiSearch(query, env, extra = '') {
  return worker.fetch(
    new Request('https://misakanet.org/api/lessons?q=' + encodeURIComponent(query) + extra), env);
}

test('?q= ranks through the single production implementation', async () => {
  const resp = await apiSearch('pip install timeout', createEnv());
  assert.equal(resp.status, 200);
  const data = await resp.json();
  assert.equal(data.source, 'worker-bm25', 'the HTTP surface must be served by the kept implementation');
  assert.ok(data.results.length >= 1);
  assert.equal(data.results[0].id, 'pip-timeout-ssl');
  // Compat names the deleted FTS5 rows used — docs/search/index.html's toLocalShape reads both.
  assert.equal(typeof data.results[0].rank, 'number');
  assert.equal(typeof data.results[0].score, 'number');
  assert.ok(data.results[0].description, 'the 400-char `description` the site page renders');
});

test('the rows carry the union of both old paths\' fields (#2080 drift)', async () => {
  const resp = await apiSearch('pip install timeout', createEnv());
  const row = (await resp.json()).results[0];
  // What the FTS5 rows served:
  for (const key of ['id', 'title', 'domain', 'status', 'path', 'tags', 'description',
                     'updated', 'created', 'rank']) {
    assert.ok(key in row, `missing ${key}: ${JSON.stringify(row)}`);
  }
  // What the FTS5 rows dropped even though D1 stores them — the reason this issue exists.
  assert.equal(row.evidence_level, 'E3', JSON.stringify(row));
  assert.ok(row.problem.includes('ReadTimeoutError'));
  assert.ok(row.fix.includes('mirror'));
  assert.ok(row.root_cause.includes('TLS'));
  assert.deepEqual(row.tags, ['pip', 'ssl'], 'tags must be an array on both surfaces');
});

test('?q= combines with the domain filter', async () => {
  const resp = await worker.fetch(
    new Request('https://misakanet.org/api/lessons?q=signoff&domain=git'), createEnv());
  assert.equal(resp.status, 200);
  const data = await resp.json();
  assert.ok(data.results.length >= 1);
  assert.ok(data.results.every(r => r.domain === 'git'), JSON.stringify(data.results));
  assert.equal(data.results[0].id, 'dco-signoff');
});

test('?q= combines with the status filter', async () => {
  const resp = await worker.fetch(
    new Request('https://misakanet.org/api/lessons?q=port&status=draft'), createEnv());
  assert.equal(resp.status, 200);
  const data = await resp.json();
  assert.ok(data.results.length >= 1, JSON.stringify(data));
  assert.ok(data.results.every(r => r.status === 'draft'), JSON.stringify(data.results));
});

test('operator-looking input is a literal search, not a 502', async () => {
  // The FTS5 path needed `buildFtsMatch` (quote every term) because FTS5 reads `+ - ( ) * : ^`
  // and bare AND/OR/NOT/NEAR as syntax and answered 502 on ordinary input (measured live
  // 2026-09-29). Scoring tokens has no query syntax, so the same inputs must just answer.
  for (const query of ['C++ compiler', 'NEAR(', 'a-b:c*d^e', 'pip OR timeout', 'say "hi"']) {
    const resp = await apiSearch(query, createEnv());
    assert.equal(resp.status, 200, `"${query}" -> ${resp.status}`);
    const data = await resp.json();
    assert.ok(Array.isArray(data.results), `"${query}" -> ${JSON.stringify(data).slice(0, 120)}`);
  }
});

test('a query that matches nothing is an answer, not an error', async () => {
  const resp = await apiSearch('zzz nonexistent topic', createEnv());
  assert.equal(resp.status, 200);
  const data = await resp.json();
  assert.equal(data.results.length, 0);
  assert.equal(data.no_match, true, JSON.stringify(data));
  assert.ok(data.hint, 'no_match points at intake');
});

test('a sentence still finds its lesson (no conjunction semantics)', async () => {
  // The FTS5 path read a bare token list as "every one of these must appear", so a typed
  // sentence answered zero for a lesson that exists (measured live 2026-09-30). The kept
  // implementation scores partial matches through the relevance floor instead.
  const resp = await apiSearch('docker compose port is already allocated', createEnv());
  assert.equal(resp.status, 200);
  const data = await resp.json();
  assert.ok(data.results.some(r => r.id === 'compose-port'), JSON.stringify(data));
});

test('no lesson source at all answers with a hint, not a 5xx', async () => {
  const resp = await apiSearch('pip', {});
  assert.equal(resp.status, 200);
  const data = await resp.json();
  assert.equal(data.source, 'unavailable');
  assert.match(data.hint, /requires the lesson index/);
});
