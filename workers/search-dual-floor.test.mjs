// One bench, two floors: English 20 and CJK 22, and no change ships if either drops (issue #2357).
//
// WHY ONE FILE. Every previous attempt at CJK recall was judged on the Chinese side alone, and the
// parent issue (#2250) is a record of what that cost: four designs were built and all four *regressed
// English*, the worst taking the Chinese top-3 from 9/20 to 2/20 while English positives fell 13/15 →
// 4/15. A CJK-only bench cannot see that trade, and a CJK-only gate cannot stop it. So the two sets
// live here together and are asserted against one corpus in one run, which makes "the English floor
// did not move" a property of this file rather than a promise in a PR description.
//
// The floors below are what `data/lessons.json` at **418 rows** answers today (2026-09-28),
// through the real MCP handler, with alias expansion on (the production default):
//
//   language   rows   top-1   top-3
//   English     20    16/20   19/20   (unchanged by the CJK channel, #2356 — the floor is the same)
//   CJK         22    11/22   15/22   (was 6/22 and 11/22; the bigram channel and its fusion, #2355/#2356)
//
// Both are *floors*, not equalities: the corpus grows, and a row that moves reds this gate only when
// recall actually drops. Raising a floor is how an improvement is recorded — the CJK pair was raised
// from 6/22 and 11/22 on 2026-09-28, when the bigram channel (#2355) and its fusion (#2356) landed and
// the English pair did not move at all. That is the property this file exists for. Lowering one
// means accepting less than the code did on 2026-09-28, so it needs a reason in the commit message.
//
// Re-measured 2026-10-03 at 457 rows (#2762 merged 19 lessons since): English 16/20 · 19/20, CJK
// 11/22 · 16/22. The CJK top-3 is one above its floor, and the floor was deliberately NOT raised to
// meet it: that extra hit came from 19 unrelated lessons shifting the ranking, not from search getting
// better, and pinning a floor to a corpus size would hand the gate to unrelated churn. The top-1 sits
// exactly on its floor, so there is no headroom to record either way.
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
// The floors here are measured over the *repository* corpus. Production is a different corpus (426 rows
// in D1's `rich` projection when these floors were last raised, against `data/lessons.json`'s 418), so
// the live numbers legitimately differ: measured 2026-09-28 they were 13/20 · 18/20 and 11/22 · 14/22.
// `scripts/bench_production_recall.py` prints both sides at once. Never move these floors to match it —
// that deletes the measurement instead of the gap.
//
// The corpus here is the WHOLE file, drafts included, and that is deliberate (#2766). The search path
// does not filter on `status`: a draft lesson is served like any other, carrying a `status` marker
// because whether a draft should be retrievable at all is still open (#2270, see `lessonStatusMarker` in
// `register-proxy-sw.js`). Filtering this bench down to `published` would therefore measure a system
// that does not exist — measured 2026-10-03 it reads CJK 10/22 · 15/22 instead of 11/22 · 16/22, which
// is a number about a hypothetical, not about production. One row (zh-18) does depend on a draft
// lesson, and the guard below makes that dependency a recorded decision instead of an accident.
//
// One trap for anyone adding a second corpus-based bench to this file: the worker memoises the BM25
// index at MODULE scope (`_bm25Index` / `_bm25IndexExpiry` in `register-proxy-sw.js`). Two `env`s with
// two different corpora in one process do NOT get two measurements — the second silently reuses the
// first index, so a comparison like "full corpus vs published-only" reports the full corpus twice and
// the delta looks like zero. Measure one corpus per process.
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
export const ZH_FLOOR = { hit1: 11, hit3: 15 };

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

