// Coogen 借鉴 Phase 1 tests: misakanet_me_events — reuse evidence, and what E4 rests on.
//
// Since 2026-10-17 E4 has exactly one producer, and it is an *observation*: two or more distinct
// clients actually retrieved the lesson, counted from `search_signals.client_hint` (written by the
// worker from the request, never from the lesson body). Everything else the tool reports is an E3
// hint — a helpful vote, a regression citation, and a lesson's own `verified by:` line — and none of
// them can confer the rung by being counted, trusted, or typed.
//
// The red half of every rule below was measured against the pre-fix worker (the vote-cap commit this
// change builds on, materialised with `git show <sha>:workers/register-proxy-sw.js`). Two defects
// lived there, in opposite directions: a lesson body containing `verified by: someone` answered
// `evidence: "E4"` — the top rung conferred by prose — while a lesson two distinct clients had
// genuinely retrieved could not reach it at all. The fixtures watch both.
//
// Run: node --test workers/me-events.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import worker from './register-proxy-sw.js';
import { testToken } from './_test-token.mjs';

const TOKEN = testToken('me-events');

// Global fetch mock: regression_queries.json returns configurable data, and the GitHub contents API
// serves whatever lesson body a test puts in `lessonBodies` (empty → 404, i.e. no declared
// provenance). URLs are matched on parsed hostname/pathname — never on substrings
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

/**
 * Minimal D1 stand-in for the one `search_signals` query `countDistinctRetrievingClients` issues.
 *
 * It answers *from the SQL it is handed*, not from a hard-coded number, and it throws on a shape it
 * does not model — so the fixture is anchored to the predicate rather than to this file's opinion of
 * it. Mutating the worker's `COUNT(DISTINCT client_hint)` into `COUNT(*)`, or dropping the
 * `client_hint IS NOT NULL` guard, cannot pass silently through a double that would have computed
 * the right answer anyway: the unmodelled query raises, the handler's `catch` swallows it, and the
 * observation disappears — which is exactly what the rule tests assert must not happen.
 *
 * `matched` counts the rows the predicate selected, the `client_hint IS NOT NULL` guard included, so
 * a test can show the anonymous rows were present in the table and were rejected before the
 * aggregate rather than silently averaged in.
 */
const D1_DISTINCT = /COUNT\s*\(\s*DISTINCT\s+client_hint\s*\)/i;
const D1_ANON_GUARD = /client_hint\s+IS\s+NOT\s+NULL/i;

function createSearchSignalsD1(rows) {
  const seen = { queries: 0, matched: 0 };
  return {
    rows,
    seen,
    prepare(sql) {
      const stmt = {
        _bound: [],
        bind(...args) { stmt._bound = args; return stmt; },
        async first() {
          if (!/FROM\s+search_signals/i.test(sql)) return null;
          seen.queries += 1;
          if (!D1_DISTINCT.test(sql) || !D1_ANON_GUARD.test(sql)) {
            throw new Error(`unmodelled search_signals query: ${sql}`);
          }
          // Binding order is the worker's: exact `top_id` candidates first, then the `%/id.md`
          // pattern for a search that stored a path.
          const bound = stmt._bound.map(String);
          const like = bound.find(v => v.startsWith('%/'));
          const exact = bound.filter(v => v !== like);
          const kept = v => v !== null && v !== undefined && v !== '';
          const matched = rows.filter(r => {
            const top = String(r.top_id ?? '');
            const hit = exact.includes(top) || (!!like && top.endsWith(like.slice(1)));
            return hit && kept(r.client_hint);
          });
          seen.matched += matched.length;
          const clients = new Set(matched.map(r => r.client_hint));
          return { clients: clients.size };
        },
        async all() { return { results: [] }; }, // kv_store is empty → storeGet falls back to KV
        async run() { return { success: true }; },
      };
      return stmt;
    },
  };
}

function createEnv(seed = {}, { d1 = null } = {}) {
  const store = new Map(Object.entries(seed));
  return {
    MCP_TOKEN: TOKEN,
    // The declared-provenance path reads the lesson body through the GitHub contents API; without a
    // token `fetchLessonContent` throws and the hint never appears.
    REGISTER_TOKEN: TOKEN,
    MCP_VERSION: 'me-events-test',
    ...(d1 ? { MISAKANET_D1: d1 } : {}),
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

function observedEvent(result) {
  return result.events.find(e => e.type === 'lesson_retrieved_by_distinct_clients');
}

// ── the hints: real signals, E3, never the rung ───────────────────────────────────────────────────

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
  // This is the pre-fix bug in one assertion. Against the vote-cap change's own pre-fix worker
  // (`git show origin/main:workers/register-proxy-sw.js`) the event above is pushed with
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
  // "≥2 independent reuse signals → E4" is how a hint became proof; adding lower signals together
  // must not do it.
  assert.equal(result.evidence, 'E3');
});

test('misakanet_me_events reports a declared `verified by:` line as an E3 hint, never E4 (red fixture)', async () => {
  // The defect this pins: the prose path parsed the lesson's own body and emitted
  // `evidence_level: "E4"`, so anyone who could edit the lesson could award themselves the top rung
  // by typing one line — cheaper than the vote the previous change had just demoted. Against the
  // pre-fix worker this body answers `evidence: "E4"`.
  regressionQueries.queries = [];
  lessonBodies.clear();
  lessonBodies.set('lessons/core/self-declared.md',
    '---\ntitle: Self-declared\n---\n\nVerified by: someone else\n');
  const result = await resultText(await meEvents({ lesson_id: 'self-declared' }, createEnv()));
  const declared = result.events.find(e => e.type === 'lesson_confirmed_by');
  assert.ok(declared, 'the declaration is still reported: it is information');
  assert.equal(declared.evidence_level, 'E3');
  assert.deepEqual(declared.sources, ['someone else']);
  assert.equal(result.evidence, 'E3');
  assert.notEqual(result.evidence, 'E4', 'a line the lesson writes about itself cannot confer E4');
  // The old comment above this code claimed "provenance shows multiple contributors" while the code
  // accepted a single name. One name is this fixture, so the comment cannot drift back.
});

