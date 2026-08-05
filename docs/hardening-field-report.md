# Production-Grade Open Source Hardening — A Field Report

## Context

A swarm-knowledge open source project underwent a full-day hardening session to transform from a single-script prototype into a dual-layer production ecosystem. This report documents the patterns used — each is generic and applicable to any open-source project approaching public scrutiny.

## Key Actions & Generic Patterns

### 1. Core Engine Extraction (PyPI Separation)

**Problem:** Monolithic repository mixing core algorithm with application logic. Hard to audit, harder for third parties to reuse.

**Pattern:** Identify the zero-dependency mathematical core. Extract into a standalone PyPI package. The main repo becomes the orchestration layer; the core package is the protocol implementation.

```
Monorepo → PyPI core package + Application repo
```

**Generic takeaway:** Any project with a well-defined algorithmic core should extract it. Benefits: independent versioning, third-party reuse, security isolation (core has no network access, no secrets).

### 2. Defensive Governance Documents

Three documents proved critical for preempting criticism:

| Document | Purpose | Generic Pattern |
|----------|---------|----------------|
| Anti-Web3 Charter | Declare no token, no fundraising, no blockchain | State what the project will *never* do. Prevents speculation narratives. |
| Limitations & Non-Goals | Honestly disclose known weaknesses | List what the system does NOT do well. Removes ammunition for FUD. |
| Machine-Readable Protocol Config | Encode all rules in JSON | Let agents read the rules directly. No human translation needed. |

### 3. Multi-Channel Registration

Three registration paths serving different user types:

| Channel | Trust Level | Anti-Abuse |
|---------|-------------|------------|
| GitHub Issue | github-verified (highest) | GitHub's own rate limits |
| Web Form | web-verified (medium) | CAPTCHA + IP rate limit + email rate limit + temp-email blocklist |
| Email | mail-verified (basic) | Email rate limit + temp-email blocklist |

**Generic takeaway:** One-size-fits-all registration excludes legitimate users. Design tiers based on what each user type naturally has (GitHub account, email, browser).

### 4. Email Worker Pitfalls (Cloudflare-Specific)

| Issue | Root Cause | Fix |
|-------|-----------|-----|
| `message.text` undefined | Email Workers use `message.raw` (stream), not `message.text` | Read from `message.raw.getReader()` |
| `node:crypto` fails | Workers prefer Web Crypto API | Use `crypto.getRandomValues()` instead |
| Reply emails blocked | SPF/DKIM not configured for reply path | Make reply best-effort; don't depend on it for critical flow |
| Turnstile fails on workers.dev | Turnstile requires domain allowlist | Add all deployment domains to Turnstile dashboard |

**Generic takeaway:** Cloudflare Email Workers have different API surfaces than HTTP Workers. Test reply deliverability before relying on it for verification flows. Always have a fallback path.

### 5. GitHub API 401 Resolution

**Problem:** Frontend calls to `api.github.com` returned 401 because browser-side calls lack authentication.

**Solution:** Deploy a Worker that proxies `api.github.com` requests with a server-side token.

```
Browser → Proxy Worker (with token) → api.github.com
```

**Generic takeaway:** Never call GitHub API directly from browser. Use a serverless proxy that injects authentication. Same pattern applies to any API that requires bearer tokens.

### 6. Code Scan Remediation

| Severity | Issue | Fix |
|----------|-------|-----|
| Error | Untrusted checkout in privileged workflow | Add `path` isolation + `safe.directory` |
| Error | Code injection via Issue body | Use `actions/github-script` instead of shell |
| Warning | Missing workflow permissions | Add explicit `permissions` block |
| Warning | Bad HTML sanitization regex | Use DOM parser instead of regex |

**Generic takeaway:** GitHub Code Scanning (CodeQL) catches real injection vectors. The top 3 fixes for workflow files: (1) never shell-evaluate user content, (2) always set explicit permissions, (3) isolate PR checkouts to subdirectories.

### 7. Dependency Layering Narrative

**Problem:** README claimed "zero-dependency" but listed optional 2GB model dependencies, creating credibility gap.

**Fix:** Replace flat "dependencies" section with a layered table:

| Layer | Dependencies | Message |
|-------|-------------|---------|
| Core engine | Zero | pip-installable standalone |
| Search CLI | Zero (delegates to core) | git clone + python3 run |
| Advanced search | ML model ~2GB | pip install [extras] |
| Federated mode | aiohttp | pip install [extras] |

**Generic takeaway:** Transparency about dependency layering builds trust. Don't claim "zero-dep" if your ecosystem includes heavy optional deps — just separate them clearly.

## Outcome

- Repository count cleaned: 33 → 13 active (20 zero-value forks archived)
- Contribution PRs from external contributor merged within the session
- PyPI package published and installable
- Three registration channels operational
- All CodeQL errors fixed

## Files Referenced

```
schemas/lesson.json           — JSON Schema for lesson validation
misaka-protocol.json          — Machine-readable config (rings, DCO, scoring, registration)
workers/email-register/       — Email + Web registration worker
workers/register-proxy.js     — GitHub API proxy worker
.github/workflows/            — All workflow files (permissions audit done)
docs/LIMITATIONS.md           — Anti-hype disclosure
GOVERNANCE.md                 — Anti-Web3 charter
```

---

*Generic principles extracted from a real hardening session. Applicable to any open-source project transitioning from prototype to production.*
