// The Analytics Engine write points (2026-11-15).
//
// The dataset is the first place the worker stores a *row per request* rather than a counter, and
// its whole justification is a privacy promise: the site says query text does not leave the machine,
// and a data point is a stored row. So these tests assert the two halves that can break independently:
//
//   1. a completed tool call writes exactly one point, with the fields the query script reads;
//   2. the point contains no raw query, no intake problem text, and no token.
//
// The last test drives the same calls with `EVENTS` absent — the local-dev / older-deploy shape —
// and asserts the answer is unchanged, because a missing binding has to be a no-op rather than a
// crash. `writeDataPoint` is synchronous in Workers; the stub records the object it was handed, which
// is exactly what a reviewer needs to check the privacy claim.
//
// Run: node --test workers/analytics-events.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import { createHash } from 'node:crypto';
import worker, { hashString } from './register-proxy-sw.js';
import { testToken } from './_test-token.mjs';

const TOKEN = testToken('analytics-events');
const QUERY = 'pip install timeout on a corporate proxy';
const LESSON_PATH = 'lessons/core/pip-timeout-mirror.md';
const LESSON_BODY = '# pip timeout\n\n## Root cause\n\nA slow network.\n';
const INTAKE_PROBLEM = 'the build fails on a clean checkout with exit code 17';

const LESSONS = [
  {
    id: 'pip-timeout-mirror',
    title: 'pip install timeout',
    description: 'pip install times out on slow networks; use a mirror.',
    domain: 'python',
    tags: ['pip', 'network'],
    path: LESSON_PATH,
    status: 'published',
  },
  {
    id: 'dco-signoff',
    title: 'DCO sign-off failed',
    description: 'GitHub requires DCO sign-off on commits.',
    domain: 'git',
    tags: ['github', 'dco'],
    path: 'lessons/core/dco-signoff.md',
    status: 'published',
  },
];

function sha256Prefix(text) {
  return createHash('sha256').update(text, 'utf8').digest('hex').slice(0, 16);
}

function createEnv({ withEvents = true } = {}) {
  const store = new Map([
    ['proxy:lessons', JSON.stringify({ ts: Date.now(), data: LESSONS })],
  ]);
  const points = [];
  const env = {
    MCP_TOKEN: TOKEN,
    REGISTER_TOKEN: TOKEN,
    MCP_VERSION: 'analytics-events-test',
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
  if (withEvents) {
    env.EVENTS = {
      writeDataPoint(point) { points.push(point); },
    };
  }
  return { env, points, store };
}

function mcpRequest(name, args, { ip = '198.51.100.7' } = {}) {
  return new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'MCP-Protocol-Version': '2025-06-18',
      Origin: 'https://misakanet.org',
      'CF-Connecting-IP': ip,
      Authorization: `Bearer ${TOKEN}`,
    },
    body: JSON.stringify({
      jsonrpc: '2.0',
      id: 1,
      method: 'tools/call',
      params: { name, arguments: args },
    }),
  });
}

/** Drive one tool call, await every `ctx.waitUntil` write, return the tool payload. */
async function callTool(env, name, args, opts) {
  const pending = [];
  const response = await worker.fetch(
    mcpRequest(name, args, opts),
    env,
    { waitUntil: (promise) => pending.push(Promise.resolve(promise)) },
  );
  await Promise.all(pending);
  const body = await response.json();
  assert.equal(body.error, undefined, `unexpected MCP error: ${JSON.stringify(body.error)}`);
  return JSON.parse(body.result.content[0].text);
}

/** A GitHub stub for the get_lesson and new-intake paths. */
async function withGitHubStub(handler, work) {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = handler;
  try {
    return await work();
  } finally {
    globalThis.fetch = originalFetch;
  }
}

function lessonContentsStub(body = LESSON_BODY) {
  return async (url) => {
    if (String(url).includes('/contents/')) {
      return new Response(JSON.stringify({
        content: Buffer.from(body, 'utf-8').toString('base64'),
        encoding: 'base64',
      }), { status: 200, headers: { 'content-type': 'application/json' } });
    }
    return new Response('{}', { status: 404, headers: { 'content-type': 'application/json' } });
  };
}

// ── search ────────────────────────────────────────────────────────────────────────────────────

