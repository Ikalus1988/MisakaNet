// The relevance floor is evaluated in ONE term space — and the confidently-wrong answer of #2358.
//
// THE CASE, as measured on production MCP (2026-09-27, recorded on #2358):
//
//   `wsl2 landlock 文件系统沙箱` → `chrome-relay-browser-automation`, a completely unrelated lesson
//   (WSL2 headless-browser automation, top hit) while the corpus has no landlock lesson at all.
//
// #2356 answered the *ranking* half of that (a bigram channel, fused by rank). This file pins the other
// half, which is a floor defect and lives on the English path — the path a mixed query takes when the
// bigram channel has nothing to say.
//
// THE MECHANISM, measured on the real corpus (`data/lessons.json`, 418 rows) by instrumenting
// `searchLessonsBM25` for exactly this query:
//
//   floorTerms  = ['wsl2', 'landlock']          ← what the user typed (`bm25Tokenize` erases CJK runs)
//   queryTerms  = ['wsl2', 'landlock', 'sandbox'] ← …plus what the alias table guessed (沙箱 → sandbox)
//   idfTotal          = 9.966                   ← idf(wsl2) + idf(landlock); landlock is absent from
//                                                 the corpus, so it counts as maximally rare
//   matchedIdf[decoy] = 6.747                   ← idf(wsl2) + idf(sandbox): the *expansion* supplied
//                                                 mass the denominator never contained
//   ratio             = 0.677 ≥ RELEVANCE_MIN_COVERAGE (0.55)  → admitted, i.e. the answer
//
// Counted from `floorTerms` — the terms `floor.required` and `idfTotal` are computed from — the decoy is
// 3.235/9.966 = 0.325 and the floor refuses it, which is what it was written to do. That is the fix: the
// numerator and the denominator of the floor now come from the same set of words. `rankCjkChannel`
// already had this property (it floors over exactly the query's bigrams it can match), which is why the
// bigram channel was never the source of this answer.
//
// HOW THIS FILE TESTS IT. A fixture corpus, per #2358's acceptance criteria, and deliberately free of
// CJK: with no bigrams in any document the channel has no postings, so the English path alone decides and
// the assertion is about the floor rather than about the fusion. The decoy is the shape of the lesson
// production returned — it matches `wsl2` and the *guessed* `sandbox`, never `landlock`.
//
// Run: node --test workers/search-floor-term-space.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import { testToken } from './_test-token.mjs';

const WORKER = new URL('./register-proxy-sw.js', import.meta.url);
const worker = (await import(WORKER.href)).default;
const module = await import(WORKER.href);

/** Filler lessons: real enough to give the corpus term statistics, matching none of the query. */
const FILLER = Array.from({ length: 22 }, (_, i) => ({
  id: `filler-${i}`,
  title: `Service ${i} rotation runbook`,
  domain: 'ops',
  tags: ['ops'],
  description: `Rotating service ${i} credentials without downtime.`,
  indexText: `Rotating service ${i} credentials without downtime deploy rollout drain connection.`,
}));

// The decoy matches `wsl2` (typed) and `sandbox` (the alias table's guess for 沙箱) — never `landlock`.
const DECOY = {
  id: 'decoy-browser-relay',
  title: 'Chrome Relay browser automation in WSL2',
  domain: 'automation',
  tags: ['chrome', 'wsl2'],
  description: 'Drive a headless browser from WSL2 over CDP without installing one per environment.',
  indexText: 'Chrome Relay browser automation headless CDP over WebSocket in WSL2 linux sandbox form fill screenshot automation.',
};

