// submit_intake kind tests: kind whitelist + question routing (labels/title).
// Run: node --test workers/intake-kind.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import worker, { hashString } from './register-proxy-sw.js';

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

// ── PRD ⑤ §9: pull-based answer delivery (D1 questions store) ──

// Minimal D1 stub for the questions table: INSERT INTO questions (.run),
// SELECT ... WHERE dedup_hash = ?1 / status = 'answered' (.all).
function createQuestionD1(seedRows = []) {
  const rows = seedRows.map((r) => ({ ...r }));
  const selectAll = (sql, bound) => {
    if (sql.includes("status = 'answered'")) {
      return { results: rows.filter((r) => r.status === 'answered') };
    }
    if (sql.includes('WHERE dedup_hash = ?1')) {
      return { results: rows.filter((r) => r.dedup_hash === bound[0]) };
    }
    return { results: rows };
  };
  const makeStatement = (sql, bound) => ({
    async run() {
      if (String(sql).trim().startsWith('INSERT INTO questions')) {
        rows.push({
          issue_number: bound[0], dedup_hash: bound[1], problem: bound[2],
          source: bound[3], status: 'pending', issue_url: bound[4],
        });
      }
      return { meta: { changes: 1 } };
    },
    async all() {
      return selectAll(sql, bound);
    },
  });
  return {
    _rows: rows,
    prepare(sql) {
      return {
        bind: (...bound) => makeStatement(sql, bound),
        all: () => makeStatement(sql, []).all(),   // real D1: prepare().all() works without bind
      };
    },
  };
}

function contentHashOf(kind, problem, error = '') {
  // Mirror the worker: hashString(`${kind}:${safeProblem}:${safeError}`)
  return hashString(`${kind}:${problem}:${error}`);
}

test('question submit records a pending row in D1 when bound', async () => {
  const env = createEnv();
  env.MISAKANET_D1 = createQuestionD1([]);
  const { result, captured } = await submitAndCapture(
    { kind: 'question', problem: 'How do I configure MCP auth in production?' }, env);
  assert.equal(result.submitted, true);
  assert.equal(result.routing.kind, 'question');
  assert.ok(result.follow_up, 'question submit should carry a follow_up contract');
  assert.match(result.follow_up.how, /pull the answer later/i);
  const rows = env.MISAKANET_D1._rows;
  assert.equal(rows.length, 1);
  assert.equal(rows[0].status, 'pending');
  assert.equal(rows[0].issue_number, 42);
  assert.equal(rows[0].dedup_hash, contentHashOf('question', 'How do I configure MCP auth in production?'));
});

test('re-submitting an answered question returns the answer (pull)', async () => {
  const problem = 'How do I configure MCP server authentication for production?';
  const env = createEnv();
  env.MISAKANET_D1 = createQuestionD1([{
    issue_number: 1364, dedup_hash: contentHashOf('question', problem),
    problem, status: 'answered', answer: '## Answered\nRegister once per node...',
    issue_url: 'https://github.com/x/issues/1364', answered_at: '2026-09-03 00:00:00',
  }]);
  const { result } = await submitAndCapture({ kind: 'question', problem }, env);
  assert.equal(result.submitted, false);
  assert.equal(result.duplicate, true);
  assert.equal(result.answered, true);
  assert.match(result.answer, /Register once per node/);
  assert.equal(result.intake_id, 'issue-1364');
});

test('re-submitting a pending question returns the pending pointer', async () => {
  const problem = 'How should agents handle rate limits?';
  const env = createEnv();
  env.MISAKANET_D1 = createQuestionD1([{
    issue_number: 1362, dedup_hash: contentHashOf('question', problem),
    problem, status: 'pending', issue_url: 'https://github.com/x/issues/1362',
  }]);
  const { result } = await submitAndCapture({ kind: 'question', problem }, env);
  assert.equal(result.submitted, false);
  assert.equal(result.duplicate, true);
  assert.equal(result.pending, true);
  assert.ok(result.answered !== true);
  assert.match(result.note, /pending a maintainer answer/i);
});

