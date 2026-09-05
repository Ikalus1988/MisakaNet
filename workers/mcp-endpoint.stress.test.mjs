// Deterministic in-process stress tests for POST /mcp (issue #910).
// Run: node --expose-gc --test workers/mcp-endpoint.stress.test.mjs
import assert from 'node:assert/strict';
import { performance } from 'node:perf_hooks';
import test from 'node:test';
import worker, { MAX_MCP_REQUEST_BYTES } from './register-proxy-sw.js';

const TOKEN = 'stress-test-token';
const env = { MCP_TOKEN: TOKEN, MCP_VERSION: 'stress-test' };
const metrics = [];

function mcpRequest(body, headers = {}) {
  return new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${TOKEN}`,
      'Content-Type': 'application/json',
      ...headers,
    },
    body: typeof body === 'string' ? body : JSON.stringify(body),
  });
}

function initialize(id) {
  return mcpRequest({
    jsonrpc: '2.0',
    id,
    method: 'initialize',
    params: { protocolVersion: '2025-06-18' },
  });
}

function toolCall(id, name, args, token) {
  return new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      jsonrpc: '2.0',
      id,
      method: 'tools/call',
      params: { name, arguments: args },
    }),
  });
}

function toolResult(body) {
  return JSON.parse(body.result.content[0].text);
}

class MemoryKv {
  constructor() {
    this.values = new Map();
    this.readKeys = [];
  }

  async get(key, type) {
    this.readKeys.push(key);
    const value = this.values.get(key);
    if (value === undefined) return null;
    return type === 'json' ? JSON.parse(value) : value;
  }

  async put(key, value) {
    this.values.set(key, String(value));
  }
}

async function runBatch(count) {
  const started = performance.now();
  const responses = await Promise.all(
    Array.from({ length: count }, (_, id) => worker.fetch(initialize(id), env)),
  );
  const elapsedMs = performance.now() - started;
  return { responses, elapsedMs, requestsPerSecond: count / (elapsedMs / 1000) };
}

test('serves 100 concurrent MCP connections with valid, isolated responses', async () => {
  const { responses, elapsedMs, requestsPerSecond } = await runBatch(100);
  const bodies = await Promise.all(responses.map((response) => response.json()));

  assert.ok(responses.every((response) => response.status === 200));
  assert.deepEqual(bodies.map((body) => body.id), Array.from({ length: 100 }, (_, id) => id));
  assert.ok(bodies.every((body) => body.result?.serverInfo?.name === 'misakanet'));

  metrics.push({ scenario: '100-concurrent', requests: 100, elapsedMs, requestsPerSecond });
});

test('rejects oversized payloads with and without a Content-Length hint', async () => {
  const oversized = JSON.stringify({
    jsonrpc: '2.0', id: 1, method: 'tools/list', padding: 'x'.repeat(MAX_MCP_REQUEST_BYTES),
  });

  const declared = await worker.fetch(mcpRequest('{}', {
    'content-length': String(MAX_MCP_REQUEST_BYTES + 1),
  }), env);
  const measured = await worker.fetch(mcpRequest(oversized), env);

  assert.equal(declared.status, 413);
  assert.equal(measured.status, 413);
  assert.match((await measured.json()).error.message, /Request too large/);
});

test('returns stable errors under mixed invalid load', async () => {
  const requests = Array.from({ length: 100 }, (_, id) => {
    if (id % 2 === 0) return mcpRequest('{not-json');
    // Read tools allow anonymous access; write_lesson still requires a token.
    return new Request('https://misakanet.org/mcp', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        jsonrpc: '2.0',
        id,
        method: 'tools/call',
        params: { name: 'misakanet_write_lesson', arguments: {} },
      }),
    });
  });
  const responses = await Promise.all(requests.map((request) => worker.fetch(request, env)));

  assert.equal(responses.filter((response) => response.status === 400).length, 50);
  assert.equal(responses.filter((response) => response.status === 401).length, 50);
});

test('accepts a newly registered KV token from the write_lesson Bearer header', async (t) => {
  t.after(() => t.mock.restoreAll());
  const kv = new MemoryKv();
  const testEnv = { MISAKANET_KV: kv, REGISTER_TOKEN: 'github-test-token' };
  const registerResponse = await worker.fetch(toolCall(
    1,
    'misakanet_register',
    { agent_type: 'node-test' },
  ), testEnv);
  const registration = toolResult(await registerResponse.json());

  t.mock.method(globalThis, 'fetch', async (input, init) => {
    assert.equal(String(input), 'https://api.github.com/repos/Ikalus1988/MisakaNet/issues');
    assert.equal(init.headers.Authorization, 'Bearer github-test-token');
    return new Response(JSON.stringify({
      number: 1240,
      html_url: 'https://github.com/Ikalus1988/MisakaNet/issues/1240',
    }), {
      status: 201,
      headers: { 'Content-Type': 'application/json' },
    });
  });

  const writeResponse = await worker.fetch(toolCall(
    2,
    'misakanet_write_lesson',
    {
      title: 'KV token verification regression',
      domain: 'mcp',
      problem: 'A newly registered token was rejected by the remote MCP endpoint.',
      root_cause: 'The write path did not complete after validating the KV token record.',
      fix: 'Verify the stored token and submit the reviewed lesson through the GitHub API.',
      verification: 'Register, write with the same token, and observe a pending-review receipt.',
      source: 'node-test',
    },
    registration.token,
  ), testEnv);
  const result = toolResult(await writeResponse.json());

  assert.equal(writeResponse.status, 200);
  assert.equal(result.submitted, true);
  assert.equal(result.lesson_id, 'issue-1240');
  assert.ok(kv.readKeys.includes(`mcp_token:${registration.token}`));
  assert.equal(globalThis.fetch.mock.callCount(), 1);
});

test('repeated concurrent batches retain no unbounded heap', { skip: !global.gc }, async () => {
  await runBatch(100); // warm runtime allocations before measuring
  global.gc();
  const baseline = process.memoryUsage().heapUsed;

  for (let batch = 0; batch < 10; batch += 1) {
    const { responses } = await runBatch(100);
    await Promise.all(responses.map((response) => response.arrayBuffer()));
  }
  global.gc();

  const finalHeap = process.memoryUsage().heapUsed;
  const heapDeltaBytes = finalHeap - baseline;
  const allowedHeapGrowthBytes = 32 * 1024 * 1024;
  metrics.push({
    scenario: 'memory-retention',
    requests: 1000,
    baselineHeapBytes: baseline,
    finalHeapBytes: finalHeap,
    heapDeltaBytes,
    allowedHeapGrowthBytes,
  });
  assert.ok(
    heapDeltaBytes <= allowedHeapGrowthBytes,
    `heap grew by ${heapDeltaBytes} bytes (limit ${allowedHeapGrowthBytes})`,
  );
});

test.after(() => {
  for (const metric of metrics) {
    console.log(`MCP_STRESS_METRIC ${JSON.stringify(metric)}`);
  }
});