test('a completed search writes one point, with the query hashed and the miss flag set', async () => {
  const { env, points } = createEnv();
  const payload = await callTool(env, 'misakanet_search', { query: QUERY, top: 3 });
  assert.ok(payload.results.length >= 1, JSON.stringify(payload));
  assert.equal(points.length, 1, `one search must write one point: ${JSON.stringify(points)}`);

  const [point] = points;
  assert.equal(point.blobs[0], 'misakanet_search');
  assert.equal(point.blobs[1], 'mcp', 'the worker classifies /mcp as mcp');
  assert.equal(point.blobs[2], sha256Prefix(QUERY), 'blob3 is the stable SHA-256 prefix');
  assert.equal(point.blobs[3], 'hit');
  assert.equal(point.blobs[4], '', 'search writes no lesson id');
  assert.equal(point.blobs[5], '', 'search writes no intake kind');
  assert.equal(point.doubles[1], payload.results.length, 'double2 is the served result count');
  assert.equal(point.doubles[2], 0);
  assert.ok(Number.isInteger(point.doubles[0]) && point.doubles[0] >= 0,
    `double1 must be a whole millisecond latency: ${point.doubles[0]}`);
});

test('a no_match search writes the miss flag and a zero result count', async () => {
  const { env, points } = createEnv();
  const query = 'zzz-no-such-topic-anywhere-999';
  const payload = await callTool(env, 'misakanet_search', { query });
  assert.equal(payload.no_match, true, JSON.stringify(payload));
  assert.equal(points.length, 1);
  assert.equal(points[0].blobs[3], 'miss');
  assert.equal(points[0].blobs[2], sha256Prefix(query));
  assert.equal(points[0].doubles[1], 0);
  assert.equal(points[0].doubles[2], 1);
});

test('the search point contains no raw query text and no token', async () => {
  const { env, points } = createEnv();
  await callTool(env, 'misakanet_search', { query: QUERY });
  const written = JSON.stringify(points);
  assert.ok(!written.includes(QUERY), `raw query reached the data point: ${written}`);
  assert.ok(!written.includes(TOKEN), `the caller token reached the data point: ${written}`);
  assert.ok(!written.toLowerCase().includes('pip install'), `a query fragment reached the data point: ${written}`);
});

// ── get_lesson ───────────────────────────────────────────────────────────────────────────────

test('a lesson hit writes the resolved slug, hit, and latency', async () => {
  const { env, points } = createEnv();
  const payload = await withGitHubStub(lessonContentsStub(), () =>
    callTool(env, 'misakanet_get_lesson', { id: 'pip-timeout-mirror' }));
  assert.equal(payload.path, LESSON_PATH, JSON.stringify(payload));
  assert.equal(points.length, 1, JSON.stringify(points));

  const [point] = points;
  assert.equal(point.blobs[0], 'misakanet_get_lesson');
  assert.equal(point.blobs[3], 'hit');
  assert.equal(point.blobs[4], 'pip-timeout-mirror');
  assert.equal(point.doubles[2], 0);
  assert.ok(Number.isInteger(point.doubles[0]) && point.doubles[0] >= 0);
});

test('a lesson miss writes miss, and stores no caller-supplied reference', async () => {
  const { env, points } = createEnv();
  const miss = await withGitHubStub(
    async () => new Response('{}', { status: 404, headers: { 'content-type': 'application/json' } }),
    () => callTool(env, 'misakanet_get_lesson', { id: 'no-such-lesson' }),
  );
  assert.equal(miss.code, 'lesson_not_found', JSON.stringify(miss));
  assert.equal(points.length, 1);
  assert.equal(points[0].blobs[3], 'miss');
  assert.equal(points[0].blobs[4], '',
    'a miss reference is caller text and must not be stored');
  assert.equal(points[0].doubles[2], 1);
});

test('a token-shaped lesson id never reaches the data point', async () => {
  const { env, points } = createEnv();
  // `lessonReferenceProblem` accepts any slash-free id, so this is a real shape a caller can send.
  const tokenish = `${TOKEN}`;
  await withGitHubStub(
    async () => new Response('{}', { status: 404, headers: { 'content-type': 'application/json' } }),
    () => callTool(env, 'misakanet_get_lesson', { id: tokenish }),
  );
  assert.equal(points.length, 1);
  assert.equal(points[0].blobs[3], 'miss');
  assert.equal(points[0].blobs[4], '');
  assert.ok(!JSON.stringify(points).includes(tokenish),
    `a caller-supplied id reached the data point: ${JSON.stringify(points)}`);
});

test('a path outside lessons/ contributes a miss count and no stored path', async () => {
  const { env, points } = createEnv();
  const refused = await callTool(env, 'misakanet_get_lesson', { path: 'docs/CI.md' });
  assert.equal(refused.code, 'invalid_lesson_path', JSON.stringify(refused));
  assert.equal(points.length, 1);
  assert.equal(points[0].blobs[3], 'miss');
  assert.equal(points[0].blobs[4], '', 'a refused path must not become a stored string');
  assert.ok(!JSON.stringify(points).includes('docs/CI.md'));
});

