// Unit tests for the remote MCP endpoint (Issue #804).
// Run: node --test workers/mcp-remote.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import worker, {
  MCP_FALLBACK_VERSION,
  MCP_TOOLS,
  handleMcpRequest,
  mcpMethodNotAllowed,
  mcpOriginAllowed,
  mcpRankLessons,
  mcpSafeLessonPath,
  mcpTimingSafeEqual,
  mcpTokenize,
} from './register-proxy-sw.js';

const TOKEN = 'test-mcp-token';
const ENV = { MCP_TOKEN: TOKEN, REGISTER_TOKEN: 'gh-token' };

const LESSONS = [
  {
    id: 'sqlite-database-locked',
    title: 'SQLite database is locked under concurrent writers',
    domain: 'python',
    tags: ['sqlite', 'database', 'locking'],
    summary: 'Concurrent writers hit "database is locked"; fix with WAL mode and a busy timeout.',
    preview: '# database locked\n\nUse WAL.',
    url: 'lessons/core/sqlite-database-locked.md',
    status: 'active',
    verified: true,
    confidence: 0.9,
  },
  {
    id: 'npm-publish-otp',
    title: 'npm publish fails with EOTP',
    domain: 'devops',
    tags: ['npm', 'publish'],
    summary: 'npm publish needs a one-time password when 2FA is enabled.',
    preview: 'Pass --otp=<code>.',
    url: 'lessons/contrib/npm-publish-otp.md',
    status: 'active',
    verified: false,
    confidence: 0.6,
  },
  {
    id: 'zh-locked-db',
    title: '数据库锁定导致写入失败',
    domain: 'python',
    tags: ['数据库'],
    summary: '并发写入时数据库锁定，需要开启 WAL 模式。',
    preview: '数据库锁定的排查步骤。',
    url: 'lessons/core/zh-locked-db.md',
    status: 'active',
    verified: false,
    confidence: 0.5,
  },
];

const MARKDOWN = {
  'lessons/core/sqlite-database-locked.md': '# SQLite database is locked\n\nEnable WAL mode.\n',
  'lessons/core/zh-locked-db.md': '# 数据库锁定\n\n开启 WAL 模式并设置 busy_timeout。\n',
};

// Stub the GitHub contents API the worker reads through.
function installFakeGitHub() {
  const calls = [];
  globalThis.fetch = async (url) => {
    calls.push(String(url));
    const parsed = new URL(String(url));
    const path = decodeURIComponent(parsed.pathname.split('/contents/')[1] || '');
    const ref = parsed.searchParams.get('ref');

    let text = null;
    if (path === 'lessons.json' && ref === 'data') text = JSON.stringify(LESSONS);
    else if (ref === 'main' && MARKDOWN[path] !== undefined) text = MARKDOWN[path];

    if (text === null) return new Response('{"message":"Not Found"}', { status: 404 });
    return new Response(
      JSON.stringify({ content: Buffer.from(text, 'utf8').toString('base64'), encoding: 'base64' }),
      { status: 200, headers: { 'content-type': 'application/json' } },
    );
  };
  return calls;
}

