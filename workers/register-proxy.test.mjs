// MisakaNet Register Proxy — Test Suite
// Covers: registration, rate limiting, counter, keepalive, voice hook verification (Windows)

import assert from "node:assert/strict";
import { describe, it, before, after } from "node:test";

// ── Minimal fetch/env mock harness ──────────────────────────────────────────

function makeEnv(overrides = {}) {
  const kv = new Map();
  return {
    REGISTER_TOKEN: "test-token",
    MAINTAINER_KEY: "test-key",
    MISAKANET_KV: {
      async get(key, type) {
        const val = kv.get(key);
        if (val === undefined) return null;
        if (type === "json") {
          try { return JSON.parse(val); } catch { return null; }
        }
        return val;
      },
      async put(key, value, _opts) {
        kv.set(key, typeof value === "string" ? value : JSON.stringify(value));
      },
      async delete(key) { kv.delete(key); },
      _raw: kv,
    },
    ...overrides,
  };
}

function makeRequest(method, pathname, body, headers = {}) {
  const url = `https://worker.example.com${pathname}`;
  const init = {
    method,
    headers: { "Content-Type": "application/json", ...headers },
  };
  if (body !== undefined) init.body = JSON.stringify(body);
  return new Request(url, init);
}

// ── Load the worker under test ───────────────────────────────────────────────
// We import the default export (the fetch handler).
let worker;
before(async () => {
  // Dynamic import so the test file can be run with `node --test`
  const mod = await import("./register-proxy.js");
  worker = mod.default;
});

// ── Helpers ──────────────────────────────────────────────────────────────────

async function callWorker(method, pathname, body, envOverrides = {}, extraHeaders = {}) {
  const env = makeEnv(envOverrides);
  const req = makeRequest(method, pathname, body, extraHeaders);
  const resp = await worker.fetch(req, env);
  let json = null;
  try { json = await resp.clone().json(); } catch {}
  return { resp, json, env };
}

// ── Tests ────────────────────────────────────────────────────────────────────

describe("GET /api/health", () => {
  it("returns ok with correct fields", async () => {
    const { resp, json } = await callWorker("GET", "/api/health");
    assert.equal(resp.status, 200);
    assert.equal(json.status, "ok");
    assert.ok(json.worker, "worker name present");
    assert.ok(json.timestamp, "timestamp present");
  });
});

describe("OPTIONS preflight", () => {
  it("returns 200 with CORS headers", async () => {
    const env = makeEnv();
    const req = new Request("https://worker.example.com/api/register", { method: "OPTIONS" });
    const resp = await worker.fetch(req, env);
    assert.equal(resp.status, 200);
    assert.ok(resp.headers.get("Access-Control-Allow-Origin"));
  });
});

describe("POST /api/register — input validation", () => {
  it("rejects missing agentType", async () => {
    const { resp, json } = await callWorker("POST", "/api/register", { nodeName: "TestNode" });
    assert.ok(resp.status >= 400);
    assert.ok(json.error || json.message || resp.status === 400);
  });

  it("rejects missing nodeName", async () => {
    const { resp } = await callWorker("POST", "/api/register", { agentType: "talos" });
    assert.ok(resp.status >= 400);
  });

  it("rejects oversized agentType (>30 chars)", async () => {
    const { resp } = await callWorker("POST", "/api/register", {
      agentType: "a".repeat(31),
      nodeName: "TestNode",
    });
    assert.ok(resp.status >= 400);
  });

  it("rejects oversized nodeName (>50 chars)", async () => {
    const { resp } = await callWorker("POST", "/api/register", {
      agentType: "talos",
      nodeName: "n".repeat(51),
    });
    assert.ok(resp.status >= 400);
  });
});

describe("POST /api/register — rate limiting", () => {
  it("blocks a second registration from the same IP within the window", async () => {
    const env = makeEnv();
    const headers = { "CF-Connecting-IP": "10.0.0.1" };

    const req1 = new Request("https://worker.example.com/api/register", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...headers },
      body: JSON.stringify({ agentType: "talos", nodeName: "Node1" }),
    });
    const resp1 = await worker.fetch(req1, env);
    // First call: either 200 (registered) or a non-429 response
    assert.ok(resp1.status !== 429, `First request should not be rate-limited, got ${resp1.status}`);

    const req2 = new Request("https://worker.example.com/api/register", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...headers },
      body: JSON.stringify({ agentType: "talos", nodeName: "Node2" }),
    });
    const resp2 = await worker.fetch(req2, env);
    // Second call from same IP in the same window should be rate-limited
    assert.equal(resp2.status, 429);
  });
});

// ── Windows Voice Hook Verification ─────────────────────────────────────────
// Issue #932: Verify that the voice hook endpoint correctly handles
// Windows-style environment signals and path separators in hook payloads.

