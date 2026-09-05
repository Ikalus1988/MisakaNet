// PRD ① tests: misakanet_search returns no_match + suggestion when nothing
// matches, so agents can close the gap loop via misakanet_submit_intake.
// Run: node --test workers/mcp-no-match.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import worker from './register-proxy-sw.js';

const TOKEN = 'no-match-test-token';
const TODAY = new Date().toISOString().slice(0, 10);

// Seed KV so search never hits GitHub: a proxy:lessons cache entry (fresh TTL)
// and no BM25 index (forces the naive searchLessons fallback path).
function createEnv(lessons) {
  const store = new Map([
    ['proxy:lessons', JSON.stringify({ ts: Date.now(), data: lessons })],
  ]);
  return {
    MCP_TOKEN: TOKEN,
    MCP_VERSION: 'no-match-test',
    MISAKANET_KV: {
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
    },
  };
}

const SAMPLE_LESSONS = [
  {
    id: 'pip-timeout-mirror',
    title: 'pip install timeout',
    description: 'pip install times out on slow networks; use a mirror.',
    domain: 'python',
    tags: ['pip', 'network'],
    path: 'lessons/core/pip-timeout-mirror.md',
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

function searchRequest(query, extra = {}, args = {}) {
  return new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${TOKEN}`,
      'Content-Type': 'application/json',
      'MCP-Protocol-Version': '2025-06-18',
      'CF-Connecting-IP': '198.51.100.' + (Math.floor(Math.random() * 200) + 1),
      ...extra,
    },
    body: JSON.stringify({
      jsonrpc: '2.0',
      id: 1,
      method: 'tools/call',
      params: { name: 'misakanet_search', arguments: { query, ...args } },
    }),
  });
}

async function toolResultText(response) {
  const body = await response.json();
  assert.equal(body.error, undefined, `unexpected MCP error: ${JSON.stringify(body.error)}`);
  return JSON.parse(body.result.content[0].text);
}

test('misakanet_search returns no_match + suggestion when nothing matches', async () => {
  const env = createEnv(SAMPLE_LESSONS);
  const resp = await worker.fetch(
    searchRequest('zzz-no-such-topic-anywhere-999'),
    env,
  );
  assert.equal(resp.status, 200);
  const result = await toolResultText(resp);

  assert.equal(result.no_match, true);
  assert.deepEqual(result.results, []);
  assert.match(result.suggestion, /misakanet_submit_intake/);
  assert.match(result.suggestion, /kind="missing_lesson"/);
  // Machine-readable intake hint for tool-calling agents
  assert.equal(result.intake.tool, 'misakanet_submit_intake');
  assert.equal(result.intake.args.kind, 'missing_lesson');
  assert.equal(result.intake.args.error, 'zzz-no-such-topic-anywhere-999');
});

test('misakanet_search keeps working when results exist (no no_match)', async () => {
  const env = createEnv(SAMPLE_LESSONS);
  const resp = await worker.fetch(searchRequest('pip install timeout'), env);
  assert.equal(resp.status, 200);
  const result = await toolResultText(resp);

  assert.equal(result.no_match, undefined);
  assert.ok(Array.isArray(result.results));
  assert.ok(result.results.length >= 1);
  assert.equal(result.results[0].id, 'pip-timeout-mirror');
});

test('no-match search still logs the gap to KV', async () => {
  const env = createEnv(SAMPLE_LESSONS);
  const query = 'kwfzzz-unique-gap-42';
  await worker.fetch(searchRequest(query), env);
  const gap = await env.MISAKANET_KV.get(`gap:${query.toLowerCase().trim()}`, 'json');
  assert.ok(gap, 'gap entry should be recorded');
  assert.equal(gap.count, 1);
});

test('no-match response is identical across detail levels', async () => {
  const env = createEnv(SAMPLE_LESSONS);
  const query = 'abcxyz-nothing-here-77';
  for (const detail of ['compact', 'summary', 'full']) {
    const resp = await worker.fetch(
      searchRequest(query, { 'CF-Connecting-IP': '198.51.100.9' }, { detail }),
      env,
    );
    const result = await toolResultText(resp);
    assert.equal(result.no_match, true, `detail=${detail}`);
    assert.ok(result.suggestion.includes('misakanet_submit_intake'));
    assert.equal(result.detail, detail);
  }
});

// #1396: how-to no-match queries must suggest kind="question", not route the
// question into the failure-lesson funnel (missing_lesson → auto-reject).
test('no-match how-to query suggests kind=question intake', async () => {
  const env = createEnv(SAMPLE_LESSONS);
  const resp = await worker.fetch(searchRequest('how do i configure mcp auth in production'), env);
  const result = await toolResultText(resp);
  assert.equal(result.no_match, true);
  assert.match(result.suggestion, /kind="question"/);
  assert.equal(result.intake.tool, 'misakanet_submit_intake');
  assert.equal(result.intake.args.kind, 'question');
  assert.equal(result.intake.args.error, undefined);
});

test('no-match error-like query still suggests kind=missing_lesson', async () => {
  const env = createEnv(SAMPLE_LESSONS);
  const query = 'zzz-econnrefused-on-corporate-proxy-404';
  const resp = await worker.fetch(searchRequest(query), env);
  const result = await toolResultText(resp);
  assert.equal(result.no_match, true);
  assert.match(result.suggestion, /kind="missing_lesson"/);
  assert.equal(result.intake.args.kind, 'missing_lesson');
  assert.equal(result.intake.args.error, query);
});
