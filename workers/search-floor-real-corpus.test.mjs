// Search quality against the REAL corpus (2026-09-12).
//
// The existing relevance tests build a handful of synthetic documents, which is why
// the defect they were supposed to prevent went unnoticed: with 389 real lessons, the
// floor admitted documents that matched one corpus-wide word, so
// `how do I bake sourdough bread` returned five lessons and
// `VISION_API_KEY env var not set` returned five unrelated ones with the lesson that
// actually mentions that variable ranked ninth. An adversarial review found both in
// production and pointed out that no test ran against the real corpus at all.
//
// These cases are calibrated, not cherry-picked: the positives are queries that must
// keep finding their lesson (recall), the negatives are queries the corpus genuinely
// cannot answer (precision). Both directions are asserted so the floor cannot be
// tuned to pass one at the other's expense.
//
// Run: node --test workers/search-floor-real-corpus.test.mjs
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import worker, { buildBM25Index, BM25_INDEX_KEY } from './register-proxy-sw.js';
import { testToken } from './_test-token.mjs';

const TOKEN = testToken('real-corpus');

// Production builds `indexText` from D1's rich projection (summary + problem +
// root_cause + solution + verification, one 6000-char budget). `data/lessons.json`
// carries summary + a ~2.4k preview, which is a subset of that — sufficient here and
// dependency-free. The projection rule itself is pinned separately in
// workers/bm25-index-refresh.test.mjs.
const CORPUS = JSON.parse(readFileSync(new URL('../data/lessons.json', import.meta.url), 'utf8'))
  .map((l) => ({
    id: l.id,
    title: l.title || '',
    domain: l.domain || '',
    tags: l.tags || [],
    path: l.url || '',
    description: (l.summary || '').slice(0, 400),
    indexText: `${l.summary || ''} ${l.preview || ''}`.slice(0, 6000),
  }));

function createEnv() {
  const store = new Map([
    [BM25_INDEX_KEY, JSON.stringify(buildBM25Index(CORPUS))],
    ['proxy:lessons', JSON.stringify({ ts: Date.now(), data: CORPUS })],
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
  };
}

async function search(env, query, top = 5) {
  const response = await worker.fetch(new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${TOKEN}`, 'Content-Type': 'application/json',
      'MCP-Protocol-Version': '2025-06-18', 'Origin': 'https://misakanet.org',
      'CF-Connecting-IP': `198.51.100.${Math.floor(Math.random() * 200) + 1}`,
    },
    body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'tools/call',
      params: { name: 'misakanet_search', arguments: { query, top } } }),
  }), env);
  const body = await response.json();
  const payload = JSON.parse(body.result.content[0].text);
  return { ids: (payload.results || []).map((r) => r.id), noMatch: !!payload.no_match };
}

const env = createEnv();

// Recall: the lesson that answers the query must be found.
const POSITIVES = [
  ['docker exit code 137', ['kubernetes-crashloopbackoff-debugging']],
  ['kubectl crashloopbackoff', ['kubernetes-crashloopbackoff-debugging']],
  ['pip install timeout corporate proxy', ['pip-install-proxy-timeout', 'instalacao-pip-timeout-proxy']],
  ['DCO sign-off missing', ['dco-auto-fix-workflow', 'ci-dco-fork-pr-signoff', 'dco-signoff-force-push-pitfall']],
];

for (const [query, expected] of POSITIVES) {
  test(`real corpus: "${query}" finds its lesson`, async () => {
    const { ids, noMatch } = await search(env, query);
    assert.equal(noMatch, false, `answered no_match for a query the corpus can answer`);
    assert.ok(ids.slice(0, 3).some((id) => expected.includes(id)),
      `expected one of ${expected.join(', ')} in the top 3, got ${ids.join(', ')}`);
  });
}

// Precision: a query with no corresponding lesson must say so instead of returning
// neighbours. Every one of these returned results before the coverage floor.
const NEGATIVES = [
  'how do I bake sourdough bread',
  'best pizza in Rome tonight',
  'what is the capital of France',
  'who won the match last night',
  'recipe for chocolate cake',
];

for (const query of NEGATIVES) {
  test(`real corpus: "${query}" is an honest miss`, async () => {
    const { ids, noMatch } = await search(env, query);
    assert.equal(noMatch, true,
      `expected no_match, got ${ids.join(', ')} — a document matching one corpus-wide word is not an answer`);
  });
}

test('real corpus: the index covers every lesson', () => {
  const index = buildBM25Index(CORPUS);
  assert.equal(index.docCount, CORPUS.length);
  assert.ok(Object.keys(index.terms).length > 2000, 'expected a real vocabulary');
});
