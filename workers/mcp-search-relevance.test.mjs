// Relevance-floor tests (#1527 orientation, 2026-09-12).
//
// Ranking without a floor means every query gets "the least bad" N lessons, so an
// external agent asking about something the corpus has never seen got unrelated
// hits instead of the honest no_match → intake path. That was measured on a real
// external failure surface: `misakanet_search("VISION_API_KEY env var not set")`
// answered with `user-agent-identify-bots`.
//
// These tests drive the BM25 path (worker-bm25) — the one production uses — by
// seeding a worker_search_index, and assert both directions: junk falls through to
// no_match, real queries still find their lesson.
//
// Run: node --test workers/mcp-search-relevance.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import worker from './register-proxy-sw.js';
import { testToken } from './_test-token.mjs';

const TOKEN = testToken('relevance-floor');

// 24 synthetic docs. "hook"/"api" are corpus-ubiquitous (df 24 and 20 → not
// discriminating); "pip"/"timeout"/"dco"/"signoff" are distinctive (df ≤ 3).
function buildIndex() {
  const docs = [];
  const terms = new Map();
  const add = (term, doc, tf = 1) => {
    if (!terms.has(term)) terms.set(term, { idf: 1, docs: [] });
    terms.get(term).docs.push({ doc, tf, len: 20 });
  };
  const titles = [];
  for (let i = 0; i < 24; i++) {
    titles.push({ id: `filler-${i}`, title: `hook api error ${i}`, domain: 'ops', path: `lessons/contrib/filler-${i}.md` });
  }
  titles[0] = { id: 'pip-timeout-mirror', title: 'pip install timeout', domain: 'python', path: 'lessons/core/pip-timeout-mirror.md' };
  titles[20] = { id: 'dco-signoff', title: 'DCO sign-off failed', domain: 'git', path: 'lessons/core/dco-signoff.md' };
  titles[21] = { id: 'dco-signoff-fix', title: 'DCO signoff checklist', domain: 'git', path: 'lessons/core/dco-signoff-fix.md' };
  titles.forEach((doc, i) => docs.push(doc));

  // ubiquitous terms
  docs.forEach((_, i) => add('hook', i));
  docs.forEach((_, i) => { if (i !== 3 && i !== 7 && i !== 11 && i !== 15) add('api', i); });
  // distinctive terms
  add('pip', 0, 3); add('install', 0, 2); add('timeout', 0, 2);
  add('dco', 20); add('dco', 21); add('signoff', 20); add('signoff', 21);

  const termObject = {};
  for (const [term, data] of terms) termObject[term] = data;
  return { version: 1, docCount: docs.length, avgDocLen: 20, terms: termObject, docs };
}

