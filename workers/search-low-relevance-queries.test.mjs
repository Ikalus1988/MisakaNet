// A hit is not evidence of relevance — the boundary queries, pinned (issue #2615).
//
// Measured on production D1 (2026-10-01, recorded in discussion #2611): a question about changing a car's
// engine oil returned **2 results**, while a request for a pizza recipe returned none. "It found something"
// and "it found the right thing" are different properties, and a car-maintenance question has no business
// matching a debugging lesson.
//
// Re-measured against the real corpus on 2026-10-01, after the floor work in `search-floor-*`
// (`RELEVANCE_MIN_COVERAGE`, with numerator and denominator taken from one term space): every boundary query
// below already comes back `no_match`. The floor was right — nothing was keeping it right, which is what this
// file is for. It is the regression sample #2615 asked for.
//
// The positive control at the end matters as much as the negatives: a floor that refuses everything is not a
// fix, it is a different bug.
//
// Run: node --test workers/search-low-relevance-queries.test.mjs
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import worker, { buildBM25Index, BM25_INDEX_KEY } from './register-proxy-sw.js';
import { testToken } from './_test-token.mjs';

const TOKEN = testToken('low-relevance');

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

// Each case carries what the read actually observed, so a failure tells the next person whether this is a
// fresh regression or the old behaviour coming back.
//
// **Two cases from that read are deliberately absent**: `how do I fix my car engine oil change` and
// `best pizza recipe with mozzarella`. They stopped being boundary queries the moment
// `lessons/contrib/a-hit-is-not-evidence-of-relevance.md` was added to the corpus — the lesson quotes them, so
// the floor is now *right* to admit it for them, and asserting `no_match` would have been asserting a wish. A
// boundary query has to be one the corpus has never seen; the historical pair lives in this comment for the
// history, not in the assertions (measured 2026-10-01: two of the six failed for exactly this reason).
const NOT_RELEVANT = [
  ['zzzq nonexistent quantum flux capacitor banana 998877', 'no results on 2026-10-01'],
  ['zzqx flibber wumbo 9871', 'no results on 2026-10-01'],
  ['asdfqwer zzzz nonsense xyzzy', 'no results on 2026-10-01 (keyboard mashing)'],
  ['how to bake sourdough bread', 'no results on 2026-10-01'],
  ['0x0a', 'no results on 2026-10-01 (a hex byte, not a question)'],
  ['zzzz-no-such-thing-xyz', 'no results on 2026-10-01'],
];

for (const [query, observed] of NOT_RELEVANT) {
  test(`refuses a query with nothing to match: ${query}`, async () => {
    const { ids, noMatch } = await search(env, query);
    assert.equal(noMatch, true,
      `"${query}" was answered with ${ids.length} result(s) (${ids.slice(0, 3).join(', ')}) — ` +
      `previously observed: ${observed}. A hit is not evidence of relevance: if the corpus has nothing for ` +
      `this query, the answer is no_match, and the reason must not be a keyword blacklist (see the lesson ` +
      `in lessons/contrib/a-hit-is-not-evidence-of-relevance.md).`);
    assert.deepEqual(ids, [], `"${query}" must return no rows when no_match is reported`);
  });
}

// The control: the floor must not have been "fixed" by refusing everything.
test('still answers a query the corpus does cover', async () => {
  const { ids, noMatch } = await search(env, 'pip install timeout corporate proxy');
  assert.equal(noMatch, false, 'a covered query must not be reported as no_match');
  assert.ok(ids.includes('pip-install-proxy-timeout'),
    `the covered query must find its lesson, got: ${ids.slice(0, 5).join(', ')}`);
});
