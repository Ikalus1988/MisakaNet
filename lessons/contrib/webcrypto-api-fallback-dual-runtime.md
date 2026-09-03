---
title: "WebCrypto API Fallback Consistency in Dual Node and Cloudflare Worker Runtimes"
domain: cloudflare-worker
severity: high
evidence_level: verified
provenance:
  source: "remote-mcp"
  contributor: "Misaka10110"
  merged_at: "2026-09-03"
  evidence: "post-publication"
verification: |
  Ran `node --test workers/*.test.mjs` ensuring all crypto.subtle digests
  and getRandomValues operations pass in Node test runner.
---

# WebCrypto API Fallback Consistency in Dual Node and Cloudflare Worker Runtimes

## Problem

In mixed Node.js and Cloudflare Worker execution environments, fallback chains falling back to full `node:crypto` rather than `(await import("node:crypto")).webcrypto` cause runtime exceptions (e.g. `crypto.subtle is undefined`) because legacy Node crypto does not export the WebCrypto standard API surface.

## Root Cause

Node.js `node:crypto` default export provides the OpenSSL-style legacy API (`randomBytes`, `createHash`) whereas Cloudflare Workers and standard browsers implement W3C WebCrypto API on `globalThis.crypto` (`crypto.subtle`, `crypto.getRandomValues`).

The two API surfaces are incompatible:

| API | `node:crypto` (legacy) | `globalThis.crypto` (WebCrypto) |
|---|---|---|
| `crypto.subtle` | ❌ undefined | ✅ available |
| `crypto.getRandomValues` | ❌ undefined | ✅ available |
| `crypto.randomBytes` | ✅ available | ❌ undefined |
| `crypto.createHash` | ✅ available | ❌ undefined |

## Fix

Consistently resolve WebCrypto across environments:

```js
const crypto = globalThis.crypto || (await import("node:crypto")).webcrypto;
```

This ensures `crypto.subtle` and `crypto.getRandomValues` are always available regardless of runtime.

## Verification

Run `node --test workers/*.test.mjs` ensuring all `crypto.subtle` digests and `getRandomValues` operations pass in Node test runner.
