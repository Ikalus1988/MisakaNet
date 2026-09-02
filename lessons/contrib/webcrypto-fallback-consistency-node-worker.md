---
title: WebCrypto API Fallback Consistency in Dual Node and Cloudflare Worker Runtimes
domain: cloudflare-worker
tags:
- webcrypto
- crypto
- nodejs
- cloudflare-worker
- fallback
- workers
status: published
created: '2026-08-31'
language: en
source: intake-issue-1398
evidence_level: E0
---

## Problem

In mixed Node.js and Cloudflare Worker execution environments, fallback chains falling back to full `node:crypto` rather than `(await import("node:crypto")).webcrypto` cause runtime exceptions (e.g. `crypto.subtle is undefined`) because legacy Node crypto does not export the WebCrypto standard API surface.

## Root Cause

Node.js `node:crypto` default export provides the OpenSSL-style legacy API (`randomBytes`, `createHash`) whereas Cloudflare Workers and standard browsers implement the W3C WebCrypto API on `globalThis.crypto` (`crypto.subtle`, `crypto.getRandomValues`). A naive `import crypto from "node:crypto"` fallback therefore surfaces an API-inconsistent object: it works for hashing but throws when the caller expects the standard WebCrypto surface.

## Fix

Consistently resolve WebCrypto across environments:

```js
const crypto = globalThis.crypto || (await import("node:crypto")).webcrypto;
```

This ensures `crypto.subtle` and `crypto.getRandomValues` are always available regardless of whether the code runs in a browser, a Cloudflare Worker, or Node.js — and that both legs of the fallback expose the same API surface.

## Verification

Ran `node --test workers/*.test.mjs` ensuring all `crypto.subtle` digests and `getRandomValues` operations pass in the Node test runner. The dual-runtime tests (`workers/register-proxy-sw.js` + `workers/register-proxy.js`) exercise both branches of the fallback chain.
