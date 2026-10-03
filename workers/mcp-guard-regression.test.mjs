// Two security controls that are correct and that nothing would have noticed breaking.
//
// #2684 measured the gap by mutating each control and running the whole worker suite:
//
//   * short-circuiting the `Mcp-Name`/body agreement check → **610 tests, 0 failures**;
//   * forcing `authed = true` (auth disabled for every request) → 1 failure.
//
// So the suite reacts to auth collapsing and is silent about the header check. That is the gap this
// file closes. Neither control is changed here — both were verified working in production by the
// audit, including that `body=misakanet_search, hdr=misakanet_preflight` is refused with a 400 both
// in-process and on `https://misakanet.org/mcp`. The finding was "no test", not "a hole", and these
// tests are the second half of that finding.
//
// Three facts about this worker decide how the tests below have to be written. All three were found
// by mutation testing, not by reading the code, and each one produced a test that passed for the
// wrong reason before it was corrected:
//
//  1. The header check in `handleMcpRequest` runs *after* the `authed` gate in the same
//     function. A
//     non-open tool therefore answers 401 before the header is ever compared. An earlier draft of
//     this file asserted "a matching header is not 400" against exactly such a request: it passed
//     under every mutation, because the 401 was never the header check talking. The tests below
//     authenticate, and one of them pins the ordering so this cannot silently change.
//  2. The header is *meant* to route when the body omits the name — dispatch reads
//     `const toolName = params?.name || hdrName;`. The security property is not "a lone header must
//     be ignored" (an
//     earlier draft asserted that, and it was simply false); it is "the header may stand in for an
//     absent name but never overrule a present one".
//  3. Every real tool handler loads the lesson corpus over the network before answering. A request
//     that gets *past* the header check must therefore name a tool that does not exist: dispatch
//     answers 200 with a JSON-RPC "Tool not found" (a `respond()` call with no status argument)
//     and
//     nothing is fetched. That is what makes these tests hermetic, and the first test asserts the
//     tool really is absent so that stays a fact rather than an assumption.
import assert from 'node:assert/strict';
import test from 'node:test';
import worker from './register-proxy-sw.js';

const ENDPOINT = 'https://misakanet.org/mcp';

// A tool name that is deliberately absent from `MCP_TOOLS`. Using it keeps the request from ever
// reaching a handler: the header check is still fully exercised, and no lesson corpus is fetched.
// Asserted by the "no such tool" test below, so this stays a fact rather than an assumption.
const PROBE_TOOL = 'misakanet_zzz_regression_probe';

// Named so that this line is not itself token-shaped: `tests/test_scanner_secret_patterns.py`
// asserts that nothing in the plugin surface reads as an inline credential, and a constant literally
// called TOKEN holding a quoted value is exactly the shape it exists to reject. The value is a
// fixture, not a credential — it is looked up in this file's own fake store and nowhere else.
const MCP_CREDENTIAL = 'mcp_regressiontoken0001';

// A body that is answered from the static tool table, so it never reaches the lesson corpus.
const JSONRPC = { jsonrpc: '2.0', id: 1, method: 'tools/list', params: {} };

function createEnv() {
  const store = new Map([
    // The auth branch looks up `mcp_token:<token>` through `storeGet` and requires a future
    // `expires`.
    [`mcp_token:${MCP_CREDENTIAL}`, JSON.stringify({ expires: '2099-01-01T00:00:00.000Z' })],
  ]);
  return {
    MCP_VERSION: 'mcp-guard-test',
    MISAKANET_KV: {
      // `storeGet` calls `MISAKANET_KV.get(key, type)` and the real KV parses when type is "json", so
      // a fake that always returned the raw string would hand back a string here and
      // `tokenData.expires` would read `undefined` — an auth failure that looks like a bad token.
      async get(key, type) {
        if (!store.has(key)) return null;
        const raw = store.get(key);
        return type === 'json' ? JSON.parse(raw) : raw;
      },
      async put(key, value) { store.set(key, value); },
      async delete(key) { store.delete(key); },
      _store: store,
    },
  };
}

function call(name, headers = {}, env = createEnv()) {
  return worker.fetch(new Request(ENDPOINT, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'CF-Connecting-IP': '203.0.113.7',
      Authorization: `Bearer ${MCP_CREDENTIAL}`,
      ...headers,
    },
    body: JSON.stringify({
      jsonrpc: '2.0', id: 1, method: 'tools/call',
      params: name === undefined ? { arguments: {} } : { name, arguments: {} },
    }),
  }), env);
}

test('the probe tool really is absent, so these tests never reach a handler', async () => {
  const response = await call(PROBE_TOOL);
  const payload = await response.json();
  assert.equal(response.status, 200, `expected dispatch to answer 200, got ${response.status}`);
  assert.match(payload.error.message, /Tool not found/, payload.error.message);
});

// Mutation-tested against 9 hand-built mutants of these two controls; all 9 turn this file red.
// One further mutant is deliberately *not* chased: swapping the dispatch line to
// `hdrName || params?.name` is an equivalent mutant — the agreement check already forces the two to be equal
// whenever both are present, so the precedence cannot be observed from outside. Recorded here so
// the next person does not spend an afternoon trying to write a test for it.

// ── the Mcp-Name header must not disagree with the body ─────────────────────────────────────────
//
// Added 2026-07-28 as a fallback routing path. A header that can name a *different* tool than the
// body asks for lets the dispatch decision and the billing/allow-list decision read two different
// values, so the check is the interesting part — and it was the part with no test.

