// One bench, two floors: English 20 and CJK 22, and no change ships if either drops (issue #2357).
//
// WHY ONE FILE. Every previous attempt at CJK recall was judged on the Chinese side alone, and the
// parent issue (#2250) is a record of what that cost: four designs were built and all four *regressed
// English*, the worst taking the Chinese top-3 from 9/20 to 2/20 while English positives fell 13/15 →
// 4/15. A CJK-only bench cannot see that trade, and a CJK-only gate cannot stop it. So the two sets
// live here together and are asserted against one corpus in one run, which makes "the English floor
// did not move" a property of this file rather than a promise in a PR description.
//
// The measured floors below are what `data/lessons.json` at **418 rows** answers today (2026-09-28),
// through the real MCP handler, with alias expansion on (the production default):
//
//   language   rows   top-1   top-3
//   English     20    16/20   19/20
//   CJK         22     6/22   11/22
//
// Both are *floors*, not equalities: the corpus grows, and a row that moves reds this gate only when
// recall actually drops. Raising a floor is how an improvement is recorded — the CJK numbers are
// expected to rise when #2355/#2356 land, and that is the point of writing them down now. Lowering one
// means accepting less than the code did on 2026-09-28, so it needs a reason in the commit message.
//
// The CJK set is `scripts/eval_query_aliases.py`'s twenty questions (the corpus's own measure of the
// Chinese gap, and the set `workers/search-cjk-recall.test.mjs` already pins) plus two bare
// two-character words, which #2357 asks for by name. "The corpus answers this query" is the property
// under test, not which of two good lessons ranks first, so `expected` lists every acceptable lesson
// and a hit is "any of them in the top 3".
//
// The English set is `data/regression_queries.json` (minus its one row with no expected lesson — see
// `tests/test_search_floor_queries_schema.py`), the four positives from
// `workers/relevance-floor-calibration.test.mjs`, and six added here, three of which are **body-only**:
// their distinguishing token appears in the lesson *body* and in no title anywhere, so an
// implementation that matches titles only fails on them.
//
// Run: node --test workers/search-dual-floor.test.mjs
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import worker, { buildBM25Index, BM25_INDEX_KEY } from './register-proxy-sw.js';
import { testToken } from './_test-token.mjs';

// Exported so the schema test and this file cannot disagree about which corpus these numbers describe.
export const MEASURED_ON = '2026-09-28, data/lessons.json at 418 rows';
export const EN_FLOOR = { hit1: 16, hit3: 19 };
export const ZH_FLOOR = { hit1: 6, hit3: 11 };

export const QUERIES = readFileSync(new URL('../data/search-floor-queries.jsonl', import.meta.url), 'utf8')
  .split('\n')
  .filter((line) => line.trim())
  .map((line) => JSON.parse(line));

const CORPUS = JSON.parse(readFileSync(new URL('../data/lessons.json', import.meta.url), 'utf8'))
  .map((l) => ({
    id: l.id, title: l.title || '', domain: l.domain || '', tags: l.tags || [], path: l.url || '',
    description: (l.summary || '').slice(0, 400),
    indexText: `${l.summary || ''} ${l.preview || ''}`.slice(0, 6000),
  }));

