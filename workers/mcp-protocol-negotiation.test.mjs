// Protocol-version negotiation at the MCP endpoint.
//
// Why this exists: a client that proposes a revision this server does not implement is
// *negotiating*, and the spec answers that in the `initialize` result — which this worker
// already does. It used to answer the handshake itself with HTTP 400, so the session ended
// before negotiation could happen. Hermes' MCP client (mcp 0.1.0) opens with "2025-11-25" and
// therefore could not connect to MisakaNet at all, surfacing only as
// "Client error '400 Bad Request' for url 'https://misakanet.org/mcp'" (found 2026-09-15).
//
// Run: node --test workers/mcp-protocol-negotiation.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import worker from './register-proxy-sw.js';

const SUPPORTED = '2025-06-18';

function createEnv(seed = {}) {
  const store = new Map(Object.entries(seed));
  return {
    MCP_TOKEN: 'test-token',
    MCP_VERSION: 'protocol-negotiation-test',
    MISAKANET_KV: {
      async get(key, type) {
        if (!store.has(key)) return null;
        const raw = store.get(key);
        return type === 'json' ? JSON.parse(raw) : raw;
      },
      async put(key, value) { store.set(key, value); },
      _store: store,
    },
  };
}

/** The exact shape the mcp python SDK sends: header version + body protocolVersion. */
function initialize(version) {
  return worker.fetch(new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json, text/event-stream',
      'MCP-Protocol-Version': version,
      'CF-Connecting-IP': '203.0.113.7',
    },
    body: JSON.stringify({
      jsonrpc: '2.0',
      id: 0,
      method: 'initialize',
      params: { protocolVersion: version, capabilities: {}, clientInfo: { name: 'mcp', version: '0.1.0' } },
    }),
  }), createEnv());
}

async function bodyOf(response) {
  const text = await response.text();
  // An SSE-framed reply is what a client asking for text/event-stream gets.
  const line = text.split('\n').find((l) => l.startsWith('data: '));
  return JSON.parse(line ? line.slice(6) : text);
}

test('a newer protocol revision is negotiated down, not rejected', async () => {
  const response = await initialize('2025-11-25');
  assert.equal(response.status, 200,
    'the handshake must survive a client that proposes a revision we do not implement');
  const body = await bodyOf(response);
  assert.equal(body.result.protocolVersion, SUPPORTED,
    'the server answers with the revision it speaks');
});

test('a supported revision is answered as before', async () => {
  const response = await initialize(SUPPORTED);
  assert.equal(response.status, 200);
  const body = await bodyOf(response);
  assert.equal(body.result.protocolVersion, SUPPORTED);
});

test('a malformed version header is still refused', async () => {
  // Not a negotiation: nothing date-shaped came in, so the client is broken and should be told.
  const response = await initialize('not-a-version');
  assert.equal(response.status, 400);
  const body = await bodyOf(response);
  assert.match(body.error.message, /Unsupported protocol version/);
});
