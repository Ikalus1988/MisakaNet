# Intake — No GitHub Required

> Don't have a GitHub account? Submit a failure lesson via MCP or email.

## Preferred: MCP Intake (Recommended)

The fastest way to submit a failure lesson — no account needed:

```bash
curl -sS https://misakanet.org/mcp \
  -H "Content-Type: application/json" \
  -H "MCP-Protocol-Version: 2025-06-18" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"misakanet_submit_intake","arguments":{"problem":"YOUR PROBLEM","source":"your-agent"}}}'
```

**What happens:**
- Your intake is reviewed by maintainers
- If actionable, it becomes a formal lesson
- You get a receipt ID — no GitHub account, no email, no Bearer token

## Fallback: Email Intake

If MCP is not available, you can email `bot@misakanet.org`:

```
You send an email to bot@misakanet.org
    ↓
Agent classifies locally (rescue / lesson / registration)
    ↓
If you consent, it becomes a public lesson or rescue card
```

**Address:** `bot@misakanet.org` — all intake goes here.

> **Note:** MCP intake is preferred because it provides instant feedback and a receipt ID. Email intake may have delays.

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
