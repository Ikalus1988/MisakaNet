// A `status: superseded` lesson must never outrank a live one (2026-11-06).
//
// The defect this pins was measured on the real corpus: `misakanet_search("docker compose port is
// already allocated")` answered with `ruby-require-relative-and-docker-port-allocation` — a lesson
// whose body opens with "CORRECTION (this lesson is `status: superseded`; do not follow its Ruby
// steps)" — at rank 1 (14.5), with the replacement at rank 2 (13.9). The ranker is what put the
// refusal first, so the ranker is what this file tests, on both matchers (BM25 and the naive
// fallback), not on a copied ordering rule.
//
// Run: node --test workers/superseded-rank.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import worker, { refreshSearchIndex, invalidateBM25Memo } from './register-proxy-sw.js';
import { testToken } from './_test-token.mjs';

const TOKEN = testToken('superseded-rank');

// 24 documents. `hook`/`api` are ubiquitous (df 24 → not discriminating); the port vocabulary is
// rare (df 2), which is what makes it informative to the relevance floor. The retired document is
// written to win the *ranking* — its title carries two query terms and its body repeats the exact
// phrase three times — so a test that passes because it never won in the first place cannot pass.
const FILLER = Array.from({ length: 22 }, (_, i) => ({
  id: `filler-${i}`,
  title: `hook api error ${i}`,
  domain: 'ops',
  status: 'published',
  path: `lessons/contrib/filler-${i}.md`,
  indexText: 'hook api generic error troubleshooting checklist',
}));

const LIVE = {
  id: 'port-live',
  title: 'A port that is already allocated is held by a live process',
  domain: 'docker',
  status: 'published',
  path: 'lessons/contrib/port-live.md',
  indexText: 'docker compose port is already allocated: the bind failure belongs to the kernel; '
    + 'name the holder with ss, lsof or fuser, stop it, then retry.',
};

const RETIRED = {
  id: 'port-retired',
  title: 'Docker Port Allocation and Ruby Path Resolution',
  domain: 'devops',
  status: 'superseded',
  path: 'lessons/en/port-retired.md',
  indexText: 'docker compose port is already allocated. '
    + 'docker compose port is already allocated. '
    + 'docker compose port is already allocated. '
    + 'ruby require_relative loaderror quantum frobnicator desync.',
};

const LESSONS = [...FILLER, LIVE, RETIRED];

function createEnv(lessons = LESSONS) {
  const store = new Map([['proxy:lessons', JSON.stringify({ ts: Date.now(), data: lessons })]]);
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

async function search(env, query, top = 5) {
  const request = new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${TOKEN}`,
      'Content-Type': 'application/json',
      'MCP-Protocol-Version': '2025-06-18',
      'CF-Connecting-IP': '198.51.100.' + (Math.floor(Math.random() * 200) + 1),
    },
    body: JSON.stringify({
      jsonrpc: '2.0', id: 1, method: 'tools/call',
      params: { name: 'misakanet_search', arguments: { query, top } },
    }),
  });
  const resp = await worker.fetch(request, env);
  const body = await resp.json();
  assert.equal(body.error, undefined, JSON.stringify(body.error));
  return JSON.parse(body.result.content[0].text);
}

const QUERY = 'docker compose port is already allocated';

test('the fixture ranks the superseded lesson first before the rule is applied', async () => {
  // Guard for the test itself: if this stops being true, the assertions below would pass without
  // exercising anything. Scores are read from the worker's own index (same k1/b/idf the ranker
  // uses) and summed over the query terms, which is the part the demotion reorders.
  const { buildBM25Index, bm25Tokenize } = await import('./register-proxy-sw.js');
  const index = buildBM25Index(LESSONS);
  assert.ok(index.terms.port, 'fixture must index the port vocabulary');
  const { k1, b, avgDocLen, terms, docs } = index;
  const docIndex = (id) => docs.findIndex((d) => d.id === id);
  const score = (id) => bm25Tokenize(QUERY).reduce((total, term) => {
    const entry = terms[term]?.docs.find((e) => e.doc === docIndex(id));
    if (!entry) return total;
    const norm = 1 - b + b * (entry.len / avgDocLen);
    return total + terms[term].idf * ((entry.tf * (k1 + 1)) / (entry.tf + k1 * norm));
  }, 0);
  assert.ok(score('port-retired') > score('port-live'),
    `fixture no longer reproduces the defect: retired=${score('port-retired')} live=${score('port-live')}`);
});

test('BM25 search keeps the superseded lesson below every live match', async () => {
  const env = createEnv();
  const refreshed = await refreshSearchIndex(env);
  assert.equal(refreshed.refreshed, true, JSON.stringify(refreshed));
  const { results } = await search(env, QUERY, 5);
  const ids = results.map((r) => r.id);
  assert.ok(ids.includes('port-live'), `live replacement missing from ${ids}`);
  assert.equal(ids[0], 'port-live', `superseded lesson still ranked first: ${ids}`);
  assert.ok(ids.indexOf('port-retired') > ids.indexOf('port-live') || !ids.includes('port-retired'),
    `superseded row must not precede a live row: ${ids}`);
});

test('the naive fallback applies the same rule', async () => {
  // No index is built: the handler must fall back to `searchLessons`, which reads `status` off the
  // lesson record instead of the index docs. Both matchers are user-facing, so both are tested.
  // The memo is module-scoped and an earlier test published an index, so clear it first — otherwise
  // this measures the BM25 path again and passes for the wrong reason.
  invalidateBM25Memo();
  const env = createEnv();
  const { results, source } = await search(env, QUERY, 5);
  assert.equal(source, 'worker-search');
  const ids = results.map((r) => r.id);
  assert.equal(ids[0], 'port-live', `superseded lesson still ranked first: ${ids}`);
});

test('a superseded lesson still answers when it is the only match', async () => {
  // The rule is a demotion, not a filter: an old error whose only write-up was superseded must
  // still reach the reader (with its correction), otherwise the fix trades a bad answer for none.
  const env = createEnv([...FILLER, { ...RETIRED, status: 'superseded' }]);
  await refreshSearchIndex(env);
  const { results } = await search(env, 'ruby require_relative loaderror', 5);
  assert.ok(results.length >= 1, 'a lone superseded match must not become no_match');
  assert.equal(results[0].id, 'port-retired');
  assert.equal(results[0].status, 'superseded', 'the correction has to travel with the row');
});

test('a `?status=superseded` filter still returns superseded rows', async () => {
  // The web API filters by exact status before the top-N slice (#2121); the demotion must not
  // turn that into an empty answer for the one surface that asks for superseded lessons.
  const env = createEnv([...FILLER, { ...RETIRED, status: 'superseded' }]);
  await refreshSearchIndex(env);
  const resp = await worker.fetch(new Request(
    'https://misakanet.org/api/lessons?q=docker%20compose%20port%20is%20already%20allocated&status=superseded'),
  env);
  const body = await resp.json();
  const ids = (body.results || body.data || []).map((r) => r.id);
  assert.ok(ids.includes('port-retired'), `status filter lost its row: ${JSON.stringify(body).slice(0, 200)}`);
});
