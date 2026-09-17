// Registration storage on D1 (2026-09-17).
//
// Why: `misakanet_register` writes `node:<id>` and `mcp_token:<token>` — both *new* keys on every
// call — and the free tier caps KV at 1,000 distinct keys written per day (a same-key rewrite is
// exempt). #1647 measured that failure live on 2026-09-12 and moved the counters to D1; the
// registration keys were the part left behind, and on 2026-09-17 every registration answered
// `storage_unavailable` while KV *reads* still worked — so every new user got no token, i.e. only
// the anonymous 5-reads/day, and no write tools at all.
//
// These tests drive the real HTTP path with a KV stub whose *writes* fail (exactly the production
// condition) and a D1 stub, and pin four properties:
//
//   * registration succeeds, and the token it hands out authenticates;
//   * node ids stay unique — the KV counter was best-effort, so under a write outage every
//     registration would have read the same stale value and minted the same node;
//   * /api/counter keeps moving (it read KV only, so it froze for 6.5 hours that day);
//   * the old contracts still hold: KV-only deployments keep working, a token issued before this
//     table existed still authenticates, and when *neither* store works registration still
//     refuses rather than handing out a token it could not save.
//
// Run: node --test workers/register-storage-d1.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import worker from './register-proxy-sw.js';
import { testToken } from './_test-token.mjs';

// Real tokens start with mcp_ and carry `expires`; the pre-dispatch auth keys on both.
const LEGACY_TOKEN = `mcp_${testToken('legacy-node')}`;
const KV_NODE_COUNTER = 10262;
const LESSONS = [
  { id: 'pip-timeout-mirror', title: 'pip install timeout', domain: 'python', status: 'published',
    tags: ['pip', 'network'], path: 'lessons/core/pip-timeout-mirror.md',
    problem: 'pip install times out behind a corporate proxy.',
    solution: 'Raise --default-timeout or use a mirror', updated: '2026-09-15T00:00:00Z' },
];
const LEGACY_KV = new Map([
  ['node_counter', String(KV_NODE_COUNTER)],
  // Seeded so the lesson loader answers from the cache instead of calling GitHub (no token here).
  ['proxy:lessons', JSON.stringify({ ts: Date.now(), data: LESSONS })],
  [`mcp_token:${LEGACY_TOKEN}`,
    JSON.stringify({
      node_id: 'Misaka10001', agent_type: 'legacy', registered_at: '2026-09-01T00:00:00Z',
      expires: '2099-01-01T00:00:00.000Z',
    })],
]);

/** KV whose reads work and whose writes fail — the 2026-09-17 production shape. */
function kvStub(store, { failWrites = true } = {}) {
  const writes = [];
  return {
    _writes: writes,
    async get(key, type) {
      if (!store.has(key)) return null;
      const raw = store.get(key);
      return type === 'json' ? JSON.parse(raw) : raw;
    },
    async put(key, value) {
      if (failWrites) throw new Error('KV put() limit exceeded for the day.');
      writes.push(key);
      store.set(key, value);
    },
    async delete(key) { store.delete(key); },
  };
}

/** Minimal D1 that understands the statements the register path issues. */
function d1Stub({ fail = false } = {}) {
  const kv = new Map();
  const counters = new Map();
  const ddl = [];
  const c = (scope, bucket, period) => `${scope}|${bucket}|${period}`;
  return {
    _kv: kv,
    _counters: counters,
    _ddl: ddl,
    prepare(sql) {
      const stmt = {
        _bound: [],
        bind(...args) { stmt._bound = args; return stmt; },
        async run() {
          if (fail) throw new Error('D1_ERROR: no such table');
          if (sql.includes('CREATE TABLE IF NOT EXISTS kv_store')) { ddl.push('kv_store'); return { success: true }; }
          if (sql.includes('INSERT INTO kv_store')) {
            kv.set(String(stmt._bound[0]), { value: stmt._bound[1], expires_at: stmt._bound[2] });
            return { success: true };
          }
          if (sql.includes('INSERT INTO counters')) {
            // Two shapes reach D1: the quota upsert binds (scope, bucket, period, delta); the node
            // counter binds only the seed and spells the rest as literals (see nextNodeCounter).
            const key = stmt._bound.length >= 4 ? c(stmt._bound[0], stmt._bound[1], stmt._bound[2]) : c('node', 'all', 'all-time');
            const next = counters.has(key) ? counters.get(key) + 1 : Number(stmt._bound[stmt._bound.length - 1]);
            counters.set(key, next);
            return { success: true };
          }
          return { success: true };
        },
        async all() {
          if (fail) throw new Error('D1_ERROR: no such table');
          if (sql.includes('SELECT value FROM kv_store')) {
            const row = kv.get(String(stmt._bound[0]));
            if (!row) return { results: [] };
            if (row.expires_at && row.expires_at <= new Date().toISOString()) return { results: [] };
            return { results: [{ value: row.value }] };
          }
          if (sql.includes('SELECT count FROM counters')) {
            const key = c('node', 'all', 'all-time');
            return counters.has(key) ? { results: [{ count: counters.get(key) }] } : { results: [] };
          }
          // INSERT ... RETURNING count
          if (sql.includes('INSERT INTO counters') && sql.includes('RETURNING')) {
            const key = stmt._bound.length >= 4 ? c(stmt._bound[0], stmt._bound[1], stmt._bound[2]) : c('node', 'all', 'all-time');
            const next = counters.has(key) ? counters.get(key) + 1 : Number(stmt._bound[stmt._bound.length - 1]);
            counters.set(key, next);
            return { results: [{ count: next }] };
          }
          // Lesson reads and anything else: an empty corpus is fine for these tests.
          return { results: [] };
        },
      };
      return stmt;
    },
  };
}

