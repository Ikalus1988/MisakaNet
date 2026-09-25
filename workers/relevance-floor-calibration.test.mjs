// Re-derive the calibration behind `RELEVANCE_MIN_COVERAGE` — the constant's justification was prose.
//
// The comment above the constant said the floor was calibrated on "14 positive queries that must keep
// finding their lesson, 10 negative ones that must not", that "0.55 separates them cleanly — 14/14 and
// 10/10", that "0.45 already admits three negatives" and that "0.65 starts dropping positives". None of
// that was reproducible: the query sets were never committed, and the test written in the same commit
// asserted **4 positives and 5 negatives** (the commit message says so). So for months the one number
// that decides whether a search answers or reports `no_match` rested on a measurement nobody could
// re-run — which is also why the 2026-09-24 handoff listed "fix RELEVANCE_MIN_COVERAGE" as a candidate
// and the 2026-09-25 session found it could not be done safely: there was nothing to calibrate against.
//
// This file is that measurement, as a gate. It patches the constant, drives the real MCP handler over
// the real corpus, and counts three things across a sweep:
//
//   positives   the lesson that answers the query is admitted (top 5) — recall
//   negatives   a query the corpus cannot answer returns `no_match`      — precision
//   forbidden   an id listed in `forbidden` for a query never appears    — precision, per query
//
// Positive queries are `data/regression_queries.json` (11, the repository's own high-signal set) plus
// the four from `workers/search-floor-real-corpus.test.mjs`; the negatives are that same test's five;
// the forbidden sets are `data/retrieval_noisebench_queries.json` (15).
//
// Measured 2026-09-25 against `data/lessons.json` at the 411 rows that were on `main` that day. **The
// corpus grows**, so the table is a record rather than a contract: the assertions below are floors and
// invariants, not equalities, and a row that moves reds the gate only when recall actually drops — at
// which point the table, `POSITIVE_FLOOR` and the comment above the constant are re-measured together.
//
//   threshold   positives   negatives-rejected   forbidden-clean
//     0.00        13/15           1/5                15/15   <- the coverage check can never fire here
//     0.20        13/15           2/5                15/15
//     0.30        13/15           3/5                15/15
//     0.45        13/15           3/5                15/15
//     0.50        13/15           4/5                15/15
//     0.55        13/15           5/5                15/15   <- the committed value
//     0.60        13/15           5/5                15/15
//     0.70        13/15           5/5                15/15
//     0.80        12/15           5/5                15/15
//
// What that says, including the part that is inconvenient:
//
//   * 0.55 is the smallest value that rejects every unanswerable query, and 0.80 starts costing recall
//     — so the constant is a real balance, not a guess, and both directions are asserted below;
//   * "0.65 starts dropping positives", the claim the old comment made, is **not true** of the query
//     sets that exist in this repository: positives survive to 0.70;
//   * the `forbidden` column is **invariant** across the whole sweep, including 0.00 where the floor is
//     off. It is pinned below as a real invariant and explicitly *not* as evidence about the constant;
//   * the two positives that miss (`encoding bug Python`, `MCP server setup error`) miss at every
//     threshold, so they are not floor-related at all — they are a ranking or corpus gap and belong to
//     a different ticket, not to this constant.
//
// Run: node --test workers/relevance-floor-calibration.test.mjs
import assert from 'node:assert/strict';
import { cpSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { testToken } from './_test-token.mjs';

const WORKER = new URL('./register-proxy-sw.js', import.meta.url);
const SOURCE = readFileSync(WORKER, 'utf8');
const ANCHOR = /const RELEVANCE_MIN_COVERAGE = ([\d.]+);/.exec(SOURCE);
assert.ok(ANCHOR, 'RELEVANCE_MIN_COVERAGE is no longer declared in the shape this test patches');
const COMMITTED = Number(ANCHOR[1]);

// The corpus the other retrieval tests use: `data/lessons.json` with the same projection
// (`summary` + `preview`), so a number here is comparable with a number there.
const CORPUS = JSON.parse(readFileSync(new URL('../data/lessons.json', import.meta.url), 'utf8'))
  .map((l) => ({
    id: l.id, title: l.title || '', domain: l.domain || '', tags: l.tags || [], path: l.url || '',
    description: (l.summary || '').slice(0, 400),
    indexText: `${l.summary || ''} ${l.preview || ''}`.slice(0, 6000),
  }));

const REGRESSION = JSON.parse(
  readFileSync(new URL('../data/regression_queries.json', import.meta.url), 'utf8')).queries;
const NOISEBENCH = JSON.parse(
  readFileSync(new URL('../data/retrieval_noisebench_queries.json', import.meta.url), 'utf8'));

// The four positives and the five negatives from workers/search-floor-real-corpus.test.mjs. Duplicated
// rather than imported: importing a test file would register its tests here as a side effect, and the
// alternative — moving them into a fixture — would change a file this gate does not own. If they move,
// this test is meant to be updated with them.
const INLINE_POSITIVES = [
  ['docker exit code 137', ['kubernetes-crashloopbackoff-debugging']],
  ['kubectl crashloopbackoff', ['kubernetes-crashloopbackoff-debugging']],
  ['pip install timeout corporate proxy', ['pip-install-proxy-timeout', 'instalacao-pip-timeout-proxy']],
  ['DCO sign-off missing', ['dco-auto-fix-workflow', 'ci-dco-fork-pr-signoff', 'dco-signoff-force-push-pitfall']],
];
const INLINE_NEGATIVES = [
  'how do I bake sourdough bread', 'best pizza in Rome tonight',
  'what is the capital of France', 'who won the match last night',
  'recipe for chocolate cake',
];

const POSITIVES = [
  ...INLINE_POSITIVES,
  ...REGRESSION.map((q) => [q.query, q.expected_lessons.map((p) => path.basename(p, '.md'))]),
];

// The measured floor. An improvement passes; a regression fails. `13/15` is what the corpus answers
// today and the two misses are named in the failure message so nobody has to re-derive which they are.
const POSITIVE_FLOOR = 13;

/** Run the whole set at one threshold, using a patched copy of the worker.
 *
 * Copies live in a scratch directory beside a copy of `lib/` — the worker dynamic-imports
 * `./lib/utils.js` and `./lib/handlers.js`, so a patched file in `os.tmpdir()` cannot be imported on
 * its own (the first version of this test tried, and failed with ERR_MODULE_NOT_FOUND).
 */
async function sweep(threshold, scratch) {
  const tag = String(threshold).replace('.', '_');
  const file = path.join(scratch, `worker-${tag}.js`);
  writeFileSync(file, SOURCE.replace(ANCHOR[0], `const RELEVANCE_MIN_COVERAGE = ${threshold};`), 'utf8');

  const mod = await import(file);
  const worker = mod.default;
  const store = new Map([
    [mod.BM25_INDEX_KEY, JSON.stringify(mod.buildBM25Index(CORPUS))],
    ['proxy:lessons', JSON.stringify({ ts: Date.now(), data: CORPUS })],
  ]);
  const env = {
    MCP_TOKEN: 'mcp_' + testToken('floor-sweep'),
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

  const positives = [];
  const missed = [];
  for (const [query, expected] of POSITIVES) {
    const { ids } = await search(query);
    if (ids.some((id) => expected.includes(id))) positives.push(query);
    else missed.push(query);
  }
  const admitted = [];
  for (const query of INLINE_NEGATIVES) {
    const { noMatch, ids } = await search(query);
    if (!noMatch) admitted.push(`${query} -> ${ids.slice(0, 2).join(',')}`);
  }
  const leaked = [];
  for (const row of NOISEBENCH) {
    const { ids } = await search(row.query);
    const bad = ids.filter((id) => (row.forbidden || []).includes(id));
    if (bad.length) leaked.push(`${row.query} -> ${bad.join(',')}`);
  }
  return {
    threshold, found: positives.length, total: POSITIVES.length, missed,
    admitted, negativesTotal: INLINE_NEGATIVES.length,
    leaked, forbiddenTotal: NOISEBENCH.length,
  };
}

function scratchDir() {
  const dir = mkdtempSync(path.join(tmpdir(), 'floor-sweep-'));
  cpSync(new URL('./lib', import.meta.url), path.join(dir, 'lib'), { recursive: true });
  return dir;
}

const scratch = scratchDir();
const LOOSER = 0.45;
const STRICTER = 0.80;
const atCommitted = await sweep(COMMITTED, scratch);
const atLooser = await sweep(LOOSER, scratch);
const atStricter = await sweep(STRICTER, scratch);

test('the committed threshold rejects every query the corpus cannot answer', () => {
  assert.deepEqual(atCommitted.admitted, [],
    `RELEVANCE_MIN_COVERAGE = ${COMMITTED} let ${atCommitted.admitted.length} of `
    + `${atCommitted.negativesTotal} unanswerable queries through: ${atCommitted.admitted.join(' | ')}. `
    + 'A document matching one corpus-wide word is not an answer (this is the defect the IDF-weighted '
    + 'floor replaced the previous one-term rule for).');
});

test('no forbidden lesson is returned for its own query — and this is NOT evidence about the threshold', () => {
  // Stated as a separate test with the honest label, because it was written as if the floor produced it
  // and measurement says otherwise. Sweeping the threshold from **0.00** (where `matchedIdf / idfTotal <
  // RELEVANCE_MIN_COVERAGE` can never be true, so the coverage check is off) through 0.80 leaves this
  // result at 15/15 unchanged — and so do two production mutations that were expected to move it:
  // disabling the coverage check leaks unanswerable queries (4 of 5) while leaving the forbidden column
  // at 15/15, and dropping the `!informative[i]` guard changes nothing at all. So the property holds
  // upstream of the floor, in scoring.
  //
  // The mechanism is deliberately *not* asserted here: the first version of this comment credited
  // `coverage < floor.required` and `!informative[i]`, and the mutation audit refuted the second half.
  // What is pinned is the observation, plus the fact that moving the constant cannot fail it — a gate
  // that looks like it tests the constant and does not is worse than no gate, because somebody will
  // eventually raise the constant and cite it as evidence.
  assert.deepEqual(atCommitted.leaked, [],
    `a lesson listed in \`forbidden\` for its own query was returned: ${atCommitted.leaked.join(' | ')}`);
  assert.equal(atCommitted.forbiddenTotal, NOISEBENCH.length, 'the forbidden sets went missing');
});

test('the threshold still finds the lessons the corpus can answer', () => {
  assert.ok(atCommitted.found >= POSITIVE_FLOOR,
    `positives dropped to ${atCommitted.found}/${atCommitted.total}, below the measured floor of `
    + `${POSITIVE_FLOOR}. Missed: ${atCommitted.missed.join(' | ')}. Either the corpus lost an answer it `
    + 'used to give, or the floor got stricter than the calibration supports — re-run the sweep in this '
    + "file's docstring and update both the floor and the comment above the constant.");
});

test('loosening the floor measurably costs precision — the constant is load-bearing', () => {
  // Without this direction the file would pass for a constant that does nothing. If a looser threshold
  // ever stops admitting negatives, the floor is no longer the thing keeping them out and the
  // calibration story above the constant needs rewriting rather than adjusting.
  assert.ok(atLooser.admitted.length >= 1,
    `at ${LOOSER} no unanswerable query was admitted, so the committed value is not what rejects them; `
    + 'the calibration in the comment above RELEVANCE_MIN_COVERAGE no longer describes this corpus');
});

test('tightening the floor measurably costs recall', () => {
  // The other half of the trade-off, and the reason the constant is not simply raised until precision is
  // perfect. Measured 2026-09-25: 0.80 drops one positive. If this stops being true, re-measure rather
  // than delete the assertion — it is the only evidence that the value is a balance and not a guess.
  assert.ok(atStricter.found < atCommitted.found,
    `tightening to ${STRICTER} cost no recall (${atStricter.found}/${atStricter.total}), so the sweep is `
    + 'not discriminating between thresholds — check that the patched copies are being imported at all');
});

test('the sweep is actually varying the constant', () => {
  // A guard against the whole file measuring one configuration three times: the three runs must not all
  // agree on everything, and the scratch copies must not be interchangeable.
  const fingerprint = (r) => JSON.stringify([r.found, r.admitted.length, r.leaked.length]);
  const prints = new Set([fingerprint(atCommitted), fingerprint(atLooser), fingerprint(atStricter)]);
  assert.ok(prints.size >= 2,
    `all three thresholds produced identical results (${[...prints][0]}), which means the patch did not `
    + 'take effect — this file would then be asserting nothing about the constant');
});