// A second document carrying each of those two words, so both are ordinary terms rather than one-offs.
const WSL2_NEIGHBOUR = {
  id: 'wsl2-neighbour',
  title: 'WSL2 networking mode',
  domain: 'wsl',
  tags: ['wsl2'],
  description: 'Mirrored networking mode in WSL2 needs a restart of the VM.',
  indexText: 'WSL2 mirrored networking mode restart the vm host resolution.',
};
const SANDBOX_NEIGHBOUR = {
  id: 'sandbox-neighbour',
  title: 'A stubbed success is not a sandbox',
  domain: 'testing',
  tags: ['testing'],
  description: 'Tests that stub the danger away prove nothing about the sandbox.',
  indexText: 'A stubbed success is not a sandbox the test must exercise the real isolation boundary.',
};

// The lesson the corpus does *not* have today: the one that carries the words the user typed.
const LANDLOCK = {
  id: 'landlock-sandbox-lesson',
  title: 'Landlock filesystem sandbox in WSL2',
  domain: 'linux',
  tags: ['wsl2', 'landlock'],
  description: 'Landlock ruleset for a filesystem sandbox under WSL2, and the kernel support it needs.',
  indexText: 'Landlock filesystem sandbox ruleset under WSL2 fails to start check kernel support and mount options landlock.',
};

const WITHOUT_THE_LESSON = [DECOY, WSL2_NEIGHBOUR, SANDBOX_NEIGHBOUR, ...FILLER];
const WITH_THE_LESSON = [LANDLOCK, ...WITHOUT_THE_LESSON];

const QUERY = 'wsl2 landlock 文件系统沙箱';

function createEnv(corpus) {
  // The index is memoised per isolate (that is what `invalidateBM25Memo` is for), so two corpora in one
  // test process must not share one — this is how `workers/search-cjk-fusion.test.mjs` first "failed".
  module.invalidateBM25Memo();
  const lessons = corpus.map((l) => ({ ...l, status: 'published' }));
  const store = new Map([
    [module.BM25_INDEX_KEY, JSON.stringify(module.buildBM25Index(lessons))],
    ['proxy:lessons', JSON.stringify({ ts: Date.now(), data: lessons })],
  ]);
  return {
    MCP_TOKEN: 'mcp_' + testToken('floor-term-space'),
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

async function search(env, query, top = 3) {
  const response = await worker.fetch(new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${env.MCP_TOKEN}`, 'Content-Type': 'application/json',
      'MCP-Protocol-Version': '2025-06-18', 'Origin': 'https://misakanet.org',
      'CF-Connecting-IP': '198.51.100.88',
    },
    body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'tools/call',
      params: { name: 'misakanet_search', arguments: { query, top } } }),
  }), env);
  const payload = JSON.parse((await response.json()).result.content[0].text);
  return { ids: (payload.results || []).map((r) => r.id), noMatch: !!payload.no_match };
}

test('a match on the alias expansion alone is not an answer', async () => {
  // The measured production shape: no lesson carries `landlock`, the decoy carries `wsl2` and the guessed
  // `sandbox`, and the floor used to count that guess as information. Admitting it means the API answers a
  // question about filesystem sandboxes with a lesson about driving a browser — worse than `no_match`.
  const { ids, noMatch } = await search(createEnv(WITHOUT_THE_LESSON), QUERY);
  assert.ok(!ids.includes('decoy-browser-relay'),
    `a lesson matching only the alias expansion was returned: ${JSON.stringify(ids)}`);
  assert.ok(noMatch, `expected no_match for a query the corpus cannot answer, got ${JSON.stringify(ids)}`);
});

test('the control: the same query is answered when a lesson carries the typed words', async () => {
  // A floor that refuses everything is not a fix. This is the same corpus plus the one lesson that
  // matches `wsl2` *and* `landlock`; it must still be found, and the decoy must still be absent.
  const { ids } = await search(createEnv(WITH_THE_LESSON), QUERY);
  assert.equal(ids[0], 'landlock-sandbox-lesson', `wrong lesson first: ${JSON.stringify(ids)}`);
  assert.ok(!ids.includes('decoy-browser-relay'), `the decoy is in the answer: ${JSON.stringify(ids)}`);
});
