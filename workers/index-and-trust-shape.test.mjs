// What the index and the answers must carry (#2079 shape gate, #2080 trust field).
//
// Two ways the retrieval surface can lie while every test stays green:
//
//   1. the index is published without the lesson bodies. Both routes are silent — the rich columns
//      were unavailable during a rebuild, or a build ran over summary-only rows. The documented
//      command `scripts/build_worker_index.py --lessons lessons/` does exactly this today:
//      avgDocLen 11.9 / 2,009 terms against production's 109.1 / 9,968 (measured 2026-09-23), and a
//      known recall failure stops reproducing under it because body-only queries have nothing to match;
//   2. an answer carries the trust field `evidence_level` as an **empty string**. `lessons` in D1 has no
//      such column, so the D1 path — the one production reads — never filled it, while the GitHub
//      snapshot path did. The key was present and blank on every hit, which reads as "provided" rather
//      than "missing".
//
// Run: node --test workers/index-and-trust-shape.test.mjs
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import worker, { buildBM25Index, indexShapeProblem, invalidateBM25Memo } from './register-proxy-sw.js';
import { testToken } from './_test-token.mjs';

const TOKEN = 'mcp_' + testToken('index-and-trust');
const corpus = JSON.parse(readFileSync(new URL('../data/lessons.json', import.meta.url), 'utf8'));
const ROWS = Array.isArray(corpus) ? corpus : corpus.lessons || [];

test('a build that indexed titles without the bodies is refused, not published', () => {
  // The rows *have* bodies (as production's do); the build did not index them, which is what happens
  // when the rich projection is missing at build time. Publishing it would silently degrade every
  // query, so the cron must keep the previous index and report why.
  const titleOnly = ROWS.map((r) => ({ ...r, preview: undefined, summary: r.title, description: r.title }));
  const degraded = buildBM25Index(titleOnly, { textMode: 'lean' });

  const problem = indexShapeProblem(degraded, ROWS);
  assert.ok(problem, 'a body-less build was accepted');
  assert.match(problem, /body tokens|titles without the lesson bodies/,
    `the reason should name the missing bodies, got: ${problem}`);
});

test('a real build passes the same gate', () => {
  // And the gate must not be a wall: the index that ships today has to go through it.
  const real = buildBM25Index(ROWS, { textMode: 'rich' });
  assert.equal(indexShapeProblem(real, ROWS), null,
    'the production-shaped build was refused, so the gate would block every deploy');
  assert.ok(Object.keys(real.terms).length > 3000, 'sanity: the fixture corpus is the rich one');
});

test('a malformed index is refused too', () => {
  assert.equal(indexShapeProblem(null, ROWS), 'empty index');
  assert.equal(indexShapeProblem({ docCount: 0, terms: {} }, ROWS), 'empty index');
  assert.match(indexShapeProblem({ docCount: 7, terms: { a: 1 }, avgDocLen: 100 }, ROWS), /does not match/);
});

