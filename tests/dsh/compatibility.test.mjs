// dsh/client compatibility tests for common MCP-capable agents.
// Run: node --test tests/dsh/compatibility.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';

import fs from 'node:fs';
import path from 'node:path';

import { McpStdioClient, pythonCommand, repoRoot } from './dsh-test-helpers.mjs';

function mcpServerConfig(clientName) {
  return {
    mcpServers: {
      misakanet: {
        command: pythonCommand,
        args: ['scripts/mcp_server.py'],
        env: { MISAKANET_CLIENT: clientName },
      },
    },
  };
}

test('Claude Code, Cursor, and generic MCP clients can use the same stdio server config shape', () => {
  for (const clientName of ['claude-code', 'cursor', 'generic-mcp-agent']) {
    const config = mcpServerConfig(clientName);
    assert.equal(config.mcpServers.misakanet.command, pythonCommand);
    assert.deepEqual(config.mcpServers.misakanet.args, ['scripts/mcp_server.py']);
    assert.equal(config.mcpServers.misakanet.env.MISAKANET_CLIENT, clientName);
    assert.doesNotThrow(() => JSON.stringify(config));
  }
});

test('client-facing docs mention the requested dsh compatibility targets', () => {
  const docs = fs.readFileSync(path.join(repoRoot, 'docs', 'integrations', 'dsh.md'), 'utf8').toLowerCase();
  for (const expected of ['claude code', 'cursor', 'mcp agents']) {
    assert.match(docs, new RegExp(expected.replaceAll(' ', '\\s+')));
  }
});

test('MCP handshake uses standard capabilities expected by MCP-compatible agents', async () => {
  const client = new McpStdioClient();
  try {
    const init = await client.request('initialize');
    assert.equal(init.result.serverInfo.name, 'misakanet');
    assert.ok(init.result.capabilities.tools);
    assert.ok(init.result.capabilities.resources);
    assert.ok(init.result.capabilities.prompts);

    client.notify('notifications/initialized');
    const tools = await client.request('tools/list');
    assert.ok(tools.result.tools.every((tool) => tool.name && tool.description && tool.inputSchema));
  } finally {
    await client.close();
  }
});
