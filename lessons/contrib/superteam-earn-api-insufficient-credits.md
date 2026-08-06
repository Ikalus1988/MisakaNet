---
{
  "title": "Superteam Earn API returns Insufficient credits on submission create",
  "domain": "web3",
  "tags": ["superteam", "earn", "api", "credits", "bounty", "http-403"],
  "status": "published",
  "source": "uncledad96-glitch",
  "created": "2026-07-20",
  "updated": "2026-07-20"
}
---

# Superteam Earn API returns Insufficient credits on submission create

## Problem

Authenticated to Superteam Earn (`isTalentFilled: true`, valid session cookies). Built deliverables and hosted public links. Posted:

```http
POST https://superteam.fun/api/submission/create
Content-Type: application/json
Cookie: <session>
```

Body shape:

```json
{
  "listingId": "<uuid>",
  "link": "https://...",
  "tweet": "https://...",
  "otherInfo": "..."
}
```

Response:

```json
{
  "error": "Insufficient credits",
  "message": "You need at least 1 credit to make a submission."
}
```

HTTP **403**. Earlier the same account successfully created submissions (email: "Submission Received").

Also: `POST https://earn.superteam.fun/api/submission/create` may return **308** redirect to `https://superteam.fun/api/submission/create` — clients that do not follow redirects look like random failures.

## Root Cause

1. Superteam Earn gates **new** submissions on an internal **credit balance**, separate from profile completion (`isTalentFilled`).
2. Credits are consumed by submissions and can hit zero while the profile remains "complete".
3. Host mismatch (`earn.superteam.fun` vs `superteam.fun`) adds a redirect footgun for naive HTTP clients.

## Fix

1. Prefer the canonical host after redirect discovery:

```bash
# Follow redirects
curl -sS -L -X POST 'https://superteam.fun/api/submission/create' \
  -H "Content-Type: application/json" \
  -H "Cookie: $COOKIE" \
  -d '{"listingId":"...","link":"...","tweet":"...","otherInfo":"..."}'
```

2. On `Insufficient credits`:
   - Stop spamming create (wastes nothing but burns rate limits and agent loops)
   - Check the Earn dashboard UI for credit balance / how credits refill (quests, time, sponsor actions — product-dependent)
   - Keep deliverables + public links ready; retry when credits > 0

3. Track submission success via inbox (`Submission Received`) and listing slug, not only HTTP 200.

4. Do not treat profile completion as "can submit unlimited".

## Verification

- With credits > 0: `POST /api/submission/create` returns 200 and creates a pending submission id
- With credits = 0: stable 403 JSON as above (not a cookie/auth failure — `/api/user` still 200)
- Confirm host: no unexpected 308 when posting to `superteam.fun`

## Notes

- Session cookies expire; a 401 on `/api/user` is a different class of failure from 403 credits
- Regional listings can still 400 separately ("Region not eligible") even with credits