function createEnv() {
  const index = buildIndex();
  // The handler loads lessons before it ranks (FAQ, gap logging, fallback), so the
  // cache has to exist too — otherwise it returns "Failed to load lessons" and the
  // test would pass/fail for the wrong reason.
  const lessons = index.docs.map((doc, i) => ({
    ...doc,
    description: doc.title,
    tags: doc.domain === 'python' ? ['pip', 'network'] : ['git'],
    status: 'published',
  }));
  // The `pip-timeout-mirror` record is D1-shaped on purpose (issue #1675): D1 carries
  // the real Problem/Fix sections in `problem`/`solution`, stores `tags` as a JSON
  // *string*, has `updated` for freshness, and its rows carry the internal
  // `indexText`/`textMode` fields that must never reach a response.
  Object.assign(lessons.find(l => l.id === 'pip-timeout-mirror'), {
    problem: 'pip install times out behind a corporate proxy before the package is fetched',
    solution: 'Raise --default-timeout or use a mirror',
    tags: JSON.stringify(['pip', 'network']),
    updated: new Date().toISOString(),
    indexText: 'pip install timeout internal searchable body used to build the index',
    textMode: 'rich',
  });
  const store = new Map([
    ['worker_search_index', JSON.stringify(index)],
    ['proxy:lessons', JSON.stringify({ ts: Date.now(), data: lessons })],
  ]);
  return {
    MCP_TOKEN: TOKEN,
    MCP_VERSION: 'relevance-floor-test',
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

function searchRequest(query, args = {}) {
  return new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${TOKEN}`,
      'Content-Type': 'application/json',
      'MCP-Protocol-Version': '2025-06-18',
      'CF-Connecting-IP': '198.51.100.' + (Math.floor(Math.random() * 200) + 1),
    },
    body: JSON.stringify({
      jsonrpc: '2.0', id: 1, method: 'tools/call',
      params: { name: 'misakanet_search', arguments: { query, ...args } },
    }),
  });
}

async function search(query, args = {}) {
  const resp = await worker.fetch(searchRequest(query, args), createEnv());
  assert.equal(resp.status, 200);
  const body = await resp.json();
  assert.equal(body.error, undefined, JSON.stringify(body.error));
  return JSON.parse(body.result.content[0].text);
}

test('the BM25 index path is the one under test', async () => {
  const result = await search('pip install timeout');
  assert.equal(result.source, 'worker-bm25', 'test must exercise the production path');
});

test('a real query still finds its lesson', async () => {
  const result = await search('pip install timeout');
  assert.equal(result.no_match, undefined);
  assert.ok(result.results.length >= 1);
  assert.equal(result.results[0].id, 'pip-timeout-mirror');
});

test('a query of corpus-ubiquitous words returns no_match instead of the least-bad docs', async () => {
  // "hook api" appears in nearly every doc: matching it means nothing. Before the
  // floor this returned filler lessons; now it is an honest miss with intake guidance.
  const result = await search('hook api');
  assert.equal(result.no_match, true, JSON.stringify(result.results));
  assert.deepEqual(result.results, []);
  assert.match(result.suggestion, /misakanet_submit_intake/);
  assert.equal(result.intake.args.error, 'hook api');
});

test('a query whose distinctive words are absent returns no_match', async () => {
  // The measured external case: nothing in the corpus is about this, and the only
  // overlapping words are ubiquitous ones.
  const result = await search('visionkey hook api');
  assert.equal(result.no_match, true, JSON.stringify(result.results));
  assert.deepEqual(result.results, []);
});

test('a mixed query still reaches the distinctive lesson', async () => {
  // Two ubiquitous words plus two distinctive ones must not be thrown away with
  // the junk: the floor is "at least one informative term", not "all terms".
  const result = await search('hook api dco signoff');
  assert.equal(result.no_match, undefined);
  const ids = result.results.map(r => r.id);
  assert.ok(ids.includes('dco-signoff'), JSON.stringify(ids));
  assert.ok(!ids.some(id => id.startsWith('filler-')), `filler leaked in: ${JSON.stringify(ids)}`);
});

test('a single distinctive word is enough for a one-word query', async () => {
  const result = await search('timeout');
  assert.equal(result.no_match, undefined);
  assert.equal(result.results[0].id, 'pip-timeout-mirror');
});

test('a single ubiquitous word is not', async () => {
  const result = await search('hook');
  assert.equal(result.no_match, true, JSON.stringify(result.results));
});

// ── lesson hits must carry content, not just an id (issue #1675) ──────────────
// The BM25 branch projects hits from the index, which stores only
// {id, title, domain, path, len}. Before the enrichment step every lesson hit
// therefore arrived with an empty `problem`, `fix`, `tags`, `evidence_level` and
// `freshness` — 35 of 35 sampled hits on 2026-09-13 — so an agent could not tell
// whether a hit was relevant without calling misakanet_get_lesson for each one.

test('a lesson hit carries a non-empty problem at the default detail', async () => {
  const result = await search('pip install timeout');
  const hit = result.results[0];
  assert.equal(hit.id, 'pip-timeout-mirror');
  assert.ok(hit.problem && hit.problem.length > 0, `problem was empty: ${JSON.stringify(hit)}`);
  assert.match(hit.problem, /times out behind a corporate proxy/);
  assert.notEqual(hit.title, hit.id, 'title must be the human title, not the slug');
  assert.notEqual(hit.freshness, 'unknown', 'the record has `updated`, so freshness must resolve');
});

test('detail=summary carries fix and array tags from a D1-shaped record', async () => {
  const result = await search('pip install timeout', { detail: 'summary' });
  const hit = result.results[0];
  assert.equal(hit.domain, 'python');
  assert.equal(hit.fix, 'Raise --default-timeout or use a mirror', 'fix must come from D1 `solution`');
  assert.deepEqual(hit.tags, ['pip', 'network'], 'sqlite stores tags as a JSON string; results must not');
});

test('enrichment never leaks the internal searchable body', async () => {
  for (const detail of ['compact', 'summary', 'full']) {
    const result = await search('pip install timeout', { detail });
    const hit = result.results[0];
    assert.equal(hit.indexText, undefined, `indexText leaked at detail=${detail}`);
    assert.equal(hit.textMode, undefined, `textMode leaked at detail=${detail}`);
  }
});

test('every returned lesson hit has a non-empty problem (the AC of #1675)', async () => {
  const queries = ['pip install timeout', 'hook api dco signoff', 'timeout'];
  for (const query of queries) {
    const result = await search(query, { detail: 'summary' });
    for (const hit of result.results) {
      assert.ok(hit.problem && hit.problem.length > 0,
        `empty problem for ${hit.id} on ${JSON.stringify(query)}: ${JSON.stringify(hit)}`);
    }
  }
});
