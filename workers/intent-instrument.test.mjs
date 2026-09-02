// Coogen 借鉴 Phase 2 tests: ?intent= instrumentation (id-only, opt-in,
// invalid values silently dropped) + /start single-door mode.
// Run: node --test workers/intent-instrument.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import worker from './register-proxy-sw.js';

const TOKEN = 'intent-test-token';

// D1 stub: captures INSERT INTO lesson_usage into _usage; returns seeded
// lessons for the full-scan SELECT; empty for everything else.
function createD1(rows) {
  const usage = [];
  return {
    _usage: usage,
    prepare(sql) {
      const stmt = {
        _bound: [],
        bind(...args) { stmt._bound = args; return stmt; },
        async all() {
          if (sql.includes('FROM lessons') && !sql.includes('WHERE')) return { results: rows };
          return { results: [] };
        },
        async run() {
          if (sql.trim().startsWith('INSERT INTO lesson_usage')) {
            const b = stmt._bound || [];
            usage.push({ event: b[0], query: b[1], lesson_id: b[2], domain: b[3], ip: b[4], user_agent: b[5] });
          }
          return { success: true };
        },
      };
      return stmt;
    },
  };
}

function createEnv(opts = {}) {
  const store = new Map(Object.entries(opts.kvSeed || {}));
  return {
    MCP_TOKEN: TOKEN,
    MCP_VERSION: 'intent-test',
    REGISTER_TOKEN: 'gh-test-token',
    MISAKANET_KV: {
      async get(key, type) {
        if (!store.has(key)) return null;
        const raw = store.get(key);
        return type === 'json' ? JSON.parse(raw) : raw;
      },
      async put(key, value) { store.set(key, value); },
      _store: store,
    },
    MISAKANET_D1: createD1(opts.d1Rows || []),
  };
}

// ctx collects waitUntil promises so analytics writes can be awaited.
function collectCtx() {
  const pending = [];
  return { ctx: { waitUntil: (p) => pending.push(p) }, pending };
}

