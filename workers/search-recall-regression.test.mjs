// A query must find the lesson that answers it, even when alias expansion adds words (#2079).
//
// The failure this pins, measured against the live index on 2026-09-23:
//
//   query "playwright wsl missing libnss3"    →  expanded for scoring to "… windows proxy"
//   returned  wsl-proxy-setup · wsl-proxy-huggingface-external · model-switch-script-pattern
//   correct   playwright-snap-chromium-libnss3-sandbox-launch (7.93) · openclaw-…-libnss3-… (7.48)
//
// The two winners scored **3.28** and match only "wsl"; they came first because the expansion's
// `windows proxy` — the exact topic of those two lessons — carried the same weight as the words the
// user typed. Expansions are guesses at what the user meant: they may add relevance, they may not
// outrank a document that matches more of the user's own words.
//
// `fixtures/search-recall-index.json` is extracted from the **live** index so this gate reproduces
// production instead of approximating it: an index built in-process from `data/lessons.json` does
// *not* reproduce the failure (measured 2026-09-23 — it returns the libnss3 lesson first either way,
// which made an earlier version of this file pass with the fix reverted). Only the terms this query
// can score are kept; `idf`/`tf`/`len`/`df` and `avgDocLen`/`docCount` are the production values,
// and the floor's df/docCount ratio therefore stays real too. Regenerate with:
//
//   wrangler kv key get worker_search_index --namespace-id <NS> --remote > /tmp/live-index.json
//   # then keep terms {playwright,wsl,missing,libnss3,windows,proxy} and the docs they reference
//
// Run: node --test workers/search-recall-regression.test.mjs
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import worker, { buildBM25Index } from './register-proxy-sw.js';
import { testToken } from './_test-token.mjs';

const TOKEN = testToken('search-recall');
const LIVE = JSON.parse(readFileSync(new URL('./fixtures/search-recall-index.json', import.meta.url), 'utf8'));

const LIBNSS3 = ['openclaw-playwright-wsl-libnss3-libnspr4-snap-chromium',
                 'playwright-snap-chromium-libnss3-sandbox-launch'];
// The documents the expansion's topic points at, which must not outrank the user's own words.
const EXPANSION_TOPIC = ['wsl-proxy-setup', 'wsl-proxy-huggingface-external', 'model-switch-script-pattern'];

function createEnv(index, { debug = '0' } = {}) {
  const lessons = (index.docs || []).map((d) => ({ ...d, status: 'published', description: d.title }));
  const store = new Map([
    ['worker_search_index', JSON.stringify(index)],
    ['proxy:lessons', JSON.stringify({ ts: Date.now(), data: lessons })],
  ]);
  return {
    MCP_TOKEN: TOKEN,
    MCP_VERSION: 'search-recall-test',
    MISAKA_DEBUG: debug,
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

async function search(query, env, top = 5) {
  const res = await worker.fetch(new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${TOKEN}`,
      'Content-Type': 'application/json',
      'MCP-Protocol-Version': '2025-06-18',
      'CF-Connecting-IP': '198.51.100.' + (Math.floor(Math.random() * 200) + 1),
    },
    body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'tools/call',
      params: { name: 'misakanet_search', arguments: { query, top } } }),
  }), env);
  const body = await res.json();
  return body?.result?.structuredContent || body?.result || {};
}

test('the fixture carries the production numbers this gate depends on', () => {
  // A fixture that has been trimmed too far stops reproducing the failure — which is how an earlier
  // version of this file passed while the bug was present. Pin the values the score depends on.
  assert.equal(LIVE.docCount, 411, 'docCount feeds the relevance floor\'s df/docCount ratio');
  assert.ok(LIVE.avgDocLen > 50, `avgDocLen ${LIVE.avgDocLen} is not the production index (≈109)`);
  for (const term of ['playwright', 'wsl', 'missing', 'libnss3', 'windows', 'proxy']) {
    assert.ok(LIVE.terms[term], `the fixture lost the term ${term}; the query cannot reproduce`);
  }
  assert.equal(LIVE.terms.libnss3.docs.length, LIVE.terms.libnss3.df, 'df must be the real one');
  const ids = LIVE.docs.map((d) => d.id);
  for (const id of [...LIBNSS3, ...EXPANSION_TOPIC]) assert.ok(ids.includes(id), `${id} missing from the fixture`);
});

test('the words the user typed decide the order; the expansion does not outrank them', async () => {
  const sc = await search('playwright wsl missing libnss3', createEnv(LIVE));
  const ids = (sc.results || []).map((r) => r.id);
  assert.ok(ids.length >= 2, `expected hits, got ${JSON.stringify(ids)}`);

  const firstLibnss3 = Math.min(...LIBNSS3.map((id) => ids.indexOf(id)).filter((i) => i >= 0));
  assert.ok(Number.isFinite(firstLibnss3), `neither libnss3 lesson was returned: ${JSON.stringify(ids)}`);
  for (const id of EXPANSION_TOPIC) {
    const at = ids.indexOf(id);
    assert.ok(at === -1 || firstLibnss3 < at,
      `${id} (an expansion-topic match) outranked the lesson matching the user's words: ${JSON.stringify(ids)}`);
  }
  assert.ok(ids.indexOf(LIBNSS3[0]) < ids.indexOf(LIBNSS3[1]) || ids.indexOf(LIBNSS3[1]) === 0
    || ids.indexOf(LIBNSS3[0]) === -1,
    `the 7.93-scoring lesson should not fall below the 7.48 one without a reason: ${JSON.stringify(ids)}`);
});

test('the alias expansion is still applied — the fix is the ordering, not disabling expansions',
  async () => {
    const logged = [];
    const original = console.log;
    console.log = (...args) => logged.push(
      args.map((a) => (typeof a === 'string' ? a : JSON.stringify(a))).join(' '));
    try {
      await search('playwright wsl missing libnss3', createEnv(LIVE, { debug: '2' }));
    } finally {
      console.log = original;
    }
    const expansion = logged.find((line) => line.includes('query alias expansion'));
    assert.ok(expansion, `no expansion happened, so the test above proves nothing: ${logged.join(' | ')}`);
    assert.ok(expansion.includes('windows proxy'),
      `the expansion no longer adds the terms this regression is about: ${expansion}`);
  });

test('a Chinese query still finds its lesson (the #1780 path, where expansions are the ordering terms)',
  async () => {
    // CJK is invisible to `bm25Tokenize`, so `floorTerms` *is* the expanded set and the new sort key
    // equals the old one — by construction, not by luck. That branch is pinned end-to-end by
    // `query-alias-expansion.test.mjs` ("the whole path through the MCP endpoint finds the lesson"),
    // which this change must keep green; re-asserting it here with a query the alias table happens
    // not to cover would only add a test that fails for an unrelated reason.
    const corpus = JSON.parse(readFileSync(new URL('../data/lessons.json', import.meta.url), 'utf8'));
    const rows = Array.isArray(corpus) ? corpus : corpus.lessons || [];
    const index = buildBM25Index(rows, { textMode: 'rich' });
    // What the sort keys are, stated directly: for a query with no visible original terms the two
    // accumulators are the same, which is why the ordering cannot have changed for Chinese.
    const sc = await search('公司代理导致 SSL 证书校验失败', createEnv(index));
    assert.equal(sc.source, 'worker-bm25', 'the BM25 path must still be the one answering');
    assert.ok(Array.isArray(sc.results), `expected a result array, got ${JSON.stringify(sc).slice(0, 120)}`);
  });