function createEnv() {
  const store = new Map([
    [BM25_INDEX_KEY, JSON.stringify(buildBM25Index(CORPUS))],
    ['proxy:lessons', JSON.stringify({ ts: Date.now(), data: CORPUS })],
  ]);
  return {
    MCP_TOKEN: 'mcp_' + testToken('dual-floor'),
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

const env = createEnv();
let ip = 0;

async function search(query) {
  ip += 1;
  const response = await worker.fetch(new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${env.MCP_TOKEN}`, 'Content-Type': 'application/json',
      'MCP-Protocol-Version': '2025-06-18', 'Origin': 'https://misakanet.org',
      'CF-Connecting-IP': `198.51.${Math.floor(ip / 200)}.${(ip % 200) + 1}`,
    },
    body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'tools/call',
      params: { name: 'misakanet_search', arguments: { query, top: 5 } } }),
  }), env);
  const body = await response.json();
  const payload = JSON.parse(body.result.content[0].text);
  return { ids: (payload.results || []).map((r) => r.id), noMatch: !!payload.no_match };
}

const RESULTS = [];
for (const row of QUERIES) {
  const { ids, noMatch } = await search(row.query);
  const rank = ids.findIndex((id) => row.expected.includes(id));
  RESULTS.push({ ...row, ids, noMatch, hit1: rank === 0, hit3: rank >= 0 && rank < 3, rank: rank === -1 ? null : rank + 1 });
}

function tally(language) {
  const rows = RESULTS.filter((r) => r.language === language);
  return {
    rows,
    total: rows.length,
    hit1: rows.filter((r) => r.hit1).length,
    hit3: rows.filter((r) => r.hit3).length,
    missed: rows.filter((r) => !r.hit3),
  };
}

const EN = tally('en');
const ZH = tally('zh');

// Printed on every run: the pair is the point, and a number nobody sees is a number nobody checks.
console.log('search floor bench — ' + MEASURED_ON);
console.log(`  English  hit1 ${EN.hit1}/${EN.total}  hit3 ${EN.hit3}/${EN.total}  (floors ${EN_FLOOR.hit1}/${EN_FLOOR.hit3})`);
console.log(`  CJK      hit1 ${ZH.hit1}/${ZH.total}  hit3 ${ZH.hit3}/${ZH.total}  (floors ${ZH_FLOOR.hit1}/${ZH_FLOOR.hit3})`);
for (const row of RESULTS) {
  if (row.hit1) continue;
  console.log(`  ${row.hit3 ? 'top3 ' : row.noMatch ? 'NONE ' : 'MISS '} [${row.language}/${row.shape}] ${row.query}`);
  console.log(`         got ${JSON.stringify(row.ids.slice(0, 3))} want ${JSON.stringify(row.expected)}`);
}

function floorMessage(language, label, got, want, missed) {
  return `${language} ${label} recall is ${got}, below the floor of ${want} measured on ${MEASURED_ON}. `
    + 'A drop is the whole reason this file carries both languages: a CJK change that buys Chinese '
    + 'recall with English recall fails here by construction (#2250 records four designs that did '
    + `exactly that). Still missing: ${missed.map((r) => `"${r.query}"`).join(' | ')}`
    + (language === 'English'
      ? '. `encoding bug Python` has missed at every threshold since the set was written, so it is a '
        + 'known corpus/ranking gap: raise this floor only with a measurement, and never lower it to '
        + 'make a change green.'
      : '.');
}

test('the English floor does not drop', () => {
  assert.ok(EN.hit1 >= EN_FLOOR.hit1, floorMessage('English', 'top-1', EN.hit1, EN_FLOOR.hit1, EN.rows.filter((r) => !r.hit1)));
  assert.ok(EN.hit3 >= EN_FLOOR.hit3, floorMessage('English', 'top-3', EN.hit3, EN_FLOOR.hit3, EN.missed));
});

test('the CJK floor does not drop', () => {
  assert.ok(ZH.hit1 >= ZH_FLOOR.hit1, floorMessage('CJK', 'top-1', ZH.hit1, ZH_FLOOR.hit1, ZH.rows.filter((r) => !r.hit1)));
  assert.ok(ZH.hit3 >= ZH_FLOOR.hit3, floorMessage('CJK', 'top-3', ZH.hit3, ZH_FLOOR.hit3, ZH.missed));
});

test('both sets were actually run — a floor over an empty set cannot fail', () => {
  assert.ok(EN.total >= 20, `the English set has ${EN.total} rows, expected 20`);
  assert.ok(ZH.total >= 20, `the CJK set has ${ZH.total} rows, expected 20`);
  const shapes = new Set(QUERIES.map((r) => r.shape));
  for (const shape of ['latin', 'body-only', 'cjk', 'mixed', 'two-char']) {
    assert.ok(shapes.has(shape), `the bench no longer covers the "${shape}" shape (#2357 asks for it)`);
  }
});

test('a body-only query is answered from the body, not the title', () => {
  // The three `body-only` rows are the reason a title-only matcher cannot pass this bench: their
  // distinguishing token occurs in the lesson's body and in no title anywhere. The schema test proves
  // that about the corpus; this asserts the search actually uses it.
  for (const row of RESULTS.filter((r) => r.shape === 'body-only')) {
    assert.ok(row.hit3, `"${row.query}" (token ${JSON.stringify(row.body_only_token)}) is not found: `
      + `got ${JSON.stringify(row.ids.slice(0, 3))}, want ${JSON.stringify(row.expected)}`);
  }
});