// ── the rung: observed retrieval, and only that ──────────────────────────────────────────────────

test('misakanet_me_events reaches E4 when two distinct clients retrieved the lesson (red fixture)', async () => {
  // Nothing else is present: no votes, no citations, no prose. Against the pre-fix worker this
  // answers E0/E3 — the rung was unreachable by observation — which is the other half of the defect.
  regressionQueries.queries = [];
  lessonBodies.clear();
  const d1 = createSearchSignalsD1([
    { top_id: 'observed-lesson', client_hint: 'h-client-a' },
    { top_id: 'observed-lesson', client_hint: 'h-client-b' },
    { top_id: 'observed-lesson', client_hint: 'h-client-a' }, // repetition by an existing client
    { top_id: 'a-different-lesson', client_hint: 'h-client-c' }, // must not leak across lessons
  ]);
  const result = await resultText(await meEvents({ lesson_id: 'observed-lesson' }, createEnv({}, { d1 })));
  const observed = observedEvent(result);
  assert.ok(observed, 'observed retrieval is the one producer of E4');
  assert.equal(observed.count, 2, 'distinct clients: a and b, not the three rows');
  assert.equal(observed.evidence_level, 'E4');
  assert.equal(result.evidence, 'E4');
});

test('misakanet_me_events does not reach E4 from forty retrievals by one client (red fixture)', async () => {
  // The rule is distinctness, not volume. A `COUNT(*)` implementation of the same intent would
  // answer 40 here and confer E4, so the `count === 1` assertion is what makes that mutation
  // observable — the number itself is the fixture.
  regressionQueries.queries = [];
  lessonBodies.clear();
  const d1 = createSearchSignalsD1(
    Array.from({ length: 40 }, () => ({ top_id: 'busy-but-one', client_hint: 'h-lonely-client' })),
  );
  const result = await resultText(await meEvents({ lesson_id: 'busy-but-one' }, createEnv({}, { d1 })));
  assert.equal(d1.seen.matched, 40, 'all forty retrievals matched the predicate');
  const observed = observedEvent(result);
  assert.ok(observed, 'one observed client is still worth reporting');
  assert.equal(observed.count, 1, 'forty retrievals by one client are one client');
  assert.equal(observed.evidence_level, 'E3');
  assert.notEqual(result.evidence, 'E4');
  assert.equal(result.evidence, 'E3');
});

test('misakanet_me_events does not count callers with no client_hint (the deliberate undercount)', async () => {
  // Anonymous callers send no `client_id`, so no `client_hint` is written. Their rows are in the
  // table and the predicate rejects them before the aggregate (`client_hint IS NOT NULL`), so they
  // cannot even be counted — the test asserts both halves, because the undercount is the property
  // this signal is chosen for, not an oversight to be "fixed" later. The tempting fix is a
  // User-Agent fallback; the UA is shared by every curl and every browser of the same version and is
  // trivially spoofed, so counting it would make the number meaningless.
  regressionQueries.queries = [];
  lessonBodies.clear();
  const d1 = createSearchSignalsD1([
    ...Array.from({ length: 40 }, (_, i) => ({ top_id: 'mixed-traffic', client_hint: null, agent: `agent-${i}` })),
    { top_id: 'mixed-traffic', client_hint: 'h-known-client' },
  ]);
  const result = await resultText(await meEvents({ lesson_id: 'mixed-traffic' }, createEnv({}, { d1 })));
  assert.equal(d1.rows.length, 41, 'the forty anonymous retrievals are in the table');
  assert.equal(d1.seen.matched, 1, 'the guard rejects them before the aggregate');
  const observed = observedEvent(result);
  assert.ok(observed);
  assert.equal(observed.count, 1, 'forty anonymous retrievals add nothing to the distinct count');
  assert.equal(observed.evidence_level, 'E3');
  assert.notEqual(result.evidence, 'E4', 'anonymous traffic must not be able to confer the rung');
});

test('misakanet_me_events matches the path form a search writes into top_id', async () => {
  // A search stores `results[0].id || results[0].path`, so one lesson's traffic can be split across
  // an id form and a path form. Both must reach the same count, or the signal silently undercounts
  // a lesson that only ever came back as a path.
  regressionQueries.queries = [];
  lessonBodies.clear();
  const d1 = createSearchSignalsD1([
    { top_id: 'lessons/core/path-form-lesson.md', client_hint: 'h-client-a' },
    { top_id: 'path-form-lesson', client_hint: 'h-client-b' },
  ]);
  const result = await resultText(await meEvents({ lesson_id: 'path-form-lesson' }, createEnv({}, { d1 })));
  const observed = observedEvent(result);
  assert.ok(observed);
  assert.equal(observed.count, 2);
  assert.equal(result.evidence, 'E4');
});

test('misakanet_me_events returns E0 for lesson with no reuse signals', async () => {
  regressionQueries.queries = [];
  lessonBodies.clear();
  const env = createEnv(); // no helpful votes, no citations, no observation, no declaration
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
