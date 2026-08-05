// Unit tests for the privacy-preserving unsolved failure map (Issue #788).
// Run: node --test workers/unsolved-map.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import worker, {
  UNSOLVED_FAMILY_WHITELIST,
  UNSOLVED_REASONS,
  buildUnsolvedMap,
  classifyTaskFamily,
  handleSearchSignal,
  handleUnsolvedMap,
  recordStaleLesson,
  recordUnsolvedSearch,
} from './register-proxy-sw.js';

function createFakeKV(seed = {}) {
  const store = new Map(Object.entries(seed));
  return {
    async get(key, type) {
      if (!store.has(key)) return null;
      const raw = store.get(key);
      return type === 'json' ? JSON.parse(raw) : raw;
    },
    async put(key, value) { store.set(key, value); },
    async delete(key) { store.delete(key); },
    async list({ prefix = '', cursor } = {}) {
      const keys = [...store.keys()].filter((k) => k.startsWith(prefix)).map((name) => ({ name }));
      return { keys, list_complete: true, cursor: cursor ?? null };
    },
    _store: store,
  };
}

const envWithKV = (seed) => ({ MISAKANET_KV: createFakeKV(seed) });

function signalRequest(body, headers = {}) {
  return new Request('https://misakanet.org/api/search-signal', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...headers },
    body: JSON.stringify(body),
  });
}

const daysAgo = (n) => new Date(Date.now() - n * 86_400_000).toISOString().slice(0, 10);

// ── Classification ─────────────────────────────────────────────────────────

test('queries are clustered into whitelisted task families', () => {
  assert.equal(classifyTaskFamily('sqlite database is locked on concurrent write'), 'database-lock');
  assert.equal(classifyTaskFamily('pip install ModuleNotFoundError'), 'python-env');
  assert.equal(classifyTaskFamily('npm publish EOTP one time password'), 'npm-publish');
  assert.equal(classifyTaskFamily('wrangler deploy failed on cloudflare'), 'cloudflare-worker');
  assert.equal(classifyTaskFamily('DCO sign-off missing'), 'github-auth');
  assert.equal(classifyTaskFamily('mcp server tools/list empty'), 'mcp-registry');
  assert.equal(classifyTaskFamily('UnicodeDecodeError gbk codec'), 'encoding-locale');
  assert.equal(classifyTaskFamily('kubernetes crashloopbackoff'), 'container-deploy');
});

test('unrecognised and empty queries fall back to unclassified', () => {
  assert.equal(classifyTaskFamily('why is the sky blue'), 'unclassified');
  assert.equal(classifyTaskFamily(''), 'unclassified');
  assert.equal(classifyTaskFamily(undefined), 'unclassified');
});

test('every derived family is on the published whitelist', () => {
  const queries = ['database locked', 'pip timeout', 'docker image', 'random words here'];
  for (const q of queries) assert.ok(UNSOLVED_FAMILY_WHITELIST.includes(classifyTaskFamily(q)));
});

// ── Aggregation ────────────────────────────────────────────────────────────

test('signals bucket by family, day and reason', async () => {
  const env = envWithKV();
  await recordUnsolvedSearch(env, { taskFamily: 'database-lock', reason: 'no_match' });
  await recordUnsolvedSearch(env, { taskFamily: 'database-lock', reason: 'no_match' });
  await recordUnsolvedSearch(env, { taskFamily: 'database-lock', reason: 'low_confidence' });
  await recordUnsolvedSearch(env, { taskFamily: 'python-env', reason: 'no_match' });

  const { families } = await buildUnsolvedMap(env);
  assert.deepEqual(families.map((f) => f.taskFamily), ['database-lock', 'python-env']);
  assert.equal(families[0].unsolved30d, 3);
  assert.deepEqual(families[0].reasons, { no_match: 2, low_confidence: 1 });
});