// ── submit_intake ─────────────────────────────────────────────────────────────────────────────

test('a new intake writes kind/new, and never the problem text', async () => {
  const { env, points } = createEnv();
  const created = [];
  const payload = await withGitHubStub(async (url, options = {}) => {
    created.push({ url: String(url), method: options.method || 'GET' });
    return new Response(JSON.stringify({
      number: 900,
      html_url: 'https://github.com/Ikalus1988/MisakaNet/issues/900',
    }), { status: 201, headers: { 'content-type': 'application/json' } });
  }, () => callTool(env, 'misakanet_submit_intake', {
    kind: 'missing_lesson',
    problem: INTAKE_PROBLEM,
    error: 'ENOENT',
    source: 'mcp',
  }));
  assert.equal(payload.submitted, true, JSON.stringify(payload));
  assert.equal(points.length, 1, JSON.stringify(points));

  const [point] = points;
  assert.equal(point.blobs[0], 'misakanet_submit_intake');
  assert.equal(point.blobs[3], 'new');
  assert.equal(point.blobs[5], 'missing_lesson');
  assert.equal(point.doubles[2], 0);
  const written = JSON.stringify(points);
  assert.ok(!written.includes(INTAKE_PROBLEM), `intake problem text reached the data point: ${written}`);
  assert.ok(!written.includes('ENOENT'), `intake error text reached the data point: ${written}`);
  assert.ok(!written.includes(TOKEN), `the caller token reached the data point: ${written}`);
  assert.ok(created.some((call) => call.method === 'POST' && call.url.endsWith('/issues')));
});

test('a duplicate intake writes kind/dedup without reading the problem back out', async () => {
  const { env, points, store } = createEnv();
  const dedupHash = hashString(`missing_lesson:${INTAKE_PROBLEM}:`);
  store.set(`intake_dedup:${dedupHash}`,
    'https://github.com/Ikalus1988/MisakaNet/issues/900');
  const payload = await callTool(env, 'misakanet_submit_intake', {
    kind: 'missing_lesson',
    problem: INTAKE_PROBLEM,
    source: 'mcp',
  });
  assert.equal(payload.duplicate, true, JSON.stringify(payload));
  assert.equal(points.length, 1);
  assert.equal(points[0].blobs[3], 'dedup');
  assert.equal(points[0].blobs[5], 'missing_lesson');
  assert.equal(points[0].doubles[2], 1);
  assert.ok(!JSON.stringify(points).includes(INTAKE_PROBLEM));
});

// ── missing binding ──────────────────────────────────────────────────────────────────────────

test('a missing EVENTS binding is a no-op, not a crash', async () => {
  const { env, points } = createEnv({ withEvents: false });
  assert.equal(env.EVENTS, undefined);

  const search = await callTool(env, 'misakanet_search', { query: QUERY });
  assert.ok(search.results.length >= 1, JSON.stringify(search));

  const lesson = await withGitHubStub(lessonContentsStub(), () =>
    callTool(env, 'misakanet_get_lesson', { path: LESSON_PATH }));
  assert.equal(lesson.path, LESSON_PATH);

  const miss = await callTool(env, 'misakanet_search', { query: 'zzz-nothing-here-404' });
  assert.equal(miss.no_match, true);
  assert.deepEqual(points, [], 'no binding means no point and no thrown error');
});

test('a writeDataPoint that throws leaves the answer unchanged', async () => {
  const { env } = createEnv();
  env.EVENTS = { writeDataPoint() { throw new Error('AE unavailable'); } };
  const payload = await callTool(env, 'misakanet_search', { query: QUERY });
  assert.ok(payload.results.length >= 1, 'telemetry must not be able to fail a search');
});

test('a search point carries the four phase durations as doubles 4..7', async () => {
  // The endpoint is bimodal from the outside (1.1 s warm vs 4–8.6 s cold, measured 2026-11-15) and
  // the three candidate causes — memoised corpus read, KV BM25 index, scoring — are indistinguishable
  // from a client. These four columns are what makes the next measurement answer instead of guess.
  const { env, points } = createEnv();
  await callTool(env, 'misakanet_search', { query: 'pip install timeout' });
  assert.equal(points.length, 1);
  const doubles = points[0].doubles;
  assert.equal(doubles.length, 7, `expected latency, results, miss flag and four phases: ${JSON.stringify(doubles)}`);
  for (const [i, name] of ['lessons', 'index', 'score', 'semantic'].entries()) {
    const value = doubles[3 + i];
    assert.ok(Number.isInteger(value) && value >= 0, `${name} must be a whole millisecond: ${value}`);
  }
});
