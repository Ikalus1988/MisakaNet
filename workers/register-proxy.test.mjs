import assert from 'node:assert/strict';
import test from 'node:test';
import {
  TASK_FAMILY_WHITELIST,
  normalizeTaskFamily,
  timingSafeEqual,
  recordUnsolvedSignal,
  buildDemandBoardSummary,
  buildDemandMapBuckets,
  handleDemandBoard,
  handleDemandMap,
  handleMcpRequest,
  validateMcpAuthAndOrigin,
  isValidMcpOrigin,
  searchLessonsInWorker,
} from './register-proxy.js';

function createFakeKV(seed = {}) {
  const store = new Map(Object.entries(seed));
  return {
    async get(key, type) {
      if (!store.has(key)) return null;
      const raw = store.get(key);
      return type === 'json' ? JSON.parse(raw) : raw;
    },
    async put(key, value) {
      store.set(key, value);
    },
    async delete(key) {
      store.delete(key);
    },
    _store: store,
  };
}

function daysAgo(n) {
  return new Date(Date.now() - n * 86_400_000).toISOString().slice(0, 10);
}

test('normalizeTaskFamily keeps whitelisted families and falls back to unclassified', () => {
  assert.equal(normalizeTaskFamily('github-auth'), 'github-auth');
  assert.equal(normalizeTaskFamily('made-up-family'), 'unclassified');
  assert.equal(normalizeTaskFamily(undefined), 'unclassified');
});

test('TASK_FAMILY_WHITELIST matches the issue #591 whitelist', () => {
  assert.deepEqual(TASK_FAMILY_WHITELIST, [
    'github-auth', 'npm-publish', 'cloudflare-worker', 'mcp-registry',
    'glama-release', 'python-env', 'database-lock', 'crawler-block',
    'agent-tooling', 'unclassified',
  ]);
});

test('timingSafeEqual only accepts matching same-length strings', () => {
  assert.equal(timingSafeEqual('secret-key', 'secret-key'), true);
  assert.equal(timingSafeEqual('secret-key', 'wrong-key!'), false);
  assert.equal(timingSafeEqual('short', 'much-longer-value'), false);
  assert.equal(timingSafeEqual('', ''), false);
});

test('recordUnsolvedSignal buckets by family/day/reason and dedups source hashes', async () => {
  const env = { MISAKANET_KV: createFakeKV() };
  await recordUnsolvedSignal(env, { taskFamily: 'github-auth', reason: 'no_matching_lesson', sourceId: 'node-a' });
  await recordUnsolvedSignal(env, { taskFamily: 'github-auth', reason: 'no_matching_lesson', sourceId: 'node-a' });
  await recordUnsolvedSignal(env, { taskFamily: 'github-auth', reason: 'no_matching_lesson', sourceId: 'node-b' });
  await recordUnsolvedSignal(env, { taskFamily: 'github-auth', reason: 'search_miss', sourceId: 'node-c' });
  await recordUnsolvedSignal(env, { taskFamily: 'not-a-real-family', reason: 'irrelevant' });

  const buckets = await buildDemandMapBuckets(env);
  const authBuckets = buckets.filter((b) => b.taskFamily === 'github-auth');
  const noMatch = authBuckets.find((b) => b.unsolvedReason === 'no_matching_lesson');
  const searchMiss = authBuckets.find((b) => b.unsolvedReason === 'search_miss');
  const unclassified = buckets.find((b) => b.taskFamily === 'unclassified');

  assert.equal(noMatch.unsolvedCount, 3);
  assert.equal(noMatch.distinctSourceCount, 2); // node-a deduped, node-b distinct
  assert.equal(searchMiss.unsolvedCount, 1);
  assert.equal(searchMiss.distinctSourceCount, 1);
  assert.ok(unclassified, 'unknown task family falls back into the unclassified bucket');
  assert.equal(unclassified.unsolvedCount, 1);
});

test('recordUnsolvedSignal prunes buckets older than the 30-day window', async () => {
  const ancientRecord = JSON.stringify({ days: { '2000-01-01': { reasons: { irrelevant: { count: 5, sources: [] } } } } });
  const env = { MISAKANET_KV: createFakeKV({ 'demand:family:github-auth': ancientRecord }) };

  await recordUnsolvedSignal(env, { taskFamily: 'github-auth', reason: 'irrelevant' });

  const record = JSON.parse(await env.MISAKANET_KV.get('demand:family:github-auth'));
  assert.ok(!('2000-01-01' in record.days), 'stale day bucket should have been pruned');
});