function env({ kv = true, d1 = true, store = new Map(LEGACY_KV), failKvWrites = true } = {}) {
  const e = { REGISTER_TOKEN: testToken('register-token') };
  if (kv) e.MISAKANET_KV = kvStub(store, { failWrites: failKvWrites });
  if (d1) e.MISAKANET_D1 = d1Stub();
  return e;
}

function registerRequest(clientId) {
  return new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'MCP-Protocol-Version': '2025-06-18',
      'CF-Connecting-IP': '198.51.100.7',
    },
    body: JSON.stringify({
      jsonrpc: '2.0', id: 1, method: 'tools/call',
      params: { name: 'misakanet_register', arguments: { agent_type: 'test', client_id: clientId } },
    }),
  });
}

async function callRegister(environment, clientId) {
  const resp = await worker.fetch(registerRequest(clientId), environment, {});
  const body = await resp.json();
  return JSON.parse(body.result.content[0].text);
}

test('registration succeeds on D1 while every KV write is failing', async () => {
  const environment = env();
  const result = await callRegister(environment, 'd1-first-client-0001');
  assert.equal(result.error, undefined, `registration failed: ${JSON.stringify(result)}`);
  assert.match(String(result.token || ''), /^mcp_/, JSON.stringify(result));
  assert.ok(result.node_id, JSON.stringify(result));
  // The write went to the durable store, not to KV: KV was never even asked to persist.
  assert.equal(environment.MISAKANET_KV._writes.length, 0);
});

test('two registrations under a KV write outage get different node ids', async () => {
  // The KV counter is best-effort, so under a write outage both calls would have read the same
  // stale value and minted the *same* node id — two agents sharing one pseudonym.
  const environment = env();
  const a = await callRegister(environment, 'unique-node-client-0001');
  const b = await callRegister(environment, 'unique-node-client-0002');
  assert.notEqual(a.node_id, b.node_id, `duplicate node id: ${a.node_id}`);
  assert.equal(environment.MISAKANET_D1._counters.get('node|all|all-time'), KV_NODE_COUNTER + 2);
});

test('the node counter continues where the KV counter stopped', async () => {
  const environment = env();
  const first = await callRegister(environment, 'seed-client-0000000001');
  assert.equal(
    first.node_id,
    `Misaka${KV_NODE_COUNTER + 1}`,
    'the first D1 row must seed from the KV value, or ids would restart and collide',
  );
});

test('/api/counter keeps moving off the D1 counter', async () => {
  const environment = env();
  await callRegister(environment, 'counter-client-0000001');
  const resp = await worker.fetch(new Request('https://misakanet.org/api/counter'), environment, {});
  assert.equal(resp.status, 200);
  const body = await resp.json();
  // The mirror file has no REGISTER_TOKEN in this stub, so a KV-only reader would report the
  // frozen 10262 while D1 already knows about the new node.
  assert.equal(Number(body.current), KV_NODE_COUNTER + 1, JSON.stringify(body));
});

test('a token written to D1 authenticates the next call', async () => {
  const environment = env();
  const { token } = await callRegister(environment, 'auth-client-0000000001');
  assert.ok(token);
  const resp = await worker.fetch(new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
      'MCP-Protocol-Version': '2025-06-18',
      'CF-Connecting-IP': '198.51.100.7',
    },
    body: JSON.stringify({
      jsonrpc: '2.0', id: 2, method: 'tools/call',
      params: { name: 'misakanet_preflight', arguments: { intent: 'rm -rf build/' } },
    }),
  }), environment, {});
  const body = await resp.json();
  const result = JSON.parse(body.result.content[0].text);
  assert.equal(result.error, undefined, `token from D1 was rejected: ${JSON.stringify(result)}`);
});

test('a token issued before the table existed still authenticates (KV read fallback)', async () => {
  const environment = env();
  const resp = await worker.fetch(new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${LEGACY_TOKEN}`,
      'Content-Type': 'application/json',
      'MCP-Protocol-Version': '2025-06-18',
      'CF-Connecting-IP': '198.51.100.8',
    },
    body: JSON.stringify({
      jsonrpc: '2.0', id: 3, method: 'tools/call',
      params: { name: 'misakanet_preflight', arguments: { intent: 'ls' } },
    }),
  }), environment, {});
  const body = await resp.json();
  const result = JSON.parse(body.result.content[0].text);
  assert.equal(result.error, undefined, `legacy KV token rejected: ${JSON.stringify(result)}`);
});

test('without D1 the KV path is unchanged (deployments without the binding)', async () => {
  const store = new Map(LEGACY_KV);
  const environment = env({ d1: false, store, failKvWrites: false });
  const result = await callRegister(environment, 'kv-only-client-00000001');
  assert.equal(result.error, undefined, JSON.stringify(result));
  assert.equal(result.node_id, `Misaka${KV_NODE_COUNTER + 1}`);
  assert.ok(store.has(`mcp_token:${result.token}`), 'the token must still land in KV');
});

test('when neither store works, registration still refuses to hand out a token', async () => {
  // The contract from workers/kv-write-failure.test.mjs: storage trouble may cost counters and
  // caching, it may not cost a caller a token that was never saved. D1 first does not change
  // that — it only removes KV's per-day new-key ceiling from the path.
  const environment = env({ store: new Map(LEGACY_KV) });
  environment.MISAKANET_D1 = d1Stub({ fail: true });
  const result = await callRegister(environment, 'both-stores-down-00001');
  assert.equal(result.token, undefined, 'a token that nothing stored must not be returned');
  assert.equal(result.code, 'storage_unavailable', JSON.stringify(result));
});