function createEnv(rows) {
  // The index is memoised per isolate, so without this the next environment in the same test process
  // keeps answering from this one's rows (see the export's comment).
  invalidateBM25Memo();
  const real = buildBM25Index(rows, { textMode: 'rich' });
  const store = new Map([
    ['worker_search_index', JSON.stringify(real)],
    ['proxy:lessons', JSON.stringify({ ts: Date.now(), data: rows })],
  ]);
  return {
    MCP_TOKEN: TOKEN,
    MCP_VERSION: 'index-and-trust-test',
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

async function search(query, env, top = 3) {
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

test('a D1-shaped row fills evidence_level from its frontmatter', async () => {
  // D1 rows have no `evidence_level` column; they have the raw `frontmatter` JSON. This is the shape
  // production serves and the shape the response used to answer with "" for.
  const row = {
    id: 'trust-field-probe',
    title: 'pip install times out behind a proxy',
    domain: 'python',
    path: 'lessons/contrib/trust-field-probe.md',
    status: 'published',
    preview: 'pip install hangs and then fails with a read timeout behind a corporate proxy.',
    frontmatter: JSON.stringify({
      evidence_level: 'E3',
      provenance: { source: 'intake' },
      // The other three fields that live in this JSON. This path (the GitHub snapshot, or a cached
      // payload) has no upstream lift, so the public funnel is the only place they can come from —
      // and a funnel that drops the JSON without reading it takes them with it.
      summary_plain: 'pip install times out behind a corporate proxy',
      trigger: 'pip install hang',
      verify: 'pip install returns',
    }),
  };
  const sc = await search('pip install times out behind a proxy', createEnv([row]), 1);
  const hit = (sc.results || [])[0];
  assert.ok(hit, `no hit for the probe lesson: ${JSON.stringify(sc).slice(0, 200)}`);
  assert.equal(hit.evidence_level, 'E3',
    'a lesson carrying its level in frontmatter must not answer with an empty trust field');
  assert.equal(hit.summary_plain, 'pip install times out behind a corporate proxy',
    'the plain fields come out of the same JSON and must survive the strip');
});

test('a row without any level still answers honestly', async () => {
  // Absent is fine; the failure being pinned is "present and blank while a value exists elsewhere".
  const row = {
    id: 'trust-field-absent',
    title: 'pip install times out behind a corporate proxy again',
    domain: 'python',
    path: 'lessons/contrib/trust-field-absent.md',
    status: 'published',
    preview: 'A lesson that declares no evidence level at all.',
  };
  const sc = await search('pip install times out behind a corporate proxy again', createEnv([row]), 1);
  const hit = (sc.results || [])[0];
  assert.ok(hit, 'no hit for the probe lesson');
  assert.equal(hit.evidence_level, '', 'nothing to report, and nothing invented');
});

// ── the D1 path, which is the one production actually reads ──────────────────
//
// The two tests above seed the *snapshot* path (`proxy:lessons` in KV). Every mutation of the D1
// projection survived them — including deleting the line that lifts `evidence_level` onto the row —
// which is exactly how #2080 stayed open while its own tests were green: the storage had the value,
// the fetch selected the column, the fallback existed, and the projection dropped it on the last hop.
// These two pin the hop.

const D1_ROW = {
  id: 'trust-d1-probe',
  title: 'pip install times out behind a proxy',
  domain: 'python',
  status: 'published',
  tags: '["pip"]',
  path: 'lessons/contrib/trust-d1-probe.md',
  summary: 'pip install hangs and then times out behind a corporate proxy',
  problem: 'pip install hangs behind a corporate proxy and then fails with a read timeout',
  root_cause: 'the index-url is unreachable from inside the network',
  solution: 'point pip at the internal mirror and raise the timeout',
  verification: 'pip install returns within a second',
  updated: new Date().toISOString().slice(0, 10),
  created: '2026-09-01',
  // The shape the sync writes: the level is *derived* into the stored JSON, not a column.
  frontmatter: JSON.stringify({
    evidence_level: 'E3',
    summary_plain: 'pip install times out behind a corporate proxy',
    trigger: 'pip install hang',
    verify: 'pip install returns',
  }),
};

function createD1Env(row = D1_ROW) {
  invalidateBM25Memo();
  return {
    MCP_TOKEN: TOKEN,
    MCP_VERSION: 'index-and-trust-d1',
    MISAKANET_D1: {
      prepare(sql) {
        const stmt = {
          bind() { return stmt; },
          async all() { return { results: /FROM lessons/i.test(sql) ? [row] : [] }; },
          async run() { return { success: true }; },
        };
        return stmt;
      },
    },
  };
}

test('the D1 row projection lifts the trust field and the plain fields', async () => {
  const sc = await search('pip install times out behind a proxy', createD1Env(), 1);
  const hit = (sc.results || [])[0];
  assert.ok(hit, `no hit for the D1 probe lesson: ${JSON.stringify(sc).slice(0, 240)}`);
  assert.equal(hit.evidence_level, 'E3',
    'the level is inside the stored frontmatter; a projection that drops the JSON must lift it first');
  assert.equal(hit.summary_plain, 'pip install times out behind a corporate proxy');
});

test('the listing serves the same field and does not ship the raw frontmatter', async () => {
  const res = await worker.fetch(new Request('https://misakanet.org/api/lessons'), createD1Env());
  const rows = await res.json();
  const row = rows.find((r) => r.id === 'trust-d1-probe');
  assert.ok(row, `the D1 row must be listed: ${JSON.stringify(rows).slice(0, 200)}`);
  assert.equal(row.evidence_level, 'E3');
  assert.equal(row.summary_plain, 'pip install times out behind a corporate proxy');
  assert.equal('frontmatter' in row, false,
    'the raw JSON is internal — a 411-row listing must not carry 411 copies of it');
});