test('buildDemandBoardSummary sums 7d/30d windows, excludes zero-count families, and sets lastSeen/actionUrl', async () => {
  const record = {
    days: {
      [daysAgo(0)]: { reasons: { no_matching_lesson: { count: 3, sources: ['a', 'b'] } } },
      [daysAgo(10)]: { reasons: { no_matching_lesson: { count: 9, sources: ['c'] } } },
      [daysAgo(40)]: { reasons: { no_matching_lesson: { count: 100, sources: ['d'] } } }, // outside 30d window
    },
  };
  const env = {
    MISAKANET_KV: createFakeKV({
      'demand:family:github-auth': JSON.stringify(record),
      'demand:family:npm-publish': JSON.stringify({ days: {} }),
    }),
  };

  const summary = await buildDemandBoardSummary(env);
  assert.equal(summary.length, 1, 'families with no unsolved reports in-window are omitted');

  const entry = summary[0];
  assert.equal(entry.taskFamily, 'github-auth');
  assert.equal(entry.unsolved7d, 3);
  assert.equal(entry.unsolved30d, 12);
  assert.equal(entry.lastSeen, daysAgo(0));
  assert.equal(entry.actionUrl, 'https://github.com/Ikalus1988/MisakaNet/issues/new?template=lesson-feedback.yml');
});

test('handleDemandBoard is aggregate-only and reports availability based on KV binding', async () => {
  const withKV = await handleDemandBoard({ MISAKANET_KV: createFakeKV() });
  const withKvBody = await withKV.json();
  assert.equal(withKvBody.success, true);
  assert.equal(withKvBody.available, true);
  assert.deepEqual(withKvBody.summary, []);
  assert.deepEqual(withKvBody.meta, {
    r_level: 'R1_descriptive',
    privacy: 'aggregate-only',
    raw_query: false,
    pii: false,
  });

  const withoutKV = await handleDemandBoard({});
  const withoutKvBody = await withoutKV.json();
  assert.equal(withoutKvBody.success, true);
  assert.equal(withoutKvBody.available, false);
  assert.deepEqual(withoutKvBody.summary, []);
});

test('handleDemandMap requires a maintainer key and rejects mismatches', async () => {
  const env = { MAINTAINER_KEY: 'top-secret', MISAKANET_KV: createFakeKV() };

  const notConfigured = await handleDemandMap(new Request('https://x/api/insights/demand-map'), {});
  assert.equal(notConfigured.status, 503);

  const noKey = await handleDemandMap(new Request('https://x/api/insights/demand-map'), env);
  assert.equal(noKey.status, 401);

  const wrongKey = await handleDemandMap(
    new Request('https://x/api/insights/demand-map', { headers: { 'X-Maintainer-Key': 'nope' } }),
    env,
  );
  assert.equal(wrongKey.status, 401);

  await recordUnsolvedSignal(env, { taskFamily: 'python-env', reason: 'too_basic', sourceId: 'node-z' });
  const ok = await handleDemandMap(
    new Request('https://x/api/insights/demand-map', { headers: { 'X-Maintainer-Key': 'top-secret' } }),
    env,
  );
  assert.equal(ok.status, 200);
  const body = await ok.json();
  assert.equal(body.buckets.length, 1);
  assert.equal(body.buckets[0].taskFamily, 'python-env');
  assert.equal(body.buckets[0].unsolvedReason, 'too_basic');
  assert.equal(body.buckets[0].unsolvedCount, 1);
  assert.equal(body.buckets[0].distinctSourceCount, 1);
});

test('GET /mcp returns 405 Method Not Allowed with Accept: POST header', async () => {
  const req = new Request('https://misakanet.org/mcp', { method: 'GET' });
  const res = await handleMcpRequest(req, { MCP_TOKEN: 'test-token' });
  assert.equal(res.status, 405);
  assert.equal(res.headers.get('Accept'), 'POST');
  assert.equal(res.headers.get('Allow'), 'POST');
});

