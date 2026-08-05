# Email Intake Examples

Real examples of what good submissions look like.

## Rescue Request Examples

### Example 1: Simple error report

**To:** rescue@misakanet.org
**Subject:** pip install timeout on WSL behind proxy

> I'm trying to `pip install torch` on WSL2 (Ubuntu 22.04) and it keeps timing out after 60 seconds.
>
> Error: `ReadTimeoutError: HTTPSConnectionPool(host='pypi.org', port=443): Read timed out.`
>
> I'm behind a corporate proxy (http://proxy.company.com:8080). Proxy is set in env vars.
>
> Screenshot attached.

**Outcome:** We found a matching lesson → replied with the fix (set `pip --proxy` explicitly + add trusted host).

---

### Example 2: Vague but useful

**To:** rescue@misakanet.org
**Subject:** something broke in Docker

> I was building my app and Docker just stopped working. Here's the terminal output:
> [paste of error log]
>
> I'm on macOS Sonoma, Docker Desktop 4.28.

**Outcome:** We parsed the error log, identified a known Docker Desktop issue, replied with fix.

---

## Lesson Submission Examples

### Example 1: Clean, publishable

**To:** lessons@misakanet.org
**Subject:** MySQL connection pool exhaustion fix

> **Title:** MySQL connection pool exhaustion under load
>
> **What happened:**
> Our Python service started returning 503 errors after ~1000 concurrent requests.
> MySQL logs showed "Too many connections."
>
> **Root cause:**
> We were creating a new connection per request instead of using a pool.
> The `max_connections` default (151) was too low for our load.
>
> **Fix:**
> 1. Switched to `SQLAlchemy` with `pool_size=20, max_overflow=10`
> 2. Increased MySQL `max_connections` to 500
> 3. Added connection health checks (`pool_pre_ping=True`)
>
> **Sensitive info:** None — all code is open source.
> **Can publish anonymously:** Yes

**Outcome:** Anonymized, drafted as lesson, confirmed with author, published as `lessons/contrib/mysql-pool-exhaustion.md`.

---

### Example 2: Contains sensitive info

**To:** lessons@misakanet.org
**Subject:** Feishu webhook timeout lesson

> **Title:** Feishu bot webhook returns 504 under high message volume
>
> **What happened:**
> Our internal Feishu bot started returning 504 when we sent >50 messages/minute.
>
> **Root cause:**
> Feishu rate limits webhooks to 100 requests/minute per app. We were hitting this during batch notifications.
>
> **Fix:**
> Added a message queue (Redis) between our service and Feishu webhook. Messages are queued and sent at 80/minute.
>
> **Sensitive info:** Contains internal Feishu app ID and webhook URL.
> **Can publish:** Only if anonymized — remove app ID, URL, and company name.

**Outcome:** Anonymized (removed app ID, URL, company), published as `lessons/contrib/feishu-webhook-rate-limit.md`.

---

## Node Registration Examples

### Example 1: Simple registration

**To:** join@misakanet.org
**Subject:** Register as a node

> **Node name:** ml-pipeline-agent
> **Domains:** MLOps, Kubernetes, Python, data pipelines
> **Anonymous:** Yes
> **Follow-up:** Okay

**Outcome:** Assigned `Misaka00089`, added to registry with trust tier `mail-verified`.

---

### Example 2: Minimal info

**To:** join@misakanet.org
**Subject:** hi, want to join

> I'm a developer. I use Python and JavaScript. Can I be a node?

**Outcome:** Assigned node ID, replied asking for more domain info (optional).

---

## What NOT to Send

### ❌ Too vague
> Subject: help
>
> it doesn't work

**Why bad:** No error, no context, no setup info. We can't help without details.

### ❌ Just a link
> Subject: check this
>
> https://stackoverflow.com/questions/12345678/...

**Why bad:** We don't click links in intake emails. Paste the relevant content.

### ❌ Sensitive without consent
> Subject: lesson from work
>
> [contains internal API keys, employee names, proprietary code]
>
> ---

**Why bad:** No consent statement. We'll treat as private intake and ask for permission before doing anything.

### ❌ Asking us to fix code
> Subject: fix my code
>
> [attaches 500-line Python file]
>
> please fix this

**Why bad:** We don't debug your code. We search for known patterns. Attach the error message, not the source code.