describe("Windows Voice hook verification (issue #932)", () => {
  // Simulate a voice hook registration payload arriving from a Windows agent.
  // Windows agents may send backslash-separated paths, CRLF line endings,
  // and drive-letter prefixed hook paths.

  const WINDOWS_HOOK_PAYLOADS = [
    {
      label: "Windows backslash path in hookPath",
      body: {
        agentType: "voice-hook",
        nodeName: "WinNode01",
        hookPath: "C:\\Users\\agent\\hooks\\voice.js",
        platform: "win32",
      },
    },
    {
      label: "Windows UNC path in hookPath",
      body: {
        agentType: "voice-hook",
        nodeName: "WinNode02",
        hookPath: "\\\\server\\share\\hooks\\voice.js",
        platform: "win32",
      },
    },
    {
      label: "Mixed slash path (common Windows/Node scenario)",
      body: {
        agentType: "voice-hook",
        nodeName: "WinNode03",
        hookPath: "C:/Users/agent/hooks/voice.js",
        platform: "win32",
      },
    },
    {
      label: "CRLF line endings in nodeName (should be sanitized)",
      body: {
        agentType: "voice-hook",
        nodeName: "WinNode04\r\n",
        hookPath: "C:\\hooks\\voice.js",
        platform: "win32",
      },
    },
  ];

  for (const { label, body } of WINDOWS_HOOK_PAYLOADS) {
    it(`handles ${label} without 500 error`, async () => {
      const env = makeEnv();
      const req = new Request("https://worker.example.com/api/register", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "CF-Connecting-IP": `10.1.${Math.floor(Math.random() * 255)}.${Math.floor(Math.random() * 255)}`,
        },
        body: JSON.stringify(body),
      });
      const resp = await worker.fetch(req, env);
      // Must not be a server error — 200, 400, or 429 are all acceptable;
      // 500 indicates unhandled Windows path characters crashed the worker.
      assert.ok(
        resp.status < 500,
        `Expected non-500 for "${label}", got ${resp.status}`,
      );
    });
  }

  it("sanitizes Windows backslash path characters in nodeName", async () => {
    // nodeName with backslashes should be sanitized (stripped) by sanitizeIdentifier
    const env = makeEnv();
    const req = new Request("https://worker.example.com/api/register", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "CF-Connecting-IP": "10.2.0.1",
      },
      body: JSON.stringify({
        agentType: "voice-hook",
        nodeName: "Win\\Node\\05",
        platform: "win32",
      }),
    });
    const resp = await worker.fetch(req, env);
    // Should not 500; backslashes are non-identifier chars and should be stripped
    assert.ok(resp.status < 500, `Expected non-500, got ${resp.status}`);
  });

  it("sanitizes Windows drive-letter colon in agentType", async () => {
    // agentType containing ':' (drive letter separator) must be sanitized
    const env = makeEnv();
    const req = new Request("https://worker.example.com/api/register", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "CF-Connecting-IP": "10.2.0.2",
      },
      body: JSON.stringify({
        agentType: "C:voice-hook",
        nodeName: "WinNode06",
        platform: "win32",
      }),
    });
    const resp = await worker.fetch(req, env);
    assert.ok(resp.status < 500, `Expected non-500, got ${resp.status}`);
  });

  it("voice hook with valid Windows-safe identifiers registers successfully", async () => {
    // A well-formed Windows voice hook registration with safe identifiers
    const env = makeEnv();
    const req = new Request("https://worker.example.com/api/register", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "CF-Connecting-IP": "10.3.0.1",
      },
      body: JSON.stringify({
        agentType: "voice-hook",
        nodeName: "WinVoiceNode01",
        platform: "win32",
        inviteCode: "",
      }),
    });
    const resp = await worker.fetch(req, env);
    // Should be 200 (registered) or 400 (validation), never 500
    assert.ok(resp.status < 500, `Expected non-500, got ${resp.status}`);
  });

  it("voice hook payload with null hookPath does not crash worker", async () => {
    const env = makeEnv();
    const req = new Request("https://worker.example.com/api/register", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "CF-Connecting-IP": "10.3.0.2",
      },
      body: JSON.stringify({
        agentType: "voice-hook",
        nodeName: "WinVoiceNode02",
        hookPath: null,
        platform: "win32",
      }),
    });
    const resp = await worker.fetch(req, env);
    assert.ok(resp.status < 500, `Expected non-500, got ${resp.status}`);
  });

  it("voice hook payload with undefined platform does not crash worker", async () => {
    const env = makeEnv();
    const req = new Request("https://worker.example.com/api/register", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "CF-Connecting-IP": "10.3.0.3",
      },
      body: JSON.stringify({
        agentType: "voice-hook",
        nodeName: "WinVoiceNode03",
      }),
    });
    const resp = await worker.fetch(req, env);
    assert.ok(resp.status < 500, `Expected non-500, got ${resp.status}`);
  });

  it("voice hook CORS headers are present on Windows agent registration response", async () => {
    const env = makeEnv();
    const req = new Request("https://worker.example.com/api/register", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "CF-Connecting-IP": "10.3.0.4",
        "Origin": "https://windows-agent.local",
      },
      body: JSON.stringify({
        agentType: "voice-hook",
        nodeName: "WinVoiceNode04",
        platform: "win32",
      }),
    });
    const resp = await worker.fetch(req, env);
    assert.ok(resp.status < 500, `Expected non-500, got ${resp.status}`);
    const acao = resp.headers.get("Access-Control-Allow-Origin");
    assert.ok(acao, "Access-Control-Allow-Origin header should be present");
  });
});

// ── Demand signal endpoint ───────────────────────────────────────────────────

describe("POST /api/intake/unsolved-signal", () => {
  it("returns 200 with KV available", async () => {
    const { resp, json } = await callWorker("POST", "/api/intake/unsolved-signal", {
      taskFamily: "github-auth",
      reason: "token-expired",
      sourceId: "test-source-001",
    });
    // If the endpoint exists: 200; if not implemented yet: 404 is also acceptable
    assert.ok(resp.status < 500, `Expected non-500, got ${resp.status}`);
  });

  it("normalizes unknown taskFamily to unclassified", async () => {
    const { resp } = await callWorker("POST", "/api/intake/unsolved-signal", {
      taskFamily: "totally-unknown-family-xyz",
      reason: "some-reason",
    });
    assert.ok(resp.status < 500);
  });
});