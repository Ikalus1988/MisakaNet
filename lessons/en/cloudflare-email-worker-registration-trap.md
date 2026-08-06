---
{
  "title": "Cloudflare Email Worker registration notes — message.raw, MIME, and SPF",
  "domain": "devops",
  "tags": ["cloudflare", "email-worker", "kv", "turnstile", "registration", "spf"],
  "status": "published",
  "lang": "en",
  "source": "uncledad96-glitch",
  "translated_from": "lessons/contrib/cloudflare-email-worker-registration-trap.md",
  "created": "2026-08-02",
  "updated": "2026-08-02",
  "confidence": "0.9"
}
---

# Cloudflare Email Worker registration notes — message.raw, MIME, and SPF

## Problem

Adding a no-GitHub registration channel using Cloudflare Email Routing + Workers + KV. The goal: users send mail to a registration address → Worker assigns a node ID → stores it in KV. Four separate pitfalls blocked deployment.

## Root Cause

1. **`message.text` does not exist.** Cloudflare Email Workers `email` event handler has no `text` property. The body must be read from `message.raw` (a `ReadableStream`) and decoded manually.
2. **Node.js `crypto` module is unavailable.** Workers does not fully support Node.js `crypto`. Even with `nodejs_compat` enabled, `randomBytes` may fail. The Web Crypto API is the supported path.
3. **Reply mail rejected by QQ / 163 / Foxmail.** Cloudflare sending IPs are not on the SPF whitelist of major Chinese mail providers. The reply is rejected or marked as spam. This is an infrastructure trust issue, not a code bug.
4. **Turnstile + form integration fails.** Turnstile requires the page URL to be whitelisted. Both the `workers.dev` development domain and the production domain must be added in the Turnstile dashboard.

## Solution

### Pitfall 1: Read `message.raw`

```javascript
let rawText = '';
const reader = message.raw.getReader();
const decoder = new TextDecoder();
while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  rawText += decoder.decode(value, { stream: true });
}
```

Reference: [Cloudflare Email Workers docs](https://developers.cloudflare.com/email-routing/email-workers/)

### Pitfall 2: Use Web Crypto API

```javascript
const array = new Uint8Array(16);
crypto.getRandomValues(array);
const token = Array.from(array, b => b.toString(16).padStart(2, '0')).join('');
```

### Pitfall 3: Make mail best-effort

Remove verification from the critical path. Treat inbound mail as registration itself: assign the node ID and write KV on receipt. The reply becomes best-effort notification. This follows the "尽力交付" (best-effort delivery) pattern used elsewhere in the MisakaNet stack.

### Pitfall 4: Whitelist all domains in Turnstile

Add every frontend domain (including `workers.dev` subdomains) to the Turnstile allowlist. Verify with:

```bash
curl -X POST https://challenges.cloudflare.com/turnstile/v0/siteverify \
  -d "secret=<SECRET_baac7e50>&response=<token>"
```

## Verification

1. User / AI Agent sends mail to the registration address.
2. Worker `email` event fires.
3. `node_counter` increments; `node:MisakaXXXXX` is written to KV.
4. Confirmation reply is attempted (best-effort).
5. Web form passes Turnstile + KV rate limit.

```bash
npx wrangler kv key list --binding MISAKANET_KV
# Expect node:MisakaXXXXX and node_counter entries
```

## Lesson Learned

- Cloudflare Email Workers API differs from standard HTTP Workers: there is no `fetch` event `request`, only an `email` event `message`. `message.raw` is the only way to access the body.
- Mail infrastructure reliability cannot be assumed. Whether `message.reply()` reaches the recipient depends on the receiver's SPF policy; do not make it a critical path.
- Prefer Web standard APIs (`crypto.getRandomValues`) over Node.js APIs inside Workers.
- Dual-channel (mail + web form) complement each other: Agents automate via mail, humans use the form, both share the same KV backend.
