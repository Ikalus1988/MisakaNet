// The retrieval half of `scripts/bench_relevance_separation.py` (#2790).
//
// WHY THIS FILE EXISTS SEPARATELY. The measurement has to go through the worker's real
// search path — `misakanet_search` over the MCP handler, with the index the worker builds
// itself — because the whole point of #2790 is that the retrieval layer is *holding* the
// score and not using it. Scoring offline with a re-implementation would measure the
// re-implementation. So Node runs the query and Python prints, rather than one language
// doing both badly.
//
// ONE INDEX PER PROCESS. `_bm25Index` is memoised at module scope in
// `register-proxy-sw.js`, so a second corpus in the same process silently reuses the first
// — `search-dual-floor.test.mjs`'s header calls this out for exactly this reason. This
// file therefore builds one index and answers every query against it.
//
// Prints JSON on stdout; diagnostics go to stderr so `--json` consumers are not polluted.
//
// EXCEPT the worker's own request log: `register-proxy-sw.js:6899` logs one JSON line per
// request to **stdout**, unconditionally, as issue #1347 asks. It is not silenced here — that
// log is production behaviour and a measurement must not change the thing it measures. So the
// payload is written to fd 3 when that descriptor exists, and the Python side reads from it;
// stdout stays reserved for the worker.
const emit = (obj) => {
  const text = JSON.stringify(obj, null, 2);
  if (process.env.SCORE_SEPARATION_FD) {
    writeSync(Number(process.env.SCORE_SEPARATION_FD), text);
  } else {
    process.stdout.write(text);
  }
};
import { readFileSync, writeSync } from 'node:fs';
import worker, { buildBM25Index, BM25_INDEX_KEY, indexShapeProblem } from './register-proxy-sw.js';
import { testToken } from './_test-token.mjs';

const REPO = new URL('..', import.meta.url);

const CORPUS = JSON.parse(readFileSync(new URL('data/lessons.json', REPO), 'utf8')).map((l) => ({
  id: l.id,
  title: l.title || '',
  domain: l.domain || '',
  tags: l.tags || [],
  path: l.url || '',
  description: (l.summary || '').slice(0, 400),
  indexText: `${l.summary || ''} ${l.preview || ''}`.slice(0, 6000),
}));

const RELEVANT = [
  ['SRVO-002 position error servo', 'fanuc-alarm-severity-guide'],
  ['servo following error tuning', 'fanuc-alarm-severity-guide'],
  ['SRVO-001 unexpected servo stop', 'fanuc-alarm-severity-guide'],
  ['TEACH pendant position error FANUC', 'fanuc-alarm-severity-guide'],
  ['pipe install timeout behind proxy', null],
  ['EADDRINUSE port already allocated', null],
];

const IRRELEVANT = [
  ['following error', null],
  ['how do I calibrate a Fuji tactile sensor', null],
  ['best breakfast recipe for oats', null],
  ['帮我把冰箱门关上', null],
  ['quarterly revenue forecast spreadsheet', null],
  ['how do I train for a marathon in 8 weeks', null],
];

const index = buildBM25Index(CORPUS);

// The shape of the index is part of the reading. §52 of the handoff measured that an index
// built in-process from `data/lessons.json` passes the worker's own `indexShapeProblem`
// gate (#2079) and sits within 10% of production's average document length — but only if the
// shape is printed next to the scores, so nobody reads these numbers as production's.
//
// `indexShapeProblem(index, lessons)` returns a **string** naming the defect, or a falsy value
// when the index is publishable. It is the same call `register-proxy-sw.js:2340` makes before
// it will serve a refreshed index, so calling it here measures the thing the worker measures.
const shapeProblem = indexShapeProblem(index, CORPUS);

const docLens = CORPUS.map((l) => (l.indexText || '').length);
const avgDocLen = docLens.reduce((a, b) => a + b, 0) / (docLens.length || 1);

const store = new Map([
  [BM25_INDEX_KEY, JSON.stringify(index)],
  ['proxy:lessons', JSON.stringify({ ts: Date.now(), data: CORPUS })],
]);

const env = {
  MCP_TOKEN: 'mcp_' + testToken('score-separation'),
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

async function ask(query) {
  ip += 1;
  const response = await worker.fetch(
    new Request('https://misakanet.org/mcp', {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${env.MCP_TOKEN}`,
        'Content-Type': 'application/json',
        'MCP-Protocol-Version': '2025-06-18',
        Origin: 'https://misakanet.org',
        'CF-Connecting-IP': `198.51.${Math.floor(ip / 200)}.${(ip % 200) + 1}`,
      },
      body: JSON.stringify({
        jsonrpc: '2.0', id: 1, method: 'tools/call',
        // detail:"full" is the only shape that carries scores; the default view's silence
        // about them is the second half of #2790, so the measurement has to ask for them.
        params: { name: 'misakanet_search', arguments: { query, top: 3, detail: 'full' } },
      }),
    }),
    env,
  );
  const body = await response.json();
  const payload = JSON.parse(body.result.content[0].text);
  const rows = payload.hits || payload.results || payload.lessons || [];
  const scored = rows
    .map((r) => ({ id: r.id, score: typeof r.score === 'number' ? r.score : Number(r.score) }))
    .filter((r) => Number.isFinite(r.score));
  return {
    id: payload.id ?? null,
    top1: scored.length ? scored[0].score : 0,
    hitId: scored.length ? scored[0].id : null,
    hitIds: scored.map((r) => r.id),
    rows: scored.length,
    voice: payload.voice ?? payload.status ?? null,
  };
}

async function rowsFor(list) {
  const out = [];
  for (const [query, expected] of list) {
    const r = await ask(query);
    out.push({ query, expected, top1: r.top1, hitId: r.hitId, hitIds: r.hitIds, voice: r.voice });
  }
  return out;
}

const only = process.argv.includes('--only') ? process.argv[process.argv.indexOf('--only') + 1] : null;

const out = {
  indexShape: {
    rows: CORPUS.length,
    docs: index.docs ? index.docs.length : null,
    terms: index.terms ? Object.keys(index.terms).length : (index.postings ? Object.keys(index.postings).length : null),
    avgDocLen: Number(avgDocLen.toFixed(1)),
    problem: shapeProblem || null,
  },
  relevant: only === 'irrelevant' ? [] : await rowsFor(RELEVANT),
  irrelevant: only === 'relevant' ? [] : await rowsFor(IRRELEVANT),
};

emit(out);
