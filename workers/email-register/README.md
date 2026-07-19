# MisakaNet Email Register Worker

> **Status:** Experimental / Public Intake Gateway
>
> This worker is the **public-facing intake channel** for MisakaNet.
> It validates, rate-limits, and normalizes inbound email before forwarding
> to the maintainer's private Agent Mail for processing.
>
> - **Public feedback** (this worker): Cloudflare Worker → validation → bot mailbox / GitHub Issue
> - **Private feedback** (Agent Mail): bot mailbox → agent reads → rescue card / lesson draft
>
> See [private-feedback-intake.md](../../docs/private-feedback-intake.md) for the full intake architecture.

Handles node registration, lesson submission, and bug reports via email.

## Architecture

```
[New Node]
   │  email to bot@misakanet.org
   ▼
[Cloudflare Email Routing]
   │  forwards to Worker
   ▼
[MisakaNet Email Register Worker]
   │  parses → validates → assigns node ID
   │  stores in KV → replies to sender
   │  optionally creates GitHub Issue
   ▼
[Confirmation reply sent to node]
```

## Prerequisites

1. Cloudflare account with Workers Paid plan (for Email Routing)
2. Domain configured in Cloudflare (e.g., `misakanet.org`)
3. Cloudflare Email Routing enabled
4. KV namespace created

## Deployment

```bash
# 1. Create KV namespace
npx wrangler kv:namespace create MISAKANET_KV

# 2. Update wrangler.jsonc with your KV namespace ID

# 3. Set GH_TOKEN secret (optional, for logging to GitHub Issues)
npx wrangler secret put GH_TOKEN

# 4. Deploy
npx wrangler deploy

# 5. Configure Email Routing
#    Cloudflare Dashboard → Email → Routing → Add route
#    Destination: bot@misakanet.org → Worker: misakanet-email-register
```

## Email Intake (Current Setup)

**Current recommended setup:** catch-all `*@misakanet.org` → agent mailbox → agent classifies locally.

The Worker is an **experimental / future public intake gateway**. It activates when intake volume or spam risk requires automated routing.

## Optional Future Cloudflare Email Routing

When public intake volume grows, these aliases can be routed to the Worker:

| Address | Purpose | Output |
|---------|---------|--------|
| `rescue@misakanet.org` | "I'm stuck, help!" | Rescue card candidate |
| `lessons@misakanet.org` | "I fixed something" | Lesson draft |
| `join@misakanet.org` | "I want to be a node" | Node registration |
| `bot@misakanet.org` | Legacy / auto-detect | Classify by content |

> **Note:** These routes are optional. The current catch-all setup works fine for low-to-medium volume. Only enable Worker routing when you need automated filtering, rate limiting, or spam blocking at scale.

## Email Format

```
To: bot@misakanet.org
Subject: register  (or 注册 / join / Registration)

Node Name: my-agent
Public Key: ssh-ed25519 AAAAC3...
Contact: admin@example.com
```

See [docs/email-intake.md](../../docs/email-intake.md) for the full intake guide.

## Testing

```bash
# Unit-test MIME/body parsing, intake classification, and reply content
node --test workers/email-register/email-utils.test.mjs

# Validate the Worker bundle (including Cloudflare runtime imports)
npx wrangler deploy --config workers/email-register/wrangler.jsonc --dry-run

# End-to-end: send a message to bot@misakanet.org, then verify Worker logs,
# the `email-intake:*` KV record, forwarding, audit issue, and confirmation reply.
```

## Environment Variables / Secrets

| Secret | Required | Description |
|--------|----------|-------------|
| `TURNSTILE_SECRET` | Yes | Turnstile secret key for CAPTCHA verification (set via `wrangler secret put`) |
| `GH_TOKEN` | No | GitHub PAT for creating audit Issues |
| `GH_REPO` | No | Audit repository (defaults to `Ikalus1988/MisakaNet`) |
| `MAINTAINER_EMAIL` | No | Verified Email Routing destination for forwarded copies |
| `MISAKANET_KV` | Yes (binding) | KV namespace for counters, stable sender/node mapping, and intake records |

## GitHub Issue Sync

If `GH_TOKEN` is configured, the Worker creates an audit Issue in `GH_REPO`.
Lesson submissions use `lesson-intake`; other intake uses `registered` + `email`.
