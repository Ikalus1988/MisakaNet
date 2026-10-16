// Coogen 借鉴 Phase 1 tests: misakanet_me_events — reuse evidence, and what E4 rests on.
//
// Since 2026-10-16 E4 is conferred only by an *observed* signal (cross-node confirmation), never by
// counting lower ones. The red half of that rule was measured against the pre-fix worker
// (`git show origin/main:workers/register-proxy-sw.js`): a lesson with 2 helpful votes came back
// `evidence: "E4"`. The pair of tests below is the fixture — `...two_votes...` watches the cheap
// signal fail to reach the rung, `...observed_confirmation...` watches the rung stay reachable.
//
// Run: node --test workers/me-events.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import worker from './register-proxy-sw.js';
import { testToken } from './_test-token.mjs';

const TOKEN = testToken('me-events');

// Global fetch mock: regression_queries.json returns configurable data, and the GitHub contents API
// serves whatever lesson body a test puts in `lessonBodies` (empty → 404, i.e. no cross-node
// confirmation). URLs are matched on parsed hostname/pathname — never on substrings
// (CodeQL #62: incomplete URL substring sanitization).
const regressionQueries = { queries: [] };
const lessonBodies = new Map();
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
    const match = parsed.pathname.match(/\/contents\/(.+)$/);
    const body = match ? lessonBodies.get(decodeURIComponent(match[1])) : undefined;
    if (body !== undefined) {
      return new Response(JSON.stringify({
        content: Buffer.from(body, 'utf8').toString('base64'),
        encoding: 'base64',
      }), { status: 200, headers: { 'Content-Type': 'application/json' } });
    }
    return new Response('{"message":"Not Found"}', { status: 404, headers: { 'Content-Type': 'application/json' } });
  }
  return origFetch(url);
};

function createEnv(seed = {}) {
  const store = new Map(Object.entries(seed));
  return {
    MCP_TOKEN: TOKEN,
    // Cross-node confirmation is parsed out of the lesson body, which the worker reads through the
    // GitHub contents API; without a token `fetchLessonContent` throws and the signal never appears.
    REGISTER_TOKEN: TOKEN,
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

test('misakanet_me_events reports a helpful vote as an E3 hint', async () => {
  regressionQueries.queries = [];
  lessonBodies.clear();
  const env = createEnv({ 'helpful:dco-auto-fix': '1' });
  const resp = await meEvents({ lesson_id: 'dco-auto-fix' }, env);
  assert.equal(resp.status, 200);
  const result = await resultText(resp);
  assert.equal(result.lesson_id, 'dco-auto-fix');
  const helpful = result.events.find(e => e.type === 'lesson_found_helpful');
  assert.ok(helpful, 'the vote event stays: the count is still reported');
  assert.equal(helpful.count, 1);
  assert.equal(helpful.evidence_level, 'E3');
  assert.equal(result.evidence, 'E3');
});

test('misakanet_me_events does not reach E4 from 2+ helpful votes (red fixture)', async () => {
  // This is the pre-fix bug in one assertion. Against
  // `git show origin/main:workers/register-proxy-sw.js` the event above is pushed with
  // `evidence_level: helpful >= 2 ? "E4" : "E3"`, so this lesson answers `evidence: "E4"` — two
  // clicks, two opinions, conferring the top rung.
  regressionQueries.queries = [];
  lessonBodies.clear();
  const env = createEnv({ 'helpful:two-vote-lesson': '2' });
  const result = await resultText(await meEvents({ lesson_id: 'two-vote-lesson' }, env));
  const helpful = result.events.find(e => e.type === 'lesson_found_helpful');
  assert.ok(helpful, 'the vote event still carries the count');
  assert.equal(helpful.count, 2);
  assert.equal(helpful.evidence_level, 'E3');
  assert.notEqual(result.evidence, 'E4', 'a vote must never confer E4, at any count');
  assert.equal(result.evidence, 'E3');
});

test('misakanet_me_events does not reach E4 by counting votes against citations', async () => {
  regressionQueries.queries = [
    { id: 'dco-001', expected_lessons: ['lessons/core/dco-auto-fix-workflow.md'] },
    { id: 'dco-002', expected_lessons: ['lessons/core/dco-auto-fix-workflow.md'] },
  ];
  lessonBodies.clear();
  const env = createEnv({ 'helpful:dco-auto-fix-workflow': '2' });
  const resp = await meEvents({ lesson_id: 'dco-auto-fix-workflow' }, env);
  assert.equal(resp.status, 200);
  const result = await resultText(resp);
  const cited = result.events.find(e => e.type === 'lesson_cited_in_regression');
  assert.ok(cited, 'should have regression citation event');
  assert.equal(cited.count, 2);
  // Pre-fix this was "≥2 independent reuse signals → E4"; adding lower signals together is exactly
  // how a hint became proof.
  assert.equal(result.evidence, 'E3');
});

test('misakanet_me_events reaches E4 from an observed cross-node confirmation', async () => {
  regressionQueries.queries = [];
  lessonBodies.clear();
  lessonBodies.set('lessons/core/observed-reuse.md',
    '---\ntitle: Observed reuse\n---\n\nVerified by: another node (Misaka10042), 2026-10-16\n');
  // The votes are here on purpose: the observed signal must decide the level even alongside the
  // hint, not be suppressed by it (the pre-fix `e4Ready` needed two non-confirmation events).
  const env = createEnv({ 'helpful:observed-reuse': '2' });
  const result = await resultText(await meEvents({ lesson_id: 'observed-reuse' }, env));
  const helpful = result.events.find(e => e.type === 'lesson_found_helpful');
  const confirmed = result.events.find(e => e.type === 'lesson_confirmed_by');
  assert.ok(helpful, 'the votes are still reported');
  assert.equal(helpful.evidence_level, 'E3');
  assert.ok(confirmed, 'the provenance line is the observed signal');
  assert.equal(confirmed.evidence_level, 'E4');
  assert.equal(result.evidence, 'E4', 'E4 stays reachable by observation');
});

test('misakanet_me_events returns E0 for lesson with no reuse signals', async () => {
  regressionQueries.queries = [];
  lessonBodies.clear();
  const env = createEnv(); // no helpful votes, no citations, no confirmation
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

test('misakanet_me_events shares the anonymous read burst window', async () => {
  regressionQueries.queries = [];
  lessonBodies.clear();
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
  // Reads are unlimited since 2026-09-18; what stops a crawler is the burst window, so this test
  // fills it and asserts the refusal is a *speed* message rather than a quota one.
  for (let i = 0; i < 20; i++) {
    const resp = await anonymous({ lesson_id: 'quota-lesson' });
    assert.equal(resp.status, 200);
    const result = await resultText(resp);
    assert.equal(result.evidence, 'E0', `read ${i + 1} must succeed`);
  }
  const blocked = await anonymous({ lesson_id: 'quota-lesson' });
  const blockedResult = await resultText(blocked);
  assert.match(blockedResult.error, /Too many requests: max \d+ reads per \d+s/);
  assert.match(blockedResult.error, /Reads are unlimited/,
    'a refusal must not read as a quota: registration is not the way to read more');
});
