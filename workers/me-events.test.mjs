// Coogen 借鉴 Phase 1 tests: misakanet_me_events — E4 reuse evidence.
// Run: node --test workers/me-events.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import worker from './register-proxy-sw.js';

const TOKEN = 'me-events-token';

// Global fetch mock: regression_queries.json returns configurable data;
// lesson-content fetches return 404 (no cross-node confirmation in tests).
// URLs are matched on parsed hostname/pathname — never on substrings
// (CodeQL #62: incomplete URL substring sanitization).
const regressionQueries = { queries: [] };
const origFetch = globalThis.fetch;
globalThis.fetch = async (url) => {
  if (typeof url !== 'string') return origFetch(url);
  let parsed;
  try { parsed = new URL(url); } catch { return origFetch(url); }
  if (parsed.pathname.endsWith('/regression_queries.json')) {
    return new Response(JSON.stringify(regressionQueries), {
      status: 200, headers: { 'Content-Type': 'application/json' },
    });
  }
  if (parsed.hostname === 'api.github.com') {
    return new Response('{"message":"Not Found"}', { status: 404, headers: { 'Content-Type': 'application/json' } });
  }
  return origFetch(url);
};

function createEnv(seed = {}) {
  const store = new Map(Object.entries(seed));
  return {
    MCP_TOKEN: TOKEN,
    MCP_VERSION: 'me-events-test',
    MISAKANET_KV: {
      async get(key, type) {
        if (!store.has(key)) return null;
        const raw = store.get(key);
        return type === 'json' ? JSON.parse(raw) : raw;
      },
      async put(key, value) {
        store.set(key, value);
      },
      _store: store,
    },
  };
}

function meEvents(args, env) {
  return worker.fetch(new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${TOKEN}`,
      'Content-Type': 'application/json',
      'MCP-Protocol-Version': '2025-06-18',
      'CF-Connecting-IP': '203.0.113.60',
    },
    body: JSON.stringify({
      jsonrpc: '2.0', id: 1, method: 'tools/call',
      params: { name: 'misakanet_me_events', arguments: args },
    }),
  }), env);
}

async function resultText(response) {
  const body = await response.json();
  return JSON.parse(body.result.content[0].text);
}

test('misakanet_me_events returns helpful-vote evidence (E3 for single signal)', async () => {
  regressionQueries.queries = [];
  const env = createEnv({ 'helpful:dco-auto-fix': '1' });
  const resp = await meEvents({ lesson_id: 'dco-auto-fix' }, env);
  assert.equal(resp.status, 200);
  const result = await resultText(resp);
  assert.equal(result.lesson_id, 'dco-auto-fix');
  const helpful = result.events.find(e => e.type === 'lesson_found_helpful');
  assert.ok(helpful, 'should have lesson_found_helpful event');
  assert.equal(helpful.count, 1);
  assert.equal(result.evidence, 'E3');
});

test('misakanet_me_events promotes to E4 with 2+ independent reuse signals', async () => {
  regressionQueries.queries = [
    { id: 'dco-001', expected_lessons: ['lessons/core/dco-auto-fix-workflow.md'] },
    { id: 'dco-002', expected_lessons: ['lessons/core/dco-auto-fix-workflow.md'] },
  ];
  const env = createEnv({ 'helpful:dco-auto-fix-workflow': '2' });
  const resp = await meEvents({ lesson_id: 'dco-auto-fix-workflow' }, env);
  assert.equal(resp.status, 200);
  const result = await resultText(resp);
  const cited = result.events.find(e => e.type === 'lesson_cited_in_regression');
  assert.ok(cited, 'should have regression citation event');
  assert.equal(cited.count, 2);
  // helpful(2+) + regression citations → 2 independent reuse signals → E4.
  assert.equal(result.evidence, 'E4');
});

test('misakanet_me_events returns E0 for lesson with no reuse signals', async () => {
  regressionQueries.queries = [];
  const env = createEnv(); // no helpful votes, no citations
  const resp = await meEvents({ lesson_id: 'brand-new-lesson' }, env);
  assert.equal(resp.status, 200);
  const result = await resultText(resp);
  assert.deepEqual(result.events, []);
  assert.equal(result.evidence, 'E0');
});

test('misakanet_me_events requires lesson_id', async () => {
  const env = createEnv();
  const resp = await meEvents({}, env);
  assert.equal(resp.status, 200);
  const result = await resultText(resp);
  assert.match(result.error, /lesson_id or lesson_path is required/);
});

test('misakanet_me_events shares the anonymous 5-reads/day quota', async () => {
  regressionQueries.queries = [];
  const env = createEnv();
  const anonymous = (args) => worker.fetch(new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'MCP-Protocol-Version': '2025-06-18',
      'CF-Connecting-IP': '203.0.113.99',
    },
    body: JSON.stringify({
      jsonrpc: '2.0', id: 1, method: 'tools/call',
      params: { name: 'misakanet_me_events', arguments: args },
    }),
  }), env);
  for (let i = 0; i < 5; i++) {
    const resp = await anonymous({ lesson_id: 'quota-lesson' });
    assert.equal(resp.status, 200);
    const result = await resultText(resp);
    assert.equal(result.evidence, 'E0');
  }
  // 6th anonymous call → rate limited.
  const blocked = await anonymous({ lesson_id: 'quota-lesson' });
  const blockedResult = await resultText(blocked);
  assert.match(blockedResult.error, /Rate limit/);
});