test('search surfaces answered questions as FAQ hits', async () => {
  const { hashString: hs } = await import('./register-proxy-sw.js');
  const problem = 'How should agents handle GitHub rate limits on shared runners?';
  const env = createEnv();
  // Seed KV lessons (empty corpus → search returns no lesson results) and one
  // answered FAQ row in D1.
  env.MISAKANET_KV.put('proxy:lessons', JSON.stringify({ ts: Date.now(), data: [] }));
  env.MISAKANET_D1 = createQuestionD1([{
    issue_number: 1362, dedup_hash: hs(`question:${problem}:`),
    problem, status: 'answered',
    answer: 'Authenticate every API call to get the 5000/hour budget; honor Retry-After on 403/429.',
    issue_url: 'https://github.com/x/issues/1362',
  }]);
  const resp = await worker.fetch(new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'MCP-Protocol-Version': '2025-06-18',
      Authorization: `Bearer ${TOKEN}`,
      'CF-Connecting-IP': '203.0.113.77',
    },
    body: JSON.stringify({
      jsonrpc: '2.0', id: 1, method: 'tools/call',
      params: { name: 'misakanet_search', arguments: { query: 'how to handle GitHub rate limits on runners' } },
    }),
  }), env);
  assert.equal(resp.status, 200);
  const body = await resp.json();
  const text = JSON.parse(body.result.content[0].text);
  assert.equal(text.no_match, undefined, 'answered FAQ should suppress no_match');
  const faq = (text.results || []).find((r) => r.type === 'faq');
  assert.ok(faq, 'expected a faq result entry');
  assert.equal(faq.id, 'faq-issue-1362');
  assert.match(faq.answer, /5000\/hour/);
});

// ── Review fixes (2026-09-03 dual-axis): dedup trim parity + FAQ disclosure ──

test('padded problem text still dedups (per-field trim parity)', async () => {
  const env = createEnv();
  let captured = null;
  const restore = captureGitHubFetch(env, (p) => { captured = p; });
  try {
    const padded = '  How do I rotate an expired token?  ';
    const first = await submitIntake({ kind: 'question', problem: padded }, env);
    assert.equal(JSON.parse((await first.json()).result.content[0].text).submitted, true);
    // Same padded text again → KV dedup hit (trimmed content hash), no new issue.
    const second = await submitIntake({ kind: 'question', problem: padded }, env);
    const r2 = JSON.parse((await second.json()).result.content[0].text);
    assert.equal(r2.submitted, false);
    assert.equal(r2.duplicate, true);
  } finally {
    restore();
  }
});

test('FAQ search answer is capped unless detail=full', async () => {
  const { hashString: hs } = await import('./register-proxy-sw.js');
  const problem = 'A very long answered question about cap testing?';
  const longAnswer = 'start ' + 'x'.repeat(3000) + ' end';
  const env = createEnv();
  env.MISAKANET_KV.put('proxy:lessons', JSON.stringify({ ts: Date.now(), data: [] }));
  env.MISAKANET_D1 = createQuestionD1([{
    issue_number: 7777, dedup_hash: hs(`question:${problem}:`),
    problem, status: 'answered', answer: longAnswer, issue_url: 'https://github.com/x/issues/7777',
  }]);
  const search = async (detail) => {
    const resp = await worker.fetch(new Request('https://misakanet.org/mcp', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json', 'MCP-Protocol-Version': '2025-06-18',
        Authorization: `Bearer ${TOKEN}`, 'CF-Connecting-IP': '203.0.113.88',
      },
      body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'tools/call',
        params: { name: 'misakanet_search', arguments: { query: 'long answered question cap testing', detail } } }),
    }), env);
    const body = await resp.json();
    return JSON.parse(body.result.content[0].text);
  };
  const compact = await search('compact');
  const faqC = (compact.results || []).find((r) => r.type === 'faq');
  assert.ok(faqC, 'expected faq hit in compact');
  assert.ok(faqC.answer.length <= 900, `compact answer should be capped, got ${faqC.answer.length}`);
  const full = await search('full');
  const faqF = (full.results || []).find((r) => r.type === 'faq');
  assert.ok(faqF, 'expected faq hit in full');
  assert.ok(faqF.answer.length > 3000, 'full answer should not be capped');
});