test('unknown families and reasons are normalised, never stored raw', async () => {
  const env = envWithKV();
  const recorded = await recordUnsolvedSearch(env, { taskFamily: 'made-up-family', reason: 'user typed this' });
  assert.equal(recorded.taskFamily, 'unclassified');
  assert.equal(recorded.reason, 'no_match');
  assert.ok(!JSON.stringify([...env.MISAKANET_KV._store.values()]).includes('user typed this'));
});

test('buckets older than the 30-day window are pruned and excluded', async () => {
  const env = envWithKV({
    'unsolved:family:python-env': JSON.stringify({
      days: { '2000-01-01': { reasons: { no_match: 99 } }, [daysAgo(2)]: { reasons: { no_match: 2 } } },
    }),
  });
  await recordUnsolvedSearch(env, { taskFamily: 'python-env', reason: 'no_match' });

  const { families } = await buildUnsolvedMap(env);
  assert.equal(families[0].unsolved30d, 3, 'ancient bucket must not count');
  assert.ok(!env.MISAKANET_KV._store.get('unsolved:family:python-env').includes('2000-01-01'));
});

test('7-day and 30-day windows are counted separately', async () => {
  const env = envWithKV({
    'unsolved:family:github-auth': JSON.stringify({
      days: { [daysAgo(20)]: { reasons: { no_match: 5 } }, [daysAgo(1)]: { reasons: { no_match: 2 } } },
    }),
  });
  const { families } = await buildUnsolvedMap(env);
  assert.equal(families[0].unsolved30d, 7);
  assert.equal(families[0].unsolved7d, 2);
  assert.equal(families[0].lastSeen, daysAgo(1));
});

test('stale lessons are ranked by not-helpful reports', async () => {
  const env = envWithKV();
  await recordStaleLesson(env, 'outdated-lesson');
  await recordStaleLesson(env, 'outdated-lesson');
  await recordStaleLesson(env, 'slightly-stale-lesson');

  const { staleLessons } = await buildUnsolvedMap(env);
  assert.deepEqual(staleLessons.map((l) => l.lessonId), ['outdated-lesson', 'slightly-stale-lesson']);
  assert.equal(staleLessons[0].notHelpful30d, 2);
});

// ── POST /api/search-signal ────────────────────────────────────────────────

test('zero-result searches are recorded as no_match', async () => {
  const env = envWithKV();
  const resp = await handleSearchSignal(signalRequest({ query: 'database is locked', result_count: 0 }), env);
  assert.equal(resp.status, 200);
  const body = await resp.json();
  assert.deepEqual(body, { recorded: true, taskFamily: 'database-lock', reason: 'no_match' });
});

test('low-confidence results are recorded as low_confidence', async () => {
  const env = envWithKV();
  const body = await (await handleSearchSignal(
    signalRequest({ query: 'pip install timeout', result_count: 3, top_score: 0.2 }), env)).json();
  assert.equal(body.reason, 'low_confidence');
});

test('solved searches are not recorded at all', async () => {
  const env = envWithKV();
  const body = await (await handleSearchSignal(
    signalRequest({ query: 'pip install timeout', result_count: 3, top_score: 0.9 }), env)).json();
  assert.deepEqual(body, { recorded: false, reason: 'search_was_solved' });
  assert.equal(env.MISAKANET_KV._store.size, 1, 'only the rate-limit key exists');
});

test('the raw query never reaches KV', async () => {
  const env = envWithKV();
  const secretish = 'ghp_pretend_token_in_a_query database locked /home/me/app.log';
  await handleSearchSignal(signalRequest({ query: secretish, result_count: 0 }), env);

  const dump = JSON.stringify([...env.MISAKANET_KV._store.entries()]);
  assert.ok(!dump.includes('ghp_pretend_token_in_a_query'));
  assert.ok(!dump.includes('/home/me/app.log'));
  assert.ok(dump.includes('unsolved:family:database-lock'));
});

test('missing query and malformed JSON are rejected', async () => {
  const env = envWithKV();
  assert.equal((await handleSearchSignal(signalRequest({ result_count: 0 }), env)).status, 400);

  const bad = new Request('https://misakanet.org/api/search-signal', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{oops',
  });
  assert.equal((await handleSearchSignal(bad, env)).status, 400);
});

