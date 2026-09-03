// submit_intake kind tests: kind whitelist + question routing (labels/title).
// Run: node --test workers/intake-kind.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import worker from './register-proxy-sw.js';

const TOKEN = 'intake-kind-token';

function createEnv() {
  const store = new Map();
  return {
    MCP_TOKEN: TOKEN,
    MCP_VERSION: 'intake-kind-test',
    REGISTER_TOKEN: 'gh-test-token',
    MISAKANET_KV: {
      async get(key, type) {
        if (!store.has(key)) return null;
        const raw = store.get(key);
        return type === 'json' ? JSON.parse(raw) : raw;
      },
      async put(key, value) {
        store.set(key, value);
      },
      _store: store,
    },
  };
}

// Intercept the worker's global fetch for the GitHub issue POST and capture
// the request payload, then return a fake issue response.
function captureGitHubFetch(env, onIssue) {
  const orig = globalThis.fetch;
  globalThis.fetch = async (url, opts) => {
    if (typeof url === 'string' && url.includes('/issues')) {
      const payload = JSON.parse(opts.body);
      onIssue(payload);
      return new Response(JSON.stringify({ number: 42, html_url: 'https://github.com/x/issues/42' }), {
        status: 201,
        headers: { 'Content-Type': 'application/json' },
      });
    }
    return orig(url, opts);
  };
  return () => { globalThis.fetch = orig; };
}

function submitIntake(args, env) {
  return worker.fetch(new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'MCP-Protocol-Version': '2025-06-18',
      'CF-Connecting-IP': '203.0.113.55',
    },
    body: JSON.stringify({
      jsonrpc: '2.0', id: 1, method: 'tools/call',
      params: { name: 'misakanet_submit_intake', arguments: args },
    }),
  }), env);
}

test('submit_intake question kind creates issue with needs-human-review label', async () => {
  const env = createEnv();
  let captured = null;
  const restore = captureGitHubFetch(env, (p) => { captured = p; });
  try {
    const resp = await submitIntake({ kind: 'question', problem: 'How do I set up the MCP server on Windows?' }, env);
    assert.equal(resp.status, 200);
    const body = await resp.json();
    const result = JSON.parse(body.result.content[0].text);
    assert.equal(result.submitted, true);
    assert.equal(result.intake_id, 'issue-42');
    assert.ok(captured);
    assert.ok(captured.labels.includes('needs-human-review'));
    assert.ok(captured.labels.includes('intake'));
    assert.match(captured.title, /^\[Question\]/);
    assert.match(captured.body, /\*\*Kind:\*\* question/);
  } finally {
    restore();
  }
});

test('submit_intake missing_lesson keeps standard labels and title', async () => {
  const env = createEnv();
  let captured = null;
  const restore = captureGitHubFetch(env, (p) => { captured = p; });
  try {
    const resp = await submitIntake({ kind: 'missing_lesson', problem: 'pip times out on corporate proxy' }, env);
    assert.equal(resp.status, 200);
    const body = await resp.json();
    const result = JSON.parse(body.result.content[0].text);
    assert.equal(result.submitted, true);
    assert.ok(captured);
    assert.ok(captured.labels.includes('intake'));
    assert.ok(!captured.labels.includes('needs-human-review'));
    assert.match(captured.title, /^\[Intake\]/);
  } finally {
    restore();
  }
});

test('submit_intake rejects unknown kind', async () => {
  const env = createEnv();
  const resp = await submitIntake({ kind: 'totally-unknown', problem: 'x' }, env);
  assert.equal(resp.status, 200);
  const body = await resp.json();
  const result = JSON.parse(body.result.content[0].text);
  assert.match(result.error, /Invalid kind/);
});

test('submit_intake default kind is missing_lesson when omitted', async () => {
  const env = createEnv();
  let captured = null;
  const restore = captureGitHubFetch(env, (p) => { captured = p; });
  try {
    const resp = await submitIntake({ problem: 'plain failure' }, env);
    assert.equal(resp.status, 200);
    const body = await resp.json();
    const result = JSON.parse(body.result.content[0].text);
    assert.equal(result.submitted, true);
    assert.match(captured.body, /\*\*Kind:\*\* missing_lesson/);
    assert.ok(!captured.labels.includes('needs-human-review'));
  } finally {
    restore();
  }
});

// ── Aider review follow-ups: content-based dedup + KV key sanitize ──

test('submit_intake rejects duplicate submissions by content hash', async () => {
  const env = createEnv();
  let captured = null;
  const restore = captureGitHubFetch(env, (p) => { captured = p; });
  try {
    // First submission creates the issue.
    const first = await submitIntake({ kind: 'missing_lesson', problem: 'duplicate test problem' }, env);
    const firstResult = JSON.parse((await first.json()).result.content[0].text);
    assert.equal(firstResult.submitted, true);

    // Identical problem → dedup hit, no second issue.
    const dup = await submitIntake({ kind: 'missing_lesson', problem: 'duplicate test problem' }, env);
    const dupBody = await dup.json();
    const dupResult = JSON.parse(dupBody.result.content[0].text);
    assert.equal(dupResult.submitted, false);
    assert.equal(dupResult.duplicate, true);
    assert.match(dupResult.error, /Duplicate intake/);
  } finally {
    restore();
  }
});

