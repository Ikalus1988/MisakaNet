# Deploy /api/helpful endpoint

## Context

The `/api/helpful` endpoint code is already in `workers/register-proxy-sw.js` (lines 154-175).
The Cloudflare API deploy via curl fails because of modules format metadata issues.
Use wrangler to deploy instead.

## Steps (on another machine with Cloudflare access)

```bash
# 1. Clone or pull latest
git clone https://github.com/Ikalus1988/MisakaNet.git
cd MisakaNet
# or: git pull

# 2. Verify the helpful endpoint code exists
grep -n "api/helpful" workers/register-proxy-sw.js
# Should show lines 154 and 163

# 3. Deploy with wrangler (specify script name since no wrangler.toml for this worker)
npx wrangler deploy workers/register-proxy-sw.js --name misakanet-register-proxy --compatibility-date 2024-01-01

# 4. Verify
curl "https://misakanet.org/api/helpful?lesson_id=test"
# Expected: {"lesson_id":"test","count":0}

# 5. Test POST
curl -X POST "https://misakanet.org/api/helpful" \
  -H "Content-Type: application/json" \
  -d '{"lesson_id":"test"}'
# Expected: {"lesson_id":"test","count":1}
```

## What this enables

- Frontend "This helped me" button → POST /api/helpful → KV count
- Search results can show helpful counts
- Future: helpful count influences search ranking

## After deploy

Report back that deploy succeeded. The site-health check will automatically detect `api_helpful_ok: PASS`.