function mcpCall(name, args, env, ctx) {
  return worker.fetch(new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${TOKEN}`,
      'Content-Type': 'application/json',
      'MCP-Protocol-Version': '2025-06-18',
      'CF-Connecting-IP': '203.0.113.11',
    },
    body: JSON.stringify({
      jsonrpc: '2.0', id: 1, method: 'tools/call',
      params: { name, arguments: args },
    }),
  }), env, ctx);
}

async function resultText(response) {
  const body = await response.json();
  return JSON.parse(body.result.content[0].text);
}

const D1_ROWS = [{
  id: 'pip-mirror', title: 'pip install timeout', domain: 'python', status: 'published',
  tags: '["pip"]', path: 'lessons/core/pip-mirror.md', summary: 'use a mirror',
  problem: 'pip install times out', updated: '2026-08-28T00:00:00Z', created: '2026-06-01T00:00:00Z',
}];

test('misakanet_search records a valid intent as an event=intent row', async () => {
  const env = createEnv({ d1Rows: D1_ROWS });
  const { ctx, pending } = collectCtx();
  const resp = await mcpCall('misakanet_search', { query: 'pip timeout', intent: 'eval' }, env, ctx);
  assert.equal(resp.status, 200);
  await Promise.all(pending);
  const intents = env.MISAKANET_D1._usage.filter(u => u.event === 'intent');
  assert.equal(intents.length, 1);
  assert.equal(intents[0].query, 'eval');
});

test('misakanet_search silently drops invalid intent (no error, no row)', async () => {
  const env = createEnv({ d1Rows: D1_ROWS });
  const { ctx, pending } = collectCtx();
  const resp = await mcpCall('misakanet_search', { query: 'pip timeout', intent: 'shopping' }, env, ctx);
  assert.equal(resp.status, 200);
  const result = await resultText(resp);
  assert.equal(result.error, undefined);
  assert.ok(Array.isArray(result.results));
  await Promise.all(pending);
  assert.equal(env.MISAKANET_D1._usage.filter(u => u.event === 'intent').length, 0);
});

test('misakanet_submit_intake records valid intent and still submits', async () => {
  const env = createEnv();
  const { ctx, pending } = collectCtx();
  // Mock the GitHub issue POST.
  const origFetch = globalThis.fetch;
  globalThis.fetch = async (url, opts) => {
    if (typeof url === 'string' && url.includes('/issues')) {
      return new Response(JSON.stringify({ number: 7, html_url: 'https://github.com/x/issues/7' }), {
        status: 201, headers: { 'Content-Type': 'application/json' },
      });
    }
    return origFetch(url, opts);
  };
  try {
    const resp = await mcpCall('misakanet_submit_intake',
      { problem: 'intent test problem', intent: 'intake' }, env, ctx);
    assert.equal(resp.status, 200);
    const result = await resultText(resp);
    assert.equal(result.submitted, true);
    await Promise.all(pending);
    const intents = env.MISAKANET_D1._usage.filter(u => u.event === 'intent');
    assert.equal(intents.length, 1);
    assert.equal(intents[0].query, 'intake');
  } finally {
    globalThis.fetch = origFetch;
  }
});

test('misakanet_submit_intake silently drops invalid intent', async () => {
  const env = createEnv();
  const { ctx, pending } = collectCtx();
  const origFetch = globalThis.fetch;
  globalThis.fetch = async (url, opts) => {
    if (typeof url === 'string' && url.includes('/issues')) {
      return new Response(JSON.stringify({ number: 8, html_url: 'https://github.com/x/issues/8' }), {
        status: 201, headers: { 'Content-Type': 'application/json' },
      });
    }
    return origFetch(url, opts);
  };
  try {
    const resp = await mcpCall('misakanet_submit_intake',
      { problem: 'intent invalid test', intent: 'hack' }, env, ctx);
    assert.equal(resp.status, 200);
    const result = await resultText(resp);
    assert.equal(result.submitted, true);
    await Promise.all(pending);
    assert.equal(env.MISAKANET_D1._usage.filter(u => u.event === 'intent').length, 0);
  } finally {
    globalThis.fetch = origFetch;
  }
});

test('GET /start serves the single-door page with the two-things CTA', async () => {
  const env = createEnv();
  const resp = await worker.fetch(new Request('https://misakanet.org/start'), env);
  assert.equal(resp.status, 200);
  const html = await resp.text();
  assert.match(html, /你只做两件事——授权，看结果/);
  assert.match(html, /Search lessons/);
});

test('GET /start?intent= forwards intent into the search link; bogus intent is dropped', async () => {
  const env = createEnv();
  const withIntent = await worker.fetch(new Request('https://misakanet.org/start?intent=eval'), env);
  assert.match(await withIntent.text(), /\/search\/\?intent=eval/);
  const bogus = await worker.fetch(new Request('https://misakanet.org/start?intent=spam'), env);
  assert.match(await bogus.text(), /href="\/search\/"/);
});

test('GET /connect redirects (301) to /start — single door', async () => {
  const env = createEnv();
  const resp = await worker.fetch(new Request('https://misakanet.org/connect'), env);
  assert.equal(resp.status, 301);
  assert.equal(resp.headers.get('location'), '/start');
});

test('search-signal records valid intent in the unsolved map; invalid is dropped', async () => {
  const env = createEnv();
  const post = (intent) => worker.fetch(new Request('https://misakanet.org/api/search-signal', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'CF-Connecting-IP': '203.0.113.12' },
    body: JSON.stringify({ query: 'sqlite database is locked', result_count: 0, top_score: 0, intent }),
  }), env);

  const ok = await post('search');
  const okBody = await ok.json();
  assert.equal(okBody.recorded, true);
  assert.equal(okBody.intent, 'search');

  const bad = await post('nonsense');
  const badBody = await bad.json();
  assert.equal(badBody.recorded, true);
  assert.equal(badBody.intent, undefined);

  const records = [...env.MISAKANET_KV._store.entries()]
    .filter(([k]) => k.startsWith('unsolved:family:'));
  assert.equal(records.length, 1, 'both signals land in the same family bucket');
  const rec = JSON.parse(records[0][1]);
  assert.deepEqual(rec.intents, { search: 1 }, 'only the valid intent is aggregated');
});
