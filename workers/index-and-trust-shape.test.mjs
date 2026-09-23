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
import worker, { buildBM25Index, indexShapeProblem } from './register-proxy-sw.js';
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
    frontmatter: JSON.stringify({ evidence_level: 'E3', provenance: { source: 'intake' } }),
  };
  const sc = await search('pip install times out behind a proxy', createEnv([row]), 1);
  const hit = (sc.results || [])[0];
  assert.ok(hit, `no hit for the probe lesson: ${JSON.stringify(sc).slice(0, 200)}`);
  assert.equal(hit.evidence_level, 'E3',
    'a lesson carrying its level in frontmatter must not answer with an empty trust field');
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
