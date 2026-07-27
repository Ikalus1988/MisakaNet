# Email Intake — No GitHub Required

> Don't have a GitHub account? Send us a debugging story by email — or use curl.

## Current Setup

### Email Channel

```
You send an email to bot@misakanet.org
    ↓
Agent mailbox receives it (catch-all)
    ↓
Agent classifies locally (rescue / lesson / registration)
    ↓
Agent replies to confirm receipt
    ↓
Agent anonymizes and processes your submission
    ↓
If you consent, it becomes a public lesson or rescue card
```

**Address:** `bot@misakanet.org` — all intake goes here.

> Catch-all `*@misakanet.org` is active — if you write to any address @misakanet.org, we'll receive it. But `bot@` is the recommended address.

### Curl / API Channel (NEW)

```
You POST JSON to https://misakanet.org/api/intake
    ↓
Worker validates, redacts secrets, rate-limits
    ↓
Intake stored in KV with 90-day TTL
    ↓
Use scripts/intake_digest.py to pull and classify
    ↓
If consent is allow_anonymous_publish, it may become public
```

**Usage:**
```bash
curl -X POST https://misakanet.org/api/intake \
  -H "Content-Type: application/json" \
  -d '{
    "type": "diagnostic",
    "source": "curl",
    "message": "pip install keeps timing out behind corporate proxy",
    "context": {"tool": "pip", "version": "24.0", "platform": "linux"},
    "consent": "private_only"
  }'
```

**Intake types:** `diagnostic`, `lesson_candidate`, `friction`, `bug`, `node_join`, `unsolved`

**Sources:** `mcp`, `curl`, `frontend`, `agent`

**Consent options:**
- `private_only` (default): Intake stays private, informs internal notes only
- `allow_anonymous_publish`: May be published anonymously after review

**Security guarantees:**
- IP rate limited (10/hour)
- Max body 8KB
- Secrets automatically redacted (tokens, keys, passwords)
- No auto GitHub issue creation
- No auto public lesson publishing
- No attachment/link execution

## How It Works
If you consent, it becomes a public lesson or rescue card
```

## Three Intake Channels

### rescue@misakanet.org — "I'm stuck, help!"

For when you're hitting an error and need help.

**What to write:**
1. What were you trying to do?
2. What went wrong? (paste the error or attach a screenshot)
3. What's your setup? (OS, tool, language — if you know)

**What happens:**
- We search our knowledge base for a matching fix
- If found, we reply with the solution
- If not, we log it as a rescue request for future lessons

**Example:**
> Subject: pip install keeps timing out
>
> I'm trying to install packages on WSL and pip keeps timing out after 30 seconds.
> I'm behind a corporate proxy. Screenshot attached.

---

### lessons@misakanet.org — "I fixed something, here's how"

For when you solved a problem and want to share the fix.

**What to write:**
1. Title: what was the problem?
2. What happened?
3. How did you fix it?
4. Is there anything that can't be shared publicly?
5. Can we publish this anonymously? (yes / no)

**What happens:**
- We anonymize your submission (remove names, emails, internal domains)
- We draft a lesson file
- We ask you to confirm before publishing
- If you said yes, it joins the public knowledge base

**Example:**
> Subject: Docker build fails on M1 Mac with Python 3.12
>
> Problem: `docker build` fails with `exec format error` on Apple Silicon.
> Cause: The Dockerfile used `python:3.12` (amd64 only).
> Fix: Changed to `python:3.12-slim` and added `--platform=linux/amd64`.
> Can publish anonymously: yes

---

### join@misakanet.org — "I want to be a node"

For when you want to register as a MisakaNet node.

**What to write:**
1. Node name (pick any alias)
2. What are you good at? (domains, tools, languages)
3. Are you okay with being listed anonymously?
4. Can we email you follow-up questions?

**What happens:**
- We assign you a stable node ID (e.g., `Misaka00123`)
- We add you to the node registry
- You can use your node ID in the ecosystem

**Example:**
> Subject: Join as a node
>
> Node name: rustacean-agent
> Domains: Rust, WebAssembly, systems programming
> Anonymous: yes
> Follow-up: okay

---

## Privacy & Consent

- **We never publish your name, email, or company without permission**
- **Sensitive info is stripped** before any content enters the public knowledge base
- **You can request deletion** at any time — just reply to the original email
- **Private submissions** stay private — they inform our internal rescue notes but are never published

If your email contains company secrets, internal URLs, or personal data, tell us:
> "This contains sensitive info — do not publish."

We'll treat it as a private intake and only use it to improve our internal knowledge.

## What We Don't Accept

- Spam or unsolicited marketing
- Content that violates others' privacy
- Requests to execute code or click links in attachments
- Submissions that are just "fix this for me" with no context

## Auto-Reply

When we receive your email, we reply:

> Got it. You don't need a GitHub account.
>
> If this is an error report, reply with a screenshot.
> If this is a lesson, reply "allow anonymous publish."
> If it contains sensitive info, we'll anonymize before processing.