test('sanitizeReasonKey strips unsafe chars for KV keys', async () => {
  const { sanitizeReasonKey, hashString } = await import('./register-proxy-sw.js');
  // __proto__-style pollution attempt must not become a bare __-prefixed key.
  const safe = sanitizeReasonKey('__proto__::evil key!');
  assert.ok(!safe.startsWith('__'), `should not start with __: ${safe}`);
  assert.ok(!safe.includes('::'));
  assert.ok(!safe.includes('!'));
  assert.ok(safe.length <= 64);
  assert.ok(safe.length > 0);
  // Plain text passes through mostly intact.
  assert.ok(sanitizeReasonKey('pip timeout ssl').includes('pip timeout'));
  // hashString is deterministic and hex.
  assert.match(hashString('pip timeout'), /^[0-9a-f]{8}$/);
  assert.equal(hashString('pip timeout'), hashString('pip timeout'));
  assert.notEqual(hashString('pip timeout'), hashString('pip timeout x'));
});

// ── Kind auto-detection (#1396): how-to content must route to question ──

async function submitAndCapture(args, env) {
  let captured = null;
  const restore = captureGitHubFetch(env, (p) => { captured = p; });
  try {
    const resp = await submitIntake(args, env);
    const result = JSON.parse((await resp.json()).result.content[0].text);
    return { result, captured };
  } finally {
    restore();
  }
}

test('omitted kind + EN question phrasing auto-routes to question', async () => {
  const env = createEnv();
  const { result, captured } = await submitAndCapture(
    { problem: 'How do I set up the MCP server on Windows?' }, env);
  assert.equal(result.submitted, true);
  assert.equal(result.routing.kind, 'question');
  assert.equal(result.routing.auto_detected, true);
  assert.ok(captured);
  assert.match(captured.title, /^\[Question\]/);
  assert.ok(captured.labels.includes('needs-human-review'));
  assert.match(captured.body, /\*\*Kind:\*\* question/);
});

test('omitted kind + PT-BR question phrasing auto-routes to question', async () => {
  const env = createEnv();
  const { result, captured } = await submitAndCapture(
    { problem: 'Como faço para guiar os personagens para fora de um loop narrativo?' }, env);
  assert.equal(result.routing.kind, 'question');
  assert.equal(result.routing.auto_detected, true);
  assert.match(captured.title, /^\[Question\]/);
});

test('omitted kind + ZH question phrasing auto-routes to question', async () => {
  const env = createEnv();
  const { result, captured } = await submitAndCapture(
    { problem: '怎么配置 MCP 服务器认证？' }, env);
  assert.equal(result.routing.kind, 'question');
  assert.equal(result.routing.auto_detected, true);
  assert.match(captured.title, /^\[Question\]/);
});

test('explicit missing_lesson with question content but no failure evidence is re-routed', async () => {
  const env = createEnv();
  const { result, captured } = await submitAndCapture(
    { kind: 'missing_lesson', problem: 'How do I guide characters out of a narrative loop?' }, env);
  assert.equal(result.routing.kind, 'question');
  assert.equal(result.routing.auto_detected, true);
  assert.match(captured.title, /^\[Question\]/);
});

test('failure submissions are never re-routed to question', async () => {
  const env = createEnv();
  // Structured error field present → missing_lesson kept.
  let { result, captured } = await submitAndCapture(
    { kind: 'missing_lesson', problem: 'How do I fix the timeout?', error: 'ReadTimeoutError' }, env);
  assert.equal(result.routing.kind, 'missing_lesson');
  assert.equal(result.routing.auto_detected, false);
  assert.match(captured.title, /^\[Intake\]/);

  // Failure keyword in problem text (no structured fields) → missing_lesson kept.
  ({ result, captured } = await submitAndCapture(
    { problem: 'pip install timed out on corporate proxy' }, env));
  assert.equal(result.routing.kind, 'missing_lesson');
  assert.equal(result.routing.auto_detected, false);
  assert.match(captured.title, /^\[Intake\]/);
  assert.ok(!captured.labels.includes('needs-human-review'));
});

test('non-missing_lesson explicit kinds are never overridden', async () => {
  const env = createEnv();
  let { result, captured } = await submitAndCapture(
    { kind: 'stale_lesson', problem: 'How do I update the outdated lesson?' }, env);
  assert.equal(result.routing.kind, 'stale_lesson');
  assert.equal(result.routing.auto_detected, false);
  assert.match(captured.title, /^\[Intake\]/);

  ({ result, captured } = await submitAndCapture(
    { kind: 'question', problem: 'anything at all' }, env));
  assert.equal(result.routing.kind, 'question');
  assert.equal(result.routing.auto_detected, false);
  assert.match(captured.title, /^\[Question\]/);
});
