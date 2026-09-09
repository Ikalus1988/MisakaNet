import assert from "node:assert/strict";
import test from "node:test";
import { runKeepaliveSweep } from "./register-proxy-sw.js";

// Mock the global fetch used by probeKeepaliveEndpoint: force a rejection for
// every probe so the sweep always reports failures (simulates CF edge 522).
function forceFailFetch() {
  const original = globalThis.fetch;
  globalThis.fetch = async () => {
    throw new Error("health returned HTTP 522");
  };
  return () => {
    globalThis.fetch = original;
  };
}

function makeFakeKV() {
  const store = new Map();
  return {
    async get(key, type) {
      return store.has(key) ? store.get(key) : null;
    },
    async put(key, value, opts) {
      store.set(key, value);
    },
    async delete(key) {
      store.delete(key);
    },
    _store: store,
  };
}

test("keepalive: single failure is a warn, not an error (no throw)", async () => {
  const restore = forceFailFetch();
  const kv = makeFakeKV();
  try {
    const result = await runKeepaliveSweep("*/15 * * * *", { MISAKANET_KV: kv });
    assert.equal(result.ok, false);
    assert.equal(result.consecutive, 1);
    assert.ok(result.failures.length > 0);
    assert.equal(kv._store.get("keepalive:fail-count"), "1");
  } finally {
    restore();
  }
});

test("keepalive: escalates to throw after 3 consecutive failures", async () => {
  const restore = forceFailFetch();
  const kv = makeFakeKV();
  try {
    await runKeepaliveSweep("*/15 * * * *", { MISAKANET_KV: kv }); // 1
    const second = await runKeepaliveSweep("*/15 * * * *", { MISAKANET_KV: kv }); // 2
    assert.equal(second.consecutive, 2);
    await assert.rejects(
      () => runKeepaliveSweep("*/15 * * * *", { MISAKANET_KV: kv }), // 3 → error
      /keepalive/
    );
  } finally {
    restore();
  }
});

test("keepalive: success resets the consecutive-failure counter", async () => {
  const kv = makeFakeKV();
  kv._store.set("keepalive:fail-count", "2");
  // Default fetch succeeds against real endpoints only if network allows; stub it.
  const original = globalThis.fetch;
  globalThis.fetch = async () => new Response(JSON.stringify({ ok: true }), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
  try {
    const result = await runKeepaliveSweep("manual", { MISAKANET_KV: kv });
    assert.equal(result.ok, true);
    assert.equal(kv._store.has("keepalive:fail-count"), false);
  } finally {
    globalThis.fetch = original;
  }
});