test('signals are rate limited per IP and oversize bodies rejected', async () => {
  const env = envWithKV();
  const headers = { 'CF-Connecting-IP': '203.0.113.9' };
  for (let i = 0; i < 30; i++) {
    await handleSearchSignal(signalRequest({ query: `database locked ${i}`, result_count: 0 }, headers), env);
  }
  const limited = await handleSearchSignal(signalRequest({ query: 'database locked', result_count: 0 }, headers), env);
  assert.equal(limited.status, 429);

  const big = await handleSearchSignal(
    signalRequest({ query: 'x', result_count: 0 }, { 'content-length': '99999' }), env);
  assert.equal(big.status, 413);
});

test('without KV the endpoint degrades to 503 instead of crashing', async () => {
  assert.equal((await handleSearchSignal(signalRequest({ query: 'x', result_count: 0 }), {})).status, 503);
});

// ── GET /api/insights/unsolved-map ─────────────────────────────────────────

test('the map response is aggregate-only and declares it', async () => {
  const env = envWithKV();
  await recordUnsolvedSearch(env, { taskFamily: 'database-lock', reason: 'no_match' });
  await recordStaleLesson(env, 'stale-lesson');

  const body = await (await handleUnsolvedMap(env)).json();
  assert.equal(body.success, true);
  assert.equal(body.available, true);
  assert.equal(body.windowDays, 30);
  assert.deepEqual(body.reasons, UNSOLVED_REASONS);
  assert.equal(body.families[0].taskFamily, 'database-lock');
  assert.equal(body.staleLessons[0].lessonId, 'stale-lesson');
  assert.deepEqual(body.meta, {
    privacy: 'aggregate-only', raw_query: false, prompts: false, logs: false, paths: false, pii: false,
  });

  const emitted = Object.keys(body.families[0]).concat(Object.keys(body.staleLessons[0]));
  for (const field of ['query', 'text', 'ip', 'path', 'prompt', 'user']) {
    assert.ok(!emitted.includes(field), `${field} must never be emitted`);
  }
});

test('without KV the map reports unavailable rather than failing', async () => {
  const body = await (await handleUnsolvedMap({})).json();
  assert.deepEqual(body.families, []);
  assert.equal(body.available, false);
  assert.equal(body.success, true);
});

// ── Routing + feedback integration ─────────────────────────────────────────

test('worker routes the map and the signal endpoint', async () => {
  const env = envWithKV();
  const posted = await worker.fetch(signalRequest({ query: 'sqlite database is locked', result_count: 0 }), env);
  assert.equal(posted.status, 200);

  const map = await worker.fetch(new Request('https://misakanet.org/api/insights/unsolved-map'), env);
  assert.equal(map.status, 200);
  assert.equal((await map.json()).families[0].taskFamily, 'database-lock');
});

test('not-helpful feedback feeds the map and the stale-lesson list', async () => {
  const env = envWithKV();
  const feedback = new Request('https://misakanet.org/api/feedback', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query: 'npm publish 403', lesson_id: 'npm-publish-otp', feedback: 'irrelevant' }),
  });
  assert.equal((await worker.fetch(feedback, env)).status, 200);

  const body = await (await handleUnsolvedMap(env)).json();
  assert.equal(body.families[0].taskFamily, 'npm-publish');
  assert.deepEqual(body.families[0].reasons, { not_helpful: 1 });
  assert.equal(body.staleLessons[0].lessonId, 'npm-publish-otp');
});

test('helpful feedback does not pollute the unsolved map', async () => {
  const env = envWithKV();
  const feedback = new Request('https://misakanet.org/api/feedback', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query: 'npm publish 403', lesson_id: 'npm-publish-otp', feedback: 'helpful' }),
  });
  await worker.fetch(feedback, env);
  assert.deepEqual((await (await handleUnsolvedMap(env)).json()).families, []);
});
