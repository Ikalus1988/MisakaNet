// #1528 tests: intake conversion receipt tool and source ledger counter.
// Run: node --test workers/intake-receipt.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import worker from './register-proxy-sw.js';

const TOKEN = 'receipt-test-token';

function createEnv(initialStore = []) {
  const store = new Map(initialStore);
  return {
    MCP_TOKEN: TOKEN,
    MCP_VERSION: 'test-v1',
    MISAKANET_KV: {
      async get(key, type) {
        if (!store.has(key)) return null;
        const raw = store.get(key);
        return type === 'json' ? JSON.parse(raw) : raw;
      },
      async put(key, value) {
        store.set(key, typeof value === 'string' ? value : JSON.stringify(value));
      },
      async delete(key) {
        store.delete(key);
      },
    },
    store,
  };
}

function rpcRequest(method, params = {}) {
  return new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${TOKEN}`,
      'Content-Type': 'application/json',
      'MCP-Protocol-Version': '2025-06-18',
    },
    body: JSON.stringify({
      jsonrpc: '2.0',
      id: 1,
      method,
      params,
    }),
  });
}

test('MCP tools/list includes misakanet_intake_receipt', async () => {
  const env = createEnv();
  const resp = await worker.fetch(rpcRequest('tools/list'), env);
  assert.equal(resp.status, 200);
  const data = await resp.json();
  const tool = data.result.tools.find((t) => t.name === 'misakanet_intake_receipt');
  assert.ok(tool, 'expected misakanet_intake_receipt in tools list');
  assert.equal(tool.inputSchema.required[0], 'intake_id');
});

test('misakanet_intake_receipt returns promoted receipt from KV cache', async () => {
  const cachedReceipt = {
    found: true,
    receipt_id: 'rcpt-1528-py-async-lock-deadlock',
    source: 'crawler-test',
    intake_issue: 1528,
    lesson_id: 'py-async-lock-deadlock',
    evidence_level: 'E3',
    lesson: {
      id: 'py-async-lock-deadlock',
      title: 'Async Lock Deadlock',
      url: 'https://misakanet.org/lessons/py-async-lock-deadlock/',
      evidence_level: 'E3',
    },
    status: 'promoted',
  };
  const env = createEnv([
    ['intake_receipt:1528', JSON.stringify(cachedReceipt)],
    ['intake_receipt:issue-1528', JSON.stringify(cachedReceipt)],
  ]);

  const resp = await worker.fetch(
    rpcRequest('tools/call', {
      name: 'misakanet_intake_receipt',
      arguments: { intake_id: 'issue-1528' },
    }),
    env,
  );
  assert.equal(resp.status, 200);
  const body = await resp.json();
  assert.equal(body.error, undefined);
  const parsed = JSON.parse(body.result.content[0].text);
  assert.equal(parsed.found, true);
  assert.equal(parsed.status, 'promoted');
  assert.equal(parsed.receipt_id, 'rcpt-1528-py-async-lock-deadlock');
  assert.equal(parsed.evidence_level, 'E3');
  assert.equal(parsed.lesson.id, 'py-async-lock-deadlock');
});

test('misakanet_intake_receipt resolves from lessons cache fallback', async () => {
  const lessons = [
    {
      id: 'git-commit-dco-signoff',
      title: 'DCO Sign-off required',
      source: 'bot-intake',
      intake_issue: 8888,
      evidence_level: 'E2',
    },
  ];
  const env = createEnv([
    ['proxy:lessons', JSON.stringify({ ts: Date.now(), data: lessons })],
  ]);

  const resp = await worker.fetch(
    rpcRequest('tools/call', {
      name: 'misakanet_intake_receipt',
      arguments: { intake_id: '8888' },
    }),
    env,
  );
  assert.equal(resp.status, 200);
  const body = await resp.json();
  const parsed = JSON.parse(body.result.content[0].text);
  assert.equal(parsed.found, true);
  assert.equal(parsed.status, 'promoted');
  assert.equal(parsed.lesson.id, 'git-commit-dco-signoff');
  assert.equal(parsed.lesson.evidence_level, 'E2');
});

test('misakanet_intake_receipt returns pending_review for non-promoted intake', async () => {
  const env = createEnv([
    ['proxy:lessons', JSON.stringify({ ts: Date.now(), data: [] })],
  ]);
  const resp = await worker.fetch(
    rpcRequest('tools/call', {
      name: 'misakanet_intake_receipt',
      arguments: { intake_id: '999999' },
    }),
    env,
  );
  assert.equal(resp.status, 200);
  const body = await resp.json();
  const parsed = JSON.parse(body.result.content[0].text);
  assert.equal(parsed.found, true);
  assert.equal(parsed.status, 'pending_review');
});