test('POST /mcp requires valid Bearer token (401 on missing/invalid)', async () => {
  const env = { MCP_TOKEN: 'secret-mcp-token' };

  // Missing header
  const req1 = new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'initialize' }),
  });
  const res1 = await handleMcpRequest(req1, env);
  assert.equal(res1.status, 401);

  // Wrong token
  const req2 = new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: 'Bearer wrong-token',
    },
    body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'initialize' }),
  });
  const res2 = await handleMcpRequest(req2, env);
  assert.equal(res2.status, 401);
});

test('POST /mcp validates Origin header (403 on invalid Origin)', async () => {
  const env = { MCP_TOKEN: 'valid-token' };

  // Invalid Origin
  const req1 = new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: 'Bearer valid-token',
      Origin: 'http://malicious-site.example.com',
    },
    body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'initialize' }),
  });
  const res1 = await handleMcpRequest(req1, env);
  assert.equal(res1.status, 403);

  // Valid Origin
  const req2 = new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: 'Bearer valid-token',
      Origin: 'https://glama.ai',
    },
    body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'initialize' }),
  });
  const res2 = await handleMcpRequest(req2, env);
  assert.equal(res2.status, 200);
});

test('POST /mcp initialize method returns serverInfo and protocolVersion', async () => {
  const env = { MCP_TOKEN: 'valid-token', MCP_VERSION: '0.9.1' };
  const req = new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: 'Bearer valid-token',
    },
    body: JSON.stringify({
      jsonrpc: '2.0',
      id: 1,
      method: 'initialize',
      params: { protocolVersion: '2025-06-18' },
    }),
  });
  const res = await handleMcpRequest(req, env);
  assert.equal(res.status, 200);
  const data = await res.json();
  assert.equal(data.jsonrpc, '2.0');
  assert.equal(data.id, 1);
  assert.equal(data.result.protocolVersion, '2025-06-18');
  assert.equal(data.result.serverInfo.name, 'misakanet-remote');
  assert.equal(data.result.serverInfo.version, '0.9.1');
});

test('POST /mcp tools/list method exposes misakanet_search and misakanet_get_lesson', async () => {
  const env = { MCP_TOKEN: 'valid-token' };
  const req = new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: 'Bearer valid-token',
    },
    body: JSON.stringify({ jsonrpc: '2.0', id: 2, method: 'tools/list', params: {} }),
  });
  const res = await handleMcpRequest(req, env);
  assert.equal(res.status, 200);
  const data = await res.json();
  const toolNames = data.result.tools.map((t) => t.name);
  assert.deepEqual(toolNames, ['misakanet_search', 'misakanet_get_lesson']);
});

test('searchLessonsInWorker ranks matching lessons by keywords', () => {
  const mockLessons = [
    {
      id: 'db-lock',
      title: 'Database Locked in SQLite',
      domain: 'database-lock',
      tags: ['sqlite', 'lock'],
      summary: 'Fix database is locked error',
      url: 'lessons/core/db-lock.md',
    },
    {
      id: 'npm-401',
      title: 'NPM Publish Unauthorized',
      domain: 'npm-publish',
      tags: ['npm'],
      summary: 'Fix 401 Unauthorized during npm publish',
      url: 'lessons/core/npm-401.md',
    },
  ];

  const results = searchLessonsInWorker(mockLessons, 'database locked', null, 5);
  assert.equal(results.length, 1);
  assert.equal(results[0].title, 'Database Locked in SQLite');
  assert.equal(results[0].path, 'lessons/core/db-lock.md');
});

test('POST /mcp tools/call misakanet_search executes search query', async () => {
  const mockLessons = [
    {
      id: 'db-lock',
      title: 'Database Locked in SQLite',
      domain: 'database-lock',
      tags: ['sqlite', 'lock'],
      summary: 'Fix database is locked error',
      url: 'lessons/core/db-lock.md',
    },
  ];
  const env = {
    MCP_TOKEN: 'valid-token',
    MISAKANET_KV: createFakeKV({
      'proxy:lessons': JSON.stringify({ data: mockLessons, ts: Date.now() }),
    }),
  };

  const req = new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: 'Bearer valid-token',
    },
    body: JSON.stringify({
      jsonrpc: '2.0',
      id: 3,
      method: 'tools/call',
      params: {
        name: 'misakanet_search',
        arguments: { query: 'database locked' },
      },
    }),
  });
  const res = await handleMcpRequest(req, env);
  assert.equal(res.status, 200);
  const data = await res.json();
  assert.equal(data.id, 3);
  assert.ok(data.result.content[0].text.includes('Database Locked in SQLite'));
});

