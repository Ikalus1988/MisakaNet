// Two changes measured on the live service (2026-09-29), both about *who* may see what.
//
// 1. `/api/analytics` published `knowledge_gaps` — the `no_match` column, i.e. **verbatim failed queries**
//    — world-readable and crawlable. Measured live, the top entry was a complete multi-sentence agent
//    prompt (`"What supported method reloads MCP configuration in an already-running Codex desk…"`, count
//    15). A failed query is whatever the caller sent; there is no length or content bound, so it cannot be
//    sanitised into safety. `/api/analytics/traffic` published `mcpClients`, which is other people's tool
//    names and call volumes keyed on a self-declared field.
//
//    The aggregate activity stays public (the site panel and the badges are built on it); the two fields
//    that carry other people's words and names now require the maintainer token — the same credential that
//    already unlocks the write tools. `top_searches`/`intents` stay public but bounded to query length.
//
// 2. The cron gated its traffic roll-up and its **search-index rebuild** on `env.MISAKANET_KV`, while both
//    write through the D1-first helpers. The day KV is dropped, the index would stop rebuilding and search
//    would fall back to the naive matcher with nothing reporting it. The guard now asks `hasDurableStore`,
//    the same question the readers ask.
//
// Run: node --test workers/analytics-exposure.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import worker, { BM25_INDEX_KEY, storeGet } from './register-proxy-sw.js';
import { testToken } from './_test-token.mjs';

const TOKEN = testToken('analytics-exposure');
const PROMPT = 'What supported method reloads MCP configuration in an already-running Codex desktop '
             + 'app-server after codex mcp remove succeeds, and does it need a restart?';

/** Minimal D1 stand-in: answers the five analytics queries and the counter reads, nothing else. */
function createD1() {
  const rowsFor = (sql) => {
    if (/event='search'/.test(sql)) return [{ query: 'pip install timeout corporate proxy', n: 159 }];
    if (/event='get_lesson'/.test(sql)) return [{ lesson_id: 'lessons/contrib/pip-install-proxy-timeout.md', n: 67 }];
    if (/event='no_match'/.test(sql)) return [{ query: PROMPT, n: 15 }];
    if (/event='intent'/.test(sql)) return [{ intent: 'reload-mcp-config', n: 4 }];
    if (/GROUP BY day/.test(sql)) return [{ day: '2026-09-29', n: 9 }];
    return [];
  };
  return {
    prepare(sql) {
      const stmt = {
        bind() { return stmt; },
        async all() { return { results: rowsFor(sql) }; },
        async first() { return rowsFor(sql)[0] || null; },
        async run() { return { success: true }; },
      };
      return stmt;
    },
  };
}

function createEnv({ kv = true } = {}) {
  const store = new Map();
  const env = {
    MCP_TOKEN: TOKEN,
    MISAKANET_D1: createD1(),
    _store: store,
  };
  if (kv) {
    env.MISAKANET_KV = {
      async get(key, type) { return store.has(key) ? (type === 'json' ? JSON.parse(store.get(key)) : store.get(key)) : null; },
      async put(key, value) { store.set(key, String(value)); },
      async delete(key) { store.delete(key); },
    };
  }
  return env;
}

async function get(env, path, { asMaintainer = false } = {}) {
  const headers = { 'CF-Connecting-IP': '198.51.100.42' };
  if (asMaintainer) headers.Authorization = `Bearer ${TOKEN}`;
  const response = await worker.fetch(new Request(`https://misakanet.org${path}`, { headers }), env);
  return { status: response.status, headers: response.headers, body: await response.json() };
}

test('anonymous analytics keep the aggregate and withhold the words', async () => {
  const { status, headers, body } = await get(createEnv(), '/api/analytics');
  assert.equal(status, 200, JSON.stringify(body));
  assert.ok(!('knowledge_gaps' in body), `a failed query is whatever the caller sent: ${JSON.stringify(body.knowledge_gaps)}`);
  assert.deepEqual(body.withheld, ['knowledge_gaps', 'mcpClients'], JSON.stringify(body.withheld));
  assert.equal(body.text_limit, 120, 'the bound must be visible to a consumer');
  assert.equal(headers.get('x-robots-tag'), 'noindex', 'a crawlable usage record is the exposure');

  // What stays: aggregated activity, with query text bounded to query length rather than prompt length.
  assert.equal(body.top_searches[0].query, 'pip install timeout corporate proxy');
  assert.ok(body.top_lessons.length && body.daily_requests.length, JSON.stringify(body));
  const long = 'x'.repeat(500);
  assert.ok(body.top_searches.every(row => row.query.length <= 120), JSON.stringify(body.top_searches));
  assert.ok(long.length > 120, 'the fixture must be longer than the bound for this test to mean anything');
});

test('the maintainer token still gets the full breakdown', async () => {
  const { body } = await get(createEnv(), '/api/analytics', { asMaintainer: true });
  assert.equal(body.knowledge_gaps[0].query, PROMPT, 'the maintainer loses the failed-query record');
  assert.equal(body.knowledge_gaps[0].count, 15, JSON.stringify(body.knowledge_gaps));
  assert.ok(!('withheld' in body), 'nothing is withheld from the maintainer');
});

test('per-client counts are withheld anonymously and served to the maintainer', async () => {
  const anon = await get(createEnv(), '/api/analytics/traffic');
  assert.equal(anon.status, 200, JSON.stringify(anon.body));
  assert.ok(!('mcpClients' in anon.body), `third-party tool names were published: ${JSON.stringify(anon.body.mcpClients)}`);
  assert.deepEqual(anon.body.withheld, ['mcpClients'], JSON.stringify(anon.body));
  assert.equal(anon.headers.get('x-robots-tag'), 'noindex');

  const mine = await get(createEnv(), '/api/analytics/traffic', { asMaintainer: true });
  assert.ok('mcpClients' in mine.body, 'the maintainer must still see who is calling');
  assert.ok(!('withheld' in mine.body), JSON.stringify(mine.body));
});

test('a wrong token gets the anonymous payload, not an error', async () => {
  const env = createEnv();
  const response = await worker.fetch(new Request('https://misakanet.org/api/analytics', {
    headers: { Authorization: 'Bearer not-the-token', 'CF-Connecting-IP': '198.51.100.43' },
  }), env);
  const body = await response.json();
  assert.equal(response.status, 200, JSON.stringify(body));
  assert.ok(!('knowledge_gaps' in body), 'a bad credential must not be better than none');
});