test('every expected answer names a real lesson, and none is listed twice', () => {
  // A guard on this data file, not on the ranking. `expected` is the set of answers the bench
  // will accept, which makes it the one place where "make the number go up" is available to
  // anyone editing a query. Three of the mechanical ways to do that are checkable: citing a slug
  // that does not exist, citing the same lesson twice so one answer looks like two, and parking
  // the only acceptable answer on a lesson the repository has not published.
  //
  // What this deliberately does NOT check is whether a real lesson actually answers the question.
  // That part is judgement, and no assertion can supply it. Read `note` on the row before
  // adding to `expected` — the one widening done here (zh-05, 2026-10-03) argues in its note why
  // the second lesson is a better answer to a generic query than the one it displaced.
  const rows = JSON.parse(
    readFileSync(new URL('../data/lessons.json', import.meta.url), 'utf8'));
  const ids = new Set(rows.map((l) => l.id));
  const statusById = new Map(rows.map((l) => [l.id, l.status]));
  for (const row of QUERIES) {
    assert.ok(row.expected.length > 0, `${row.id} lists no expected answer at all`);
    assert.equal(new Set(row.expected).size, row.expected.length,
      `${row.id} lists the same lesson more than once: ${row.expected.join(', ')}`);
    for (const id of row.expected) {
      assert.ok(ids.has(id), `${row.id} expects "${id}", which is not in the corpus`);
      // The third mechanical way to move the number (#2766). A draft lesson IS served by the
      // search path — it comes back with a `status` marker, because whether a draft should be
      // retrievable at all is still an open product question (#2270) and the worker makes the
      // fact visible rather than deciding it. So a non-published `expected` is legitimate, and
      // the danger is not the row but its *unrecorded* state: a draft can be published, renamed
      // or dropped by an editorial decision, and the quiet failure is somebody deleting the
      // query row to get the suite green. `ZH.total >= 20` below does not catch 22 becoming 21,
      // so the coverage would shrink with every test still passing. Requiring the note to name
      // the status turns that accident into a recorded decision: if you delete the lesson, this
      // failure now says which row lost its answer instead of leaving a smaller bench behind.
      const status = statusById.get(id);
      if (status && status !== 'published') {
        assert.ok(new RegExp(status, 'i').test(row.note || ''),
          `${row.id} expects "${id}", whose status is "${status}", but the row's note never says so. `
          + 'A non-published expected answer is allowed and is deliberate — the search path serves it, '
          + 'marked — but it must be written down: name the status in `note` and say what to do if the '
          + 'lesson is later published or removed.');
      }
    }
  }
});

test('both sets were actually run — a floor over an empty set cannot fail', () => {
  assert.ok(EN.total >= 20, `the English set has ${EN.total} rows, expected 20`);
  assert.ok(ZH.total >= 20, `the CJK set has ${ZH.total} rows, expected 20`);
  const shapes = new Set(QUERIES.map((r) => r.shape));
  for (const shape of ['latin', 'body-only', 'cjk', 'mixed', 'two-char']) {
    assert.ok(shapes.has(shape), `the bench no longer covers the "${shape}" shape (#2357 asks for it)`);
  }
});

test('the production-measured confidently-wrong answer is gone (#2358)', async () => {
  // The query #2358 records from production: on 2026-09-27 the MCP endpoint answered it with
  // `chrome-relay-browser-automation` — a lesson about driving a headless browser — because the two
  // Latin tokens decided it (the CJK half contributed no statistics). The corpus still has no landlock
  // lesson, so `no_match` is an honest answer here; an unrelated lesson is not. This is the case on the
  // *real* corpus, which the fixture in `workers/search-floor-term-space.test.mjs` cannot cover: there
  // the shape is reproduced in isolation, here it is pinned where it was measured.
  const { ids, noMatch } = await search('wsl2 landlock 文件系统沙箱');
  assert.ok(!ids.includes('chrome-relay-browser-automation'),
    `the unrelated WSL2 browser-automation lesson is back: ${JSON.stringify(ids)}`);
  if (noMatch) return;
  const top = CORPUS.find((l) => l.id === ids[0]);
  assert.ok(top, `the answer names a lesson the corpus does not have: ${ids[0]}`);
  assert.ok(['wsl', 'linux'].includes(top.domain),
    `the answer to a WSL2 filesystem-sandbox question is a ${top.domain} lesson: ${JSON.stringify(ids)}`);
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
