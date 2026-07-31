---
{
  "title": "Cloudflare Email Worker registration traps — message.raw, MIME, and SPF",
  "domain": "devops",
  "tags": ["cloudflare", "email-worker", "kv", "turnstile", "registration", "spf"],
  "status": "published",
  "lang": "en",
  "source": "wasim-builds",
  "translated_from": "lessons/contrib/cloudflare-email-worker-registration-trap.md",
  "created": "2026-07-31",
  "updated": "2026-07-31"
}
---

# Cloudflare Email Worker registration traps — message.raw, MIME, and SPF

> English translation of `lessons/contrib/cloudflare-email-worker-registration-trap.md`

## Problem

Adding a no-GitHub-account registration channel to MisakaNet using Cloudflare Email Routing + Workers + KV. Users email a registration address → Worker auto-assigns node ID → writes to KV.

## Architecture

```
User sends email → Cloudflare Email Routing → Worker email event
  → assign node ID → write to KV → message.reply() sends confirmation
```

## Pitfalls

### Pitfall 1: message.text does not exist

**Symptom:** After deploying the Worker, email content is never received; `message.text` is undefined.

**Root cause:** Cloudflare Email Workers' `email` event handler has no `text` property. The email body must be read from `message.raw` (ReadableStream) and decoded.

**Fix:**
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

### Pitfall 2: Node.js crypto module unavailable

**Symptom:** `import { randomBytes } from 'node:crypto'` throws in the Workers runtime.

**Root cause:** Workers is not fully compatible with Node.js `crypto`. Even with `nodejs_compat` enabled, `randomBytes` may still fail.

**Fix:** Use the Web Crypto API instead.
```javascript
const array = new Uint8Array(16);
crypto.getRandomValues(array);
const token = Array.from(array, b => b.toString(16).padStart(2, '0')).join('');
```

### Pitfall 3: Reply emails rejected by QQ/163/Foxmail

**Symptom:** `message.reply()` executes successfully (no errors), but users never receive the verification email.

**Root cause:** Cloudflare's mail server IPs are not in the SPF whitelist of major Chinese mail providers. The reply is rejected or sent to spam. This is an infrastructure trust issue, not a code bug.

**Fix:** Remove the verification step. Make email-sending equivalent to registration. When the user sends an email, the Worker assigns the node ID and writes to KV immediately. The reply becomes a best-effort notification.

### Pitfall 4: Turnstile integration with forms

**Symptom:** After adding Turnstile to the web form, validation always fails.

**Root cause:** Turnstile requires the page URL to be whitelisted. Both the development `workers.dev` domain and the production domain must be added in the Cloudflare Turnstile Dashboard.

**Fix:** Add all possible frontend domains (including `workers.dev` subdomains) in the Turnstile admin UI.

## Verification

1. User/AI Agent sends email to the registration address
2. Worker `email` event triggers
3. `node_counter` increments, `node:MisakaXXXXX` written to KV
4. Reply confirmation sent (best effort)
5. Web form passes Turnstile protection + KV rate limiting

```bash
npx wrangler kv key list --binding MISAKANET_KV
# should show node:MisakaXXXXX and node_counter
```

## Lessons Learned

- Cloudflare Email Workers API differs from standard HTTP Workers: no `fetch` event with `request`, but `email` event with `message` object. `message.raw` is the only way to get the body.
- Email infrastructure reliability cannot be assumed. Whether `message.reply()` arrives depends on the recipient's SPF policy. Do not make it a critical path.
- In Workers, prefer Web standard APIs (`crypto.getRandomValues`) over Node.js APIs.
- Dual channels (email + web form) complement each other: Agents use email automation, humans use forms, same KV backend.

## Related

- `cloudflare-email-worker-registration-trap` (Chinese original)
