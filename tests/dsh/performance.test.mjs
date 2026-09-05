// dsh plugin performance smoke tests.
// Run: node --test tests/dsh/performance.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import { performance } from 'node:perf_hooks';

import { McpStdioClient, run, pythonCommand } from './dsh-test-helpers.mjs';

test('MCP server responds to initialize within a practical plugin startup budget', async () => {
  const client = new McpStdioClient();
  const started = performance.now();
  try {
    const init = await client.request('initialize', {}, 5000);
    const elapsed = performance.now() - started;
    assert.equal(init.result.serverInfo.name, 'misakanet');
    assert.ok(elapsed < 5000, `initialize took ${elapsed.toFixed(1)}ms`);
  } finally {
    await client.close();
  }
});

test('server remains stable while multiple dsh requests are in flight', async () => {
  const client = new McpStdioClient();
  try {
    const requests = [];
    for (let i = 0; i < 12; i += 1) {
      requests.push(client.request(i % 2 === 0 ? 'tools/list' : 'resources/list'));
    }
    const responses = await Promise.all(requests);
    assert.equal(responses.length, 12);
    assert.ok(responses.every((response) => response.jsonrpc === '2.0' && response.result));
  } finally {
    await client.close();
  }
});

test('server import/startup path stays lightweight enough for Node 18/20/22 CI', async () => {
  const start = performance.now();
  const result = await run(pythonCommand, ['-c', 'from scripts.mcp_server import handle_request; print(handle_request({"jsonrpc":"2.0","id":1,"method":"initialize"})["result"]["serverInfo"]["name"])']);
  const elapsed = performance.now() - start;
  assert.equal(result.code, 0, result.stderr);
  assert.match(result.stdout, /misakanet/);
  assert.ok(elapsed < 5000, `python import/initialize took ${elapsed.toFixed(1)}ms`);
});
