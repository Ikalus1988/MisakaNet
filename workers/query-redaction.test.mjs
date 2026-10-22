// The search query must not carry the caller's machine into our storage (issue #3692).
//
// The trial user said it exactly: "报错片段会作为查询关键词发到该服务器——这意味着内部表名、路径等
// 可能随查询外发（有脱敏规则但是概率性的，靠 agent 执行不是确定性过滤）". Before this, the raw
// query reached five places: `search_signals.query` (80 chars), `lesson_usage.query` (200 chars),
// the knowledge-gap KV entry, the gap counter's bucket key, and the public analytics panel that
// publishes failed queries. The server had nine redaction rules and every one of them was a
// *secret* rule — a path and a mail address were not redacted anywhere.
//
// What this file pins:
//   * a query carrying a path and an address is stored redacted, in every place it is stored;
//   * the redaction does NOT change what the search matches (the lesson is still returned);
//   * ordinary text survives: an API route, an npm version spec and plain prose are stored as sent;
//   * a query that hits nothing still stores a redacted gap, because that is the row the public
//     analytics panel reads.
//
// Run: node --test workers/query-redaction.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import worker from './register-proxy-sw.js';
import { testToken } from './_test-token.mjs';

const TOKEN = testToken('query-redaction');

const LESSONS = [
  {
    id: 'eacces-open',
    title: 'EACCES permission denied on open',
    description: 'EACCES: permission denied, open /var/log/app/config.yaml — the service user cannot read the file.',
    domain: 'devops',
    tags: ['eacces', 'permission'],
    path: 'lessons/core/eacces-open.md',
    status: 'published',
  },
  {
    id: 'pip-timeout-mirror',
    title: 'pip install timeout',
    description: 'pip install times out on slow networks; use a mirror.',
    domain: 'python',
    tags: ['pip', 'network'],
    path: 'lessons/core/pip-timeout-mirror.md',
    status: 'published',
  },
];

/** A D1 stub that records the SQL and the bound values, so "what was stored" is observable. */
function createD1() {
  const state = { writes: [] };
  return {
    state,
    prepare(sql) {
      const stmt = {
        bound: [],
        bind(...values) { stmt.bound = values; return stmt; },
        async all() { return { results: [] }; },
        async first() { return null; },
        async run() {
          state.writes.push({ sql: String(sql), values: stmt.bound });
          return { success: true };
        },
      };
      return stmt;
    },
  };
}

function createEnv(d1) {
  const store = new Map([
    ['proxy:lessons', JSON.stringify({ ts: Date.now(), data: LESSONS })],
  ]);
  const state = { kvWrites: [] };
  return {
    state,
    env: {
      MCP_TOKEN: TOKEN,
      MCP_VERSION: 'query-redaction-test',
      MISAKANET_D1: d1,
      MISAKANET_KV: {
        async get(key, type) {
          if (!store.has(key)) return null;
          const raw = store.get(key);
          return type === 'json' ? JSON.parse(raw) : raw;
        },
        async put(key, value) {
          state.kvWrites.push({ key, value });
          store.set(key, value);
        },
        async delete(key) { store.delete(key); },
      },
    },
  };
}

/** A context that keeps the background writes so the test can await them. */
function createCtx() {
  const pending = [];
  return {
    ctx: { waitUntil(promise) { pending.push(Promise.resolve(promise).catch(() => {})); } },
    async drain() { await Promise.all(pending); },
  };
}

function searchRequest(query) {
  return new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${TOKEN}`,
      'Content-Type': 'application/json',
      'MCP-Protocol-Version': '2025-06-18',
      'CF-Connecting-IP': '198.51.100.7',
    },
    body: JSON.stringify({
      jsonrpc: '2.0',
      id: 1,
      method: 'tools/call',
      params: { name: 'misakanet_search', arguments: { query } },
    }),
  });
}

async function runSearch(query) {
  const d1 = createD1();
  const { env, state } = createEnv(d1);
  const { ctx, drain } = createCtx();
  const response = await worker.fetch(searchRequest(query), env, ctx);
  const body = await response.json();
  await drain();
  return { response, body, d1, kv: state };
}

/** Every value written to D1, flattened — the assertion is about what was stored, not where. */
function storedValues(d1) {
  return d1.state.writes.flatMap((write) => write.values.map((value) => String(value ?? '')));
}

test('a query with a path and a mail address is stored redacted, everywhere it is stored', async () => {
  const query = "EACCES: permission denied, open '/home/alice/project/secret.py' (mail alice@corp.com)";
  const { body, d1, kv } = await runSearch(query);

  const values = storedValues(d1);
  assert.ok(values.length > 0, 'nothing was written to D1, so this test proves nothing');

  for (const value of values) {
    assert.ok(!value.includes('/home/alice/project/secret.py'),
      `a raw path was stored: ${JSON.stringify(value)}`);
    assert.ok(!value.includes('alice@corp.com'),
      `a raw mail address was stored: ${JSON.stringify(value)}`);
  }
  const stored = values.join('\n');
  assert.ok(stored.includes('<PATH>'), `no path placeholder was stored: ${JSON.stringify(stored)}`);
  assert.ok(stored.includes('<REDACTED:email>'),
    `no mail placeholder was stored: ${JSON.stringify(stored)}`);

  for (const write of kv.kvWrites) {
    const value = String(write.value ?? '');
    assert.ok(!value.includes('/home/alice/project/secret.py'),
      `a raw path was stored in KV under ${write.key}: ${JSON.stringify(value)}`);
    assert.ok(!value.includes('alice@corp.com'),
      `a raw mail address was stored in KV under ${write.key}: ${JSON.stringify(value)}`);
  }
});

test('the redaction does not change what the search matches', async () => {
  const { body } = await runSearch("EACCES: permission denied, open '/home/alice/project/secret.py'");
  const text = JSON.parse(body.result.content[0].text);
  const ids = (text.results || []).map((r) => r.id);
  assert.ok(ids.includes('eacces-open'),
    `the lesson stopped matching once the path was redacted: ${JSON.stringify(ids)}`);
});

test('ordinary text is stored as it was sent', async () => {
  const query = 'npm install pkg@1.2.3 fails, POST /api/v1/users returns 403';
  const { d1 } = await runSearch(query);
  const stored = storedValues(d1).join('\n');
  assert.ok(stored.includes('pkg@1.2.3'), 'an npm version spec was redacted: ' + stored);
  assert.ok(stored.includes('/api/v1/users'), 'an API route was redacted: ' + stored);
  assert.ok(!stored.includes('<PATH>'), 'an ordinary query was redacted: ' + stored);
  assert.ok(!stored.includes('<REDACTED:email>'), 'an ordinary query was redacted: ' + stored);
});

test('a query that hits nothing still stores a redacted gap', async () => {
  // The gap row is what the public analytics panel reads ("knowledge gaps" — other people's
  // verbatim failed queries), so it is the row that must not carry a path.
  const { d1, kv } = await runSearch('nothing matches this one, from /home/alice/private/notes.txt');
  const stored = storedValues(d1).join('\n') + '\n' + kv.kvWrites.map((w) => String(w.value ?? '')).join('\n');
  assert.ok(!stored.includes('/home/alice/private/notes.txt'),
    'a raw path was stored in the gap rows: ' + stored);
  assert.ok(stored.includes('<PATH>'), 'the gap row was not redacted: ' + stored);
});