function mcpRequest(body, { token = TOKEN, origin, headers = {}, method = 'POST' } = {}) {
  const requestHeaders = { 'Content-Type': 'application/json', ...headers };
  if (token !== null) requestHeaders.Authorization = `Bearer ${token}`;
  if (origin) requestHeaders.Origin = origin;
  return new Request('https://misakanet.org/mcp', {
    method,
    headers: requestHeaders,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

const rpc = (method, params, id = 1) => ({ jsonrpc: '2.0', id, method, params });

async function callMcp(body, options) {
  installFakeGitHub();
  const resp = await handleMcpRequest(mcpRequest(body, options), options?.env || ENV);
  return resp;
}

// ── Auth + Origin ──────────────────────────────────────────────────────────

test('missing bearer token returns 401', async () => {
  const resp = await callMcp(rpc('tools/list', {}), { token: null });
  assert.equal(resp.status, 401);
  assert.match(resp.headers.get('WWW-Authenticate') || '', /Bearer/);
  assert.equal((await resp.json()).error.message, 'Unauthorized');
});

test('invalid bearer token returns 401', async () => {
  const resp = await callMcp(rpc('tools/list', {}), { token: 'wrong-token-value' });
  assert.equal(resp.status, 401);
});

test('unknown Origin returns 403 even with a valid token', async () => {
  const resp = await callMcp(rpc('tools/list', {}), { origin: 'https://evil.example' });
  assert.equal(resp.status, 403);
  assert.equal((await resp.json()).error.message, 'Forbidden origin');
});

test('allowlisted Origin is accepted and echoed back', async () => {
  const resp = await callMcp(rpc('tools/list', {}), { origin: 'https://misakanet.org' });
  assert.equal(resp.status, 200);
  assert.equal(resp.headers.get('Access-Control-Allow-Origin'), 'https://misakanet.org');
});

test('MCP_ALLOWED_ORIGINS extends the allowlist', () => {
  assert.equal(mcpOriginAllowed('https://extra.example', { MCP_ALLOWED_ORIGINS: 'https://extra.example' }), true);
  assert.equal(mcpOriginAllowed('https://extra.example', {}), false);
  assert.equal(mcpOriginAllowed(null, {}), true, 'non-browser clients send no Origin');
});

test('unconfigured MCP_TOKEN returns 503, not a bypass', async () => {
  const resp = await callMcp(rpc('tools/list', {}), { env: { REGISTER_TOKEN: 'gh-token' } });
  assert.equal(resp.status, 503);
});

test('timing-safe compare rejects mismatched and empty tokens', () => {
  assert.equal(mcpTimingSafeEqual(TOKEN, TOKEN), true);
  assert.equal(mcpTimingSafeEqual(TOKEN, 'test-mcp-tokeN'), false);
  assert.equal(mcpTimingSafeEqual('', ''), false);
});

// ── Protocol surface ───────────────────────────────────────────────────────

test('initialize returns serverInfo and negotiates the protocol version', async () => {
  const resp = await callMcp(rpc('initialize', { protocolVersion: '2025-06-18' }));
  assert.equal(resp.status, 200);
  const { result } = await resp.json();
  assert.equal(result.protocolVersion, '2025-06-18');
  assert.equal(result.serverInfo.name, 'misakanet');
  assert.equal(result.serverInfo.version, MCP_FALLBACK_VERSION);
  assert.ok(result.capabilities.tools);
});

test('initialize echoes the 2026-07-28 RC and falls back for unknown versions', async () => {
  const rc = await (await callMcp(rpc('initialize', { protocolVersion: '2026-07-28' }))).json();
  assert.equal(rc.result.protocolVersion, '2026-07-28');
  const unknown = await (await callMcp(rpc('initialize', { protocolVersion: '1999-01-01' }))).json();
  assert.equal(unknown.result.protocolVersion, '2025-06-18');
});

test('MCP_VERSION secret overrides the fallback version', async () => {
  const resp = await callMcp(rpc('initialize', {}), { env: { ...ENV, MCP_VERSION: '9.9.9' } });
  assert.equal((await resp.json()).result.serverInfo.version, '9.9.9');
});

test('tools/list exposes exactly the two read-only tools', async () => {
  const { result } = await (await callMcp(rpc('tools/list', {}))).json();
  assert.deepEqual(result.tools.map((t) => t.name), ['misakanet_search', 'misakanet_get_lesson']);
  for (const tool of result.tools) {
    assert.equal(tool.inputSchema.type, 'object');
    assert.ok(tool.description.length > 50);
  }
});

test('no write tools leak into Phase 1', () => {
  const names = MCP_TOOLS.map((t) => t.name);
  assert.ok(!names.includes('misakanet_submit_usage'));
  assert.ok(!names.includes('misakanet_usage_status'));
});

test('unsupported MCP-Protocol-Version header returns 400', async () => {
  const resp = await callMcp(rpc('tools/list', {}), { headers: { 'MCP-Protocol-Version': '2001-01-01' } });
  assert.equal(resp.status, 400);
});

test('notifications get 202 with no body', async () => {
  const resp = await callMcp({ jsonrpc: '2.0', method: 'notifications/initialized' });
  assert.equal(resp.status, 202);
  assert.equal(await resp.text(), '');
});

test('unknown method returns JSON-RPC -32601', async () => {
  const { error } = await (await callMcp(rpc('resources/list', {}))).json();
  assert.equal(error.code, -32601);
});

test('malformed JSON returns -32700 and batches are rejected', async () => {
  installFakeGitHub();
  const bad = new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers: { Authorization: `Bearer ${TOKEN}`, 'Content-Type': 'application/json' },
    body: '{not json',
  });
  const parseResp = await handleMcpRequest(bad, ENV);
  assert.equal(parseResp.status, 400);
  assert.equal((await parseResp.json()).error.code, -32700);

  const batchResp = await callMcp([rpc('tools/list', {})]);
  assert.equal(batchResp.status, 400);
  assert.equal((await batchResp.json()).error.code, -32600);
});

test('GET /mcp returns 405 with Accept-Post', () => {
  const resp = mcpMethodNotAllowed(new Request('https://misakanet.org/mcp'), ENV);
  assert.equal(resp.status, 405);
  assert.equal(resp.headers.get('Accept-Post'), 'application/json');
  assert.equal(resp.headers.get('Allow'), 'POST, OPTIONS');
});

// ── Routing through the worker entrypoint ──────────────────────────────────

test('worker routes /mcp before the landing page and CORS catch-alls', async () => {
  installFakeGitHub();

  const get = await worker.fetch(new Request('https://misakanet.org/mcp'), ENV);
  assert.equal(get.status, 405, 'GET /mcp must not fall through to the HTML landing page');
  assert.equal(get.headers.get('Accept-Post'), 'application/json');

  const preflight = await worker.fetch(
    new Request('https://misakanet.org/mcp', { method: 'OPTIONS', headers: { Origin: 'https://claude.ai' } }),
    ENV,
  );
  assert.equal(preflight.status, 204);
  assert.equal(preflight.headers.get('Access-Control-Allow-Origin'), 'https://claude.ai');
  assert.match(preflight.headers.get('Access-Control-Allow-Headers') || '', /Authorization/);

  const post = await worker.fetch(mcpRequest(rpc('tools/list', {})), ENV);
  assert.equal(post.status, 200);
  assert.equal((await post.json()).result.tools.length, 2);

  const trailingSlash = await worker.fetch(
    new Request('https://misakanet.org/mcp/', { method: 'POST', headers: { Authorization: `Bearer ${TOKEN}` }, body: '{}' }),
    ENV,
  );
  assert.equal(trailingSlash.status, 400, '/mcp/ is handled by the MCP route, not the 404 catch-all');
});

test('other routes still work after the MCP route is added', async () => {
  installFakeGitHub();
  const health = await worker.fetch(new Request('https://misakanet.org/api/health'), ENV);
  assert.equal(health.status, 200);
  assert.equal((await health.json()).status, 'ok');

  const lessons = await worker.fetch(new Request('https://misakanet.org/api/lessons'), ENV);
  assert.equal(lessons.status, 200);
  assert.equal((await lessons.json()).length, LESSONS.length);
});

// ── tools/call ─────────────────────────────────────────────────────────────

test('misakanet_search returns ranked lesson results', async () => {
  const resp = await callMcp(rpc('tools/call', { name: 'misakanet_search', arguments: { query: 'database locked' } }));
  const { result } = await resp.json();
  assert.equal(result.isError, false);
  const payload = JSON.parse(result.content[0].text);
  assert.equal(payload.results[0].id, 'sqlite-database-locked');
  assert.equal(payload.results[0].path, 'lessons/core/sqlite-database-locked.md');
  assert.ok(payload.results[0].score > 0);
  assert.equal(payload.count, payload.results.length);
});

test('misakanet_search validates query and honours domain/top', async () => {
  const missing = await (await callMcp(rpc('tools/call', { name: 'misakanet_search', arguments: {} }))).json();
  assert.equal(missing.result.isError, true);
  assert.match(missing.result.content[0].text, /query is required/);

  const filtered = mcpRankLessons(LESSONS, { query: 'publish', domain: 'python', top: 5 });
  assert.deepEqual(filtered, [], 'domain filter excludes non-matching domains');

  const capped = mcpRankLessons(LESSONS, { query: 'database', top: 1 });
  assert.equal(capped.length, 1);
});

test('CJK queries tokenize into bigrams and match Chinese lessons', () => {
  assert.ok(mcpTokenize('数据库锁定').includes('数据'));
  const results = mcpRankLessons(LESSONS, { query: '数据库锁定', top: 5 });
  assert.equal(results[0].id, 'zh-locked-db');
});

test('misakanet_get_lesson returns lesson markdown by path and by id', async () => {
  const byPath = await (await callMcp(rpc('tools/call', {
    name: 'misakanet_get_lesson',
    arguments: { path: 'lessons/core/sqlite-database-locked.md' },
  }))).json();
  const payload = JSON.parse(byPath.result.content[0].text);
  assert.match(payload.content, /Enable WAL mode/);
  assert.equal(payload.truncated, false);

  const byId = await (await callMcp(rpc('tools/call', {
    name: 'misakanet_get_lesson',
    arguments: { id: 'sqlite-database-locked' },
  }))).json();
  assert.equal(JSON.parse(byId.result.content[0].text).path, 'lessons/core/sqlite-database-locked.md');
});

test('lesson markdown survives UTF-8 round-trip', async () => {
  const resp = await callMcp(rpc('tools/call', {
    name: 'misakanet_get_lesson',
    arguments: { id: 'zh-locked-db' },
  }));
  const payload = JSON.parse((await resp.json()).result.content[0].text);
  assert.match(payload.content, /数据库锁定/);
});

test('missing lesson and missing arguments are tool errors, not crashes', async () => {
  const notFound = await (await callMcp(rpc('tools/call', {
    name: 'misakanet_get_lesson',
    arguments: { id: 'does-not-exist' },
  }))).json();
  assert.equal(notFound.result.isError, true);
  assert.match(notFound.result.content[0].text, /Lesson not found/);

  const noArgs = await (await callMcp(rpc('tools/call', { name: 'misakanet_get_lesson', arguments: {} }))).json();
  assert.match(noArgs.result.content[0].text, /path or id is required/);
});

test('lesson paths are confined to lessons/*.md', () => {
  assert.equal(mcpSafeLessonPath('lessons/core/a.md'), 'lessons/core/a.md');
  assert.equal(mcpSafeLessonPath('lessons/../.github/workflows/deploy-worker.yml'), null);
  assert.equal(mcpSafeLessonPath('../../etc/passwd'), null);
  assert.equal(mcpSafeLessonPath('scripts/mcp_server.py'), null);
  assert.equal(mcpSafeLessonPath('lessons/core/a.txt'), null);
});

test('traversal attempts never reach GitHub', async () => {
  const calls = installFakeGitHub();
  const resp = await handleMcpRequest(
    mcpRequest(rpc('tools/call', {
      name: 'misakanet_get_lesson',
      arguments: { path: 'lessons/../../../etc/passwd' },
    })),
    ENV,
  );
  const payload = JSON.parse((await resp.json()).result.content[0].text);
  assert.match(payload.error, /Lesson not found/);
  assert.ok(!calls.some((c) => c.includes('etc/passwd')));
});

test('unknown tool returns JSON-RPC -32602', async () => {
  const { error } = await (await callMcp(rpc('tools/call', { name: 'misakanet_delete_everything', arguments: {} }))).json();
  assert.equal(error.code, -32602);
});

test('upstream GitHub failure surfaces as a tool error, not a 500', async () => {
  globalThis.fetch = async () => new Response('nope', { status: 502 });
  const resp = await handleMcpRequest(mcpRequest(rpc('tools/call', {
    name: 'misakanet_search',
    arguments: { query: 'database locked' },
  })), ENV);
  assert.equal(resp.status, 200);
  const { result } = await resp.json();
  assert.equal(result.isError, true);
  assert.match(result.content[0].text, /Upstream failure/);
});
