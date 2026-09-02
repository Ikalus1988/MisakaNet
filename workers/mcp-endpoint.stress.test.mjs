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
    // tools/list is a public method (registry scanners need it unauthenticated,
    // see e3796f13), so these return 200 — not 401.
    return new Request('https://misakanet.org/mcp', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ jsonrpc: '2.0', id, method: 'tools/list' }),
    });
  });
  const responses = await Promise.all(requests.map((request) => worker.fetch(request, env)));

  assert.equal(responses.filter((response) => response.status === 400).length, 50);
  // tools/list without auth is allowed (public) → all 50 succeed
  assert.equal(responses.filter((response) => response.status === 200).length, 50);
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