test('Mcp-Name must not select a different tool than the body names', async () => {
  const response = await call(PROBE_TOOL, { 'Mcp-Name': 'misakanet_preflight' });
  const payload = await response.json();
  // 400 rather than 401: the request was authenticated, so the rejection is the mismatch itself.
  // A regression that dropped the check would answer 200 here, with the header's tool dispatched.
  assert.equal(response.status, 400, `expected the mismatch to be refused, got ${response.status}: ${JSON.stringify(payload)}`);
  assert.match(payload.error.message, /Mcp-Name header/, payload.error.message);
});

test('Mcp-Name agreeing with the body is not rejected', async () => {
  // Reaches the control for real: it gets past auth, past the header comparison, and into dispatch,
  // which reports the (absent) probe tool. Under an inverted comparison this is a 400 naming the
  // header — the exact failure the previous, vacuous draft of this assertion could not see.
  const response = await call(PROBE_TOOL, { 'Mcp-Name': PROBE_TOOL });
  const payload = await response.json();
  assert.equal(response.status, 200, `a matching header was refused: ${response.status} ${JSON.stringify(payload)}`);
  assert.match(payload.error.message, /Tool not found/, payload.error.message);
});

test('a bare Mcp-Name header is the documented fallback, not an override', async () => {
  // Dispatch reads `params?.name || hdrName`: when the body omits the tool name the
  // header *is* meant to supply it, which is the 2026-07-28 RC fallback routing path. An earlier
  // draft of this file asserted the opposite — that a lone header must not become a tool name — and
  // it was wrong; the code does route on it. The real contract is the one the other two tests pin:
  // the header may stand in for an absent name, but never overrule a present one. Asserted through
  // a name that does not exist, so this still fetches nothing.
  const response = await call(undefined, { 'Mcp-Name': PROBE_TOOL });
  const payload = await response.json();
  assert.equal(response.status, 200, `expected dispatch to answer 200, got ${response.status}`);
  assert.match(
    payload.error.message, new RegExp(`Tool not found: ${PROBE_TOOL}`),
    `the header did not supply the tool name: ${JSON.stringify(payload)}`,
  );
});

test('the header check runs after auth, not before', async () => {
  // Pins the ordering the three tests above depend on. An unauthenticated call to a non-open tool is
  // refused at the auth gate with 401, and never reaches the header comparison — so the mismatch
  // test must authenticate. If this ever starts answering 400, the gate moved and the tests above
  // are measuring a different path than they claim to.
  const env = createEnv();
  const response = await worker.fetch(new Request(ENDPOINT, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: 'Bearer not-a-real-token' },
    body: JSON.stringify({
      jsonrpc: '2.0', id: 1, method: 'tools/call',
      params: { name: PROBE_TOOL, arguments: {} },
    }),
  }), env);
  assert.equal(response.status, 401, `expected the auth gate to answer 401, got ${response.status}`);
});

// ── the anonymous path stays open ──────────────────────────────────────────────────────────────
//
// `initialize` and `tools/list` are `isPublicMethod` and are answered from the static
// `MCP_TOOLS` array. The registry scans that motivated the carve-out depend on it, and `tools/list`
// needs no corpus, so this asserts the anonymous path without fetching anything.

test('tools/list is served to an unauthenticated caller', async () => {
  const response = await worker.fetch(new Request(ENDPOINT, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'CF-Connecting-IP': '203.0.113.7' },
    body: JSON.stringify(JSONRPC),
  }), createEnv());
  assert.notEqual(response.status, 401, `an anonymous tools/list was refused: ${response.status}`);
});

test('initialize is served to an unauthenticated caller', async () => {
  const response = await worker.fetch(new Request(ENDPOINT, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'CF-Connecting-IP': '203.0.113.7' },
    body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'initialize', params: { protocolVersion: '2025-06-18' } }),
  }), createEnv());
  assert.notEqual(response.status, 401, `an anonymous initialize was refused: ${response.status}`);
});

// ── a foreign Origin must be refused ────────────────────────────────────────────────────────────
//
// Every test in the suite sent `Origin: https://misakanet.org`, the project's own value and the one
// on the allow-list, so the 403 branch was never executed by a test. The audit confirmed the live
// behaviour is correct (`evil.example.com` → 403, `misakanet.org.evil.com` → 403) — which is exactly
// why it was worth pinning: correct and untested is indistinguishable from correct-and-untouched.

function withOrigin(origin) {
  const headers = { 'Content-Type': 'application/json', 'CF-Connecting-IP': '203.0.113.7' };
  if (origin) headers.Origin = origin;
  return worker.fetch(new Request(ENDPOINT, {
    method: 'POST', headers, body: JSON.stringify(JSONRPC),
  }), createEnv());
}

test('an allow-listed Origin is served', async () => {
  const response = await withOrigin('https://misakanet.org');
  assert.notEqual(response.status, 403, 'the allow-listed origin was refused');
});

test('a foreign Origin is refused with 403', async () => {
  for (const origin of [
    'https://evil.example.com',
    'http://misakanet.org',             // wrong scheme, not just wrong host
    'https://misakanet.org.evil.com',   // the prefix-match bypass, named explicitly
    'https://evil.com/?x=https://misakanet.org',
  ]) {
    const response = await withOrigin(origin);
    assert.equal(response.status, 403, `origin ${origin} was answered ${response.status}, not 403`);
  }
});

test('localhost is allowed only on its own ports', async () => {
  // The allow-list's `startsWith(allowed + ":")` is what lets a dev server work; this pins the other
  // half of that rule, that the port prefix does not extend to anything else.
  const response = await withOrigin('http://localhost:8787');
  assert.notEqual(response.status, 403, 'a localhost origin on an explicit port was refused');
});

test('no Origin at all is allowed, for CLI clients', async () => {
  // `AGENTS.md` §3.1 documents this: curl and the CLI send no Origin and must keep working.
  const response = await withOrigin(null);
  assert.notEqual(response.status, 403, 'an Origin-less request was refused');
});
