// The two channels, fused — and the confidently-wrong answer that started all of this (#2356, #2358).
//
// THE CASE. Measured on production MCP (2026-09-27):
//
//   `wsl2 landlock 文件系统沙箱` → `chrome-relay-browser-automation`, a completely unrelated lesson.
//
// The Chinese half contributed no term statistics at all, so two Latin tokens (`wsl2`, `landlock`)
// decided the answer; the lesson it returned is about browser automation in WSL2, which is what "wsl2"
// finds. A confidently wrong answer is worse than `no_match`, which is what #2358 exists to pin. The
// corpus has no landlock lesson at all today, so on the real corpus the honest outcome is `no_match` —
// the shape is only reproducible with a fixture, which is exactly what #2358's acceptance asks for
// ("use a fixture corpus with the two lessons needed to reproduce the shape").
//
// HOW THIS FILE TESTS IT. Three fixture lessons: one that mentions the query in both scripts (the
// correct answer), one decoy that matches only the Latin half, and one unrelated lesson. The decoy is
// the shape of the failure, not a strawman: it is the lesson production actually returned.
//
// The fusion rules it checks are #2356's, stated in `register-proxy-sw.js` next to `rankCjkChannel`:
// each channel is ranked and floored inside its own term space (no IDF arithmetic across two maps), and
// the two rankings are combined by Reciprocal Rank Fusion — positions, never scores. A document that
// matches both channels therefore gets two contributions and beats one that matches one channel, which
// is the property that fixes the motivating query: the landlock lesson matches `wsl2`/`landlock` *and*
// five bigrams, the decoy matches `wsl2` alone.
//
// Run: node --test workers/search-cjk-fusion.test.mjs
import assert from 'node:assert/strict';
import { cpSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { testToken } from './_test-token.mjs';
import { fuseRankings } from './register-proxy-sw.js';

const WORKER = new URL('./register-proxy-sw.js', import.meta.url);
const SOURCE = readFileSync(WORKER, 'utf8');
const ANCHOR = /function cjkBigrams\(text\) \{/;
assert.ok(ANCHOR.test(SOURCE), 'cjkBigrams() is gone or renamed — the fusion is built on it');

const CORPUS = [
  {
    id: "landlock-sandbox-lesson",
    title: "wsl2 landlock 文件系统沙箱无法启动",
    domain: "linux",
    tags: ["wsl2", "landlock"],
    description: "在 wsl2 里启用 landlock 文件系统沙箱后进程无法启动，要检查内核支持与挂载选项。",
    indexText: "wsl2 landlock 文件系统沙箱无法启动 launch fails checking kernel support 内核支持 mount options 挂载选项。",
  },
  {
    // The decoy is the lesson production returned for this query: WSL2 browser automation, no sandbox.
    id: "decoy-browser-relay",
    title: "Chrome Relay 浏览器自动化 in WSL2",
    domain: "automation",
    tags: ["chrome", "wsl2"],
    description: "在 WSL2 或 Linux 下用 Chrome Relay 控制无头浏览器（CDP over WebSocket）。",
    indexText: "Chrome Relay 浏览器自动化 无头浏览器 headless CDP over WebSocket in WSL2 linux 填表 发帖 截图 automation.",
  },
  {
    id: "unrelated-postgres",
    title: "PostgreSQL connection pool exhaustion",
    domain: "database",
    tags: ["postgres"],
    description: "Too many clients already when the pool is exhausted.",
    indexText: "PostgreSQL connection pool exhaustion Too many clients already fix max_connections pgbouncer.",
  },
];

/** A worker copy whose bigram channel is empty — the code as it was before #2356. */
function scratchWorkerWithoutTheChannel() {
  const dir = mkdtempSync(path.join(tmpdir(), 'cjk-fusion-'));
  cpSync(new URL('./lib', import.meta.url), path.join(dir, 'lib'), { recursive: true });
  const file = path.join(dir, 'worker-without-cjk.js');
  writeFileSync(file, SOURCE
    .replace(ANCHOR, 'function cjkBigramsOriginal(text) {')
    .replace('const CJK_CHAR = new RegExp', 'function cjkBigrams() { return []; }\nconst CJK_CHAR = new RegExp'));
  return file;
}

function createEnv(module, { aliases = true, corpus = CORPUS } = {}) {
  // The worker memoises the index in-isolate (that is what `invalidateBM25Memo` is for), and a test that
  // drives the same module with two different corpora would otherwise read the first one's index — which
  // is how this file's English-query test first "failed": the second build answered from the real corpus
  // loaded by the test above it.
  if (typeof module.invalidateBM25Memo === 'function') module.invalidateBM25Memo();
  const lessons = corpus.map((l) => ({ ...l, status: 'published' }));
  const store = new Map([
    [module.BM25_INDEX_KEY, JSON.stringify(module.buildBM25Index(lessons))],
    ['proxy:lessons', JSON.stringify({ ts: Date.now(), data: lessons })],
  ]);
  return {
    MCP_TOKEN: 'mcp_' + testToken('cjk-fusion'),
    // The alias table rewrites Chinese questions into English words. Turning it off is what isolates the
    // *channel*: with expansion on, an English hit could be the table's doing, and this file is about
    // the path where nothing but the bigrams can answer (see `cjkRanked` in the worker). Unset keeps
    // expansion on, which is the production default.
    ...(aliases ? {} : { MISAKANET_QUERY_ALIASES: '0' }),
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

async function search(worker, env, query, top = 3) {
  const response = await worker.fetch(new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${env.MCP_TOKEN}`, 'Content-Type': 'application/json',
      'MCP-Protocol-Version': '2025-06-18', 'Origin': 'https://misakanet.org',
      'CF-Connecting-IP': '198.51.100.77',
    },
    body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'tools/call',
      params: { name: 'misakanet_search', arguments: { query, top } } }),
  }), env);
  const body = await response.json();
  const payload = JSON.parse(body.result.content[0].text);
  return { ids: (payload.results || []).map((r) => r.id), noMatch: !!payload.no_match };
}

// The two builds: the real worker, and a copy whose `cjkBigrams` returns nothing (the pre-#2356 code
// path). Both expose the same API, so a test can drive either one through the same handler.
const withChannelModule = await import(WORKER.href);
const withoutChannelModule = await import(scratchWorkerWithoutTheChannel());
const withChannel = withChannelModule.default;
const withoutChannel = withoutChannelModule.default;

test('a CJK-only query is answered by the channel alone', async () => {
  const env = createEnv(withChannelModule, { aliases: false });
  const { ids, noMatch } = await search(withChannel, env, "文件系统沙箱");
  assert.ok(!noMatch, 'the channel did not answer a query with no Latin token at all');
  assert.equal(ids[0], 'landlock-sandbox-lesson', `wrong lesson first: ${JSON.stringify(ids)}`);
});

test('the query that motivated this returns the right lesson, never the decoy', async () => {
  const env = createEnv(withChannelModule);
  const { ids } = await search(withChannel, env, "wsl2 landlock 文件系统沙箱");
  assert.equal(ids[0], 'landlock-sandbox-lesson',
    `the confidently-wrong lesson is back at the top: ${JSON.stringify(ids)}`);
  assert.ok(!ids.includes('decoy-browser-relay'),
    `the decoy (WSL2 browser automation) is still in the answer: ${JSON.stringify(ids)}`);
});

test('a higher share of the query outranks a lower one at the same rank', async () => {
  // The ordering rule the fusion uses, on a fixture: two documents that both match the CJK channel at
  // rank 1 are impossible, but two that match *different shares* of the query are not — and the one that
  // accounts for more of what the user typed must come first. Here that order is the channel's own BM25
  // ranking (one channel, so the fusion cannot reorder it); the fusion never compares a share from this
  // channel with a share from the English one — see the test below.
  const env = createEnv(withChannelModule, { aliases: false });
  const { ids } = await search(withChannel, env, "文件系统沙箱", 3);
  assert.equal(ids[0], 'landlock-sandbox-lesson',
    `the lesson that carries the whole query is not first: ${JSON.stringify(ids)}`);
});

test('a coverage ratio from two different term spaces does not decide the fusion', () => {
  // The recorded failure (docs/benchmarks/hit1-misses-2026-10-30.md, verdict 3): the fusion weighted each
  // channel's vote by `covered`, a share of *that channel's* query terms. The two channels expand one CJK
  // query to very different term counts — here 2 English words and 9 bigrams — so the denominators are
  // not comparable, and a lesson that matched both English words (1.00) beat the lesson that is the
  // answer while the latter matched 3 of the 9 bigrams (0.33).
  //
  // The shape below distils that row: the answer is rank 1 in BOTH channels (2 of 2 English words, 3 of
  // 9 bigrams) and a decoy is rank 2 in both. The decoy wins nothing on position, yet the old weight
  // promoted it on 4/9 = 0.44 > 3/9 = 0.33, i.e. the fusion contradicted both channels. Rank fusion
  // reads the ranks, which agree.
  const answer = { doc: { id: 'feishu-gateway-drops-messages' } };
  const decoy = { doc: { id: 'feishu-setup-complete-cc-connect' } };
  const english = [
    { ...answer, score: 4.10, userScore: 4.10, covered: 2 / 2 },
    { ...decoy, score: 3.90, userScore: 3.90, covered: 2 / 2 },
  ];
  const cjk = [
    { ...answer, score: 6.20, covered: 3 / 9 },
    { ...decoy, score: 5.80, covered: 4 / 9 },
  ];
  assert.deepEqual(fuseRankings(english, cjk).map((entry) => entry.doc.id),
    ['feishu-gateway-drops-messages', 'feishu-setup-complete-cc-connect'],
    'a per-channel coverage ratio outvoted both channels\' own top hit');
});

test('a document matching both channels outranks one matching a single channel', async () => {
  // The mechanical property RRF buys, in isolation: the landlock lesson matches `wsl2`/`landlock` *and*
  // five bigrams; the decoy matches `wsl2` alone. Two contributions beat one, with no weight to tune and
  // no comparison between a bigram score and an English one.
  const env = createEnv(withChannelModule);
  const { ids } = await search(withChannel, env, "wsl2 landlock 文件系统沙箱", 3);
  const decoyRank = ids.indexOf('decoy-browser-relay');
  assert.ok(decoyRank === -1 || decoyRank > 0,
    `a single-channel match outranked a two-channel one: ${JSON.stringify(ids)}`);
});

test('an English query is untouched by the channel', async () => {
  // The whole point of a separate namespace: for a query with no CJK the channel has no postings, so the
  // answer must be the same list in the same order from both builds. (The floors are the corpus-wide
  // version of this check — `workers/search-dual-floor.test.mjs` — and they are unchanged.)
  const query = "postgres connection pool exhaustion";
  const after = await search(withChannel, createEnv(withChannelModule), query);
  const before = await search(withoutChannel, createEnv(withoutChannelModule), query);
  assert.deepEqual(after, before, 'the CJK channel moved an English query');
  assert.equal(after.ids[0], 'unrelated-postgres');
});
