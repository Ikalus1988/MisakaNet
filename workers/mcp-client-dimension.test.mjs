// "14 788 calls a day" cannot answer "who is calling" — every `/mcp` request is classified `mcp`.
//
// The client dimension (#A2) reads the one place a client names itself: `params.clientInfo` on
// `initialize` (MCP spec), with `User-Agent` as the fallback for SDKs that send `node`. It lands in the
// counter family the traffic panel already reads, as its own bucket, so it costs one batched write.
//
// What this file pins: the bucket is *sanitised* (a client cannot name a bucket, inject a delimiter, or
// write 10 KB into `counters`), the fallback exists, and an `initialize` actually records it.
//
// Run: node --test workers/mcp-client-dimension.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import worker, { mcpClientBucket, MCP_CLIENT_BUCKET_PREFIX, TRAFFIC_FLUSH_BATCH } from './register-proxy-sw.js';
import { testToken } from './_test-token.mjs';

const TOKEN = testToken('mcp-client-dimension');

function createEnv() {
  const store = new Map();
  return {
    MCP_TOKEN: TOKEN,
    MISAKANET_KV: {
      async get(key, type) { return store.has(key) ? (type === 'json' ? JSON.parse(store.get(key)) : store.get(key)) : null; },
      async put(key, value) { store.set(key, String(value)); },
      async delete(key) { store.delete(key); },
    },
    _store: store,
  };
}

function initializeRequest(clientInfo, userAgent) {
  const headers = { 'Content-Type': 'application/json', 'MCP-Protocol-Version': '2025-06-18',
                    'CF-Connecting-IP': `198.51.100.${Math.floor(Math.random() * 200) + 1}` };
  if (userAgent) headers['User-Agent'] = userAgent;
  return new Request('https://misakanet.org/mcp', {
    method: 'POST', headers,
    body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'initialize',
      params: { protocolVersion: '2025-06-18', ...(clientInfo ? { clientInfo } : {}) } }),
  });
}

// ── the bucket name ───────────────────────────────────────────────────────────────────────────────

test('the bucket is the declared client, lowercased and sanitised', () => {
  const req = new Request('https://misakanet.org/mcp', { headers: { 'User-Agent': 'node' } });
  assert.equal(mcpClientBucket({ clientInfo: { name: 'Claude-Code' } }, req), 'mcpclient:claude-code');
  assert.equal(mcpClientBucket({ clientInfo: { title: 'Cursor Agent' } }, req), 'mcpclient:cursor-agent');
});

test('a client cannot name its own bucket, inject a delimiter, or write a huge string', () => {
  const req = new Request('https://misakanet.org/mcp', { headers: { 'User-Agent': 'node' } });
  // The counter key is `${bucket}|${day}` — a `|` in the name would forge a second dimension.
  assert.equal(mcpClientBucket({ clientInfo: { name: 'evil|x:agent|2026-01-01' } }, req),
               'mcpclient:evil-x-agent-2026-01-01');
  // Truncated to 32 characters, which is the bound that matters (the counters table is small and a
  // 10 KB key would be a write amplification, not a crash).
  assert.equal(mcpClientBucket({ clientInfo: { name: 'A'.repeat(5000) } }, req).length,
               MCP_CLIENT_BUCKET_PREFIX.length + 32);
  // Real control characters, not their escape text: both must become a single `-`.
  const control = `bad${String.fromCharCode(0)}na${String.fromCharCode(10)}me`;
  assert.equal(mcpClientBucket({ clientInfo: { name: control } }, req), 'mcpclient:bad-na-me');
  assert.equal(mcpClientBucket({ clientInfo: { name: '   ' } }, req), 'mcpclient:unknown');
});

test('User-Agent is the fallback, and an anonymous caller is "unknown"', () => {
  const ua = new Request('https://misakanet.org/mcp', { headers: { 'User-Agent': 'misakanet-cli/1.2' } });
  assert.equal(mcpClientBucket({}, ua), 'mcpclient:misakanet-cli-1.2');
  const none = new Request('https://misakanet.org/mcp');
  assert.equal(mcpClientBucket(undefined, none), 'mcpclient:unknown');
});

// ── the wiring ────────────────────────────────────────────────────────────────────────────────────

test('an initialize records the client in its own traffic bucket', async () => {
  const env = createEnv();
  // One flush batch's worth of initializes, so the buffered counter is written without waiting on the
  // timer (the same batching that keeps analytics from exhausting the free tier).
  for (let i = 0; i < TRAFFIC_FLUSH_BATCH; i += 1) {
    const resp = await worker.fetch(initializeRequest({ name: 'claude-code', version: '2.0' }, 'node'), env);
    assert.equal(resp.status, 200);
  }
  const day = new Date().toISOString().slice(0, 10);
  // `counters:traffic:<bucket>:<day>` — the legacy counter key shape `bumpCounter` falls back to when
  // there is no D1 binding (and the same shape the KV fallback reads).
  const key = [...env._store.keys()].find(k => k.includes(`traffic:${MCP_CLIENT_BUCKET_PREFIX}claude-code:`));
  assert.ok(key, `no client bucket was written; keys: ${[...env._store.keys()].join(', ')}`);
  assert.ok(key.endsWith(day), key);
  assert.ok(Number(env._store.get(key)) >= 1, env._store.get(key));
});

test('a client that declares nothing is counted as unknown, not dropped', async () => {
  const env = createEnv();
  for (let i = 0; i < TRAFFIC_FLUSH_BATCH; i += 1) {
    await worker.fetch(initializeRequest(null, undefined), env);
  }
  const keys = [...env._store.keys()].filter(k => k.includes(MCP_CLIENT_BUCKET_PREFIX));
  assert.ok(keys.some(k => k.includes('mcpclient:unknown')), keys.join(', '));
});

test('the analytics endpoint reports the split instead of inventing one', async () => {
  // No D1 binding: the endpoint must still answer, with an empty map rather than a fabricated split
  // (the KV fallback cannot enumerate keys, and pretending otherwise would be worse than a gap).
  const env = createEnv();
  const resp = await worker.fetch(new Request('https://misakanet.org/api/analytics/traffic'), env);
  const body = await resp.json();
  assert.equal(body.error, undefined, JSON.stringify(body));
  assert.deepEqual(body.mcpClients, {}, JSON.stringify(body));
  assert.ok(body.breakdown, 'the four original dimensions must survive');
});
