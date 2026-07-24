{
  "title": "GitHub OAuth Device Flow: authorization_pending Never Resolves",
  "domain": "devops",
  "tags": ["oauth", "github-api", "device-flow", "authentication", "headless"],
  "status": "published",
  "source": "hanyuanchen08-netizen"
}

# GitHub OAuth Device Flow: authorization_pending Never Resolves

## Problem

When using GitHub's device flow OAuth for headless/CLI authentication, the `/login/oauth/access_token` endpoint keeps returning `authorization_pending` even after the user claims they entered the code at the verification URL.

**Error:**
```
POST https://github.com/login/oauth/access_token
Response: {"error":"authorization_pending","error_description":"The authorization request is still pending."}
```

The user says they entered the code, but the token never arrives. After polling for 10 minutes, the device code expires.

## Root Cause

There are actually **three** distinct causes that all produce the same symptom:

1. **Wrong GitHub OAuth App client_id**: When using a custom OAuth App, the `client_id` in the `/login/device/code` request must match exactly the one used in the `/login/oauth/access_token` polling request. A mismatch produces `incorrect_client_credentials` after the initial `authorization_pending`.

2. **Grant type URL encoding**: The grant type parameter must be URL-encoded as `urn%3Aietf%3Aparams%3Aoauth%3Agrant-type%3Adevice_code`, not the raw string `urn:ietf:params:oauth:grant-type:device_code`. When using `curl -d`, the `:` characters can get mangled if not properly encoded.

3. **Dual account confusion**: If the user is logged into GitHub with multiple accounts in their browser, the authorization page may authorize the device code for a **different account** than the one expected. The token is issued but for a username you're not checking.

## Fix

### Step 1: Use explicit curl encoding
```bash
curl -s -X POST "https://github.com/login/oauth/access_token" \
  -H "Accept: application/json" \
  -d "client_id=YOUR_CLIENT_ID&device_code=${DEVICE_CODE}&grant_type=urn%3Aietf%3Aparams%3Aoauth%3Agrant-type%3Adevice_code"
```

### Step 2: Verify client_id consistency
```python
import httpx

# Get device code
r1 = httpx.post('https://github.com/login/device/code',
    data={'client_id': CLIENT_ID, 'scope': 'public_repo'},
    timeout=10)
device = r1.json()

# Poll with EXACT same client_id
r2 = httpx.post('https://github.com/login/oauth/access_token',
    headers={'Accept': 'application/json'},
    data={
        'client_id': CLIENT_ID,  # Must match exactly
        'device_code': device['device_code'],
        'grant_type': 'urn:ietf:params:oauth:grant-type:device_code'
    },
    timeout=15)
```

### Step 3: Poll with proper intervals
GitHub enforces a polling interval. If you get `slow_down`, increase your wait:
```python
import time

for attempt in range(12):  # 15 min = 12 × 75s
    r = httpx.post(...)
    data = r.json()
    
    if 'access_token' in data:
        print(f"✅ Token: {data['access_token'][:8]}...")
        break
    elif data.get('error') == 'slow_down':
        time.sleep(10)  # Extra wait
    elif data.get('error') == 'authorization_pending':
        time.sleep(5)  # Normal interval
    elif data.get('error') == 'expired_token':
        print("❌ User didn't authorize in time — regenerate device code")
        break
```

## Verification

```bash
# 1. Generate device code — should return user_code immediately
curl -s -X POST https://github.com/login/device/code \
  -d 'client_id=YOUR_ID&scope=public_repo' | jq .

# 2. Poll — should transition from authorization_pending to access_token within 30s of user authorizing
# 3. Verify the token works
curl -s -H "Authorization: Bearer YOUR_TOKEN" https://api.github.com/user | jq .login
```

## Key Takeaways

- The `grant_type` parameter is a URN, not a simple string — always URL-encode it
- `authorization_pending` is normal for the first few polls; it only means "user hasn't clicked yet"
- `incorrect_client_credentials` means your client_id doesn't match between the two requests
- The user must authorize at the EXACT verification URI shown in the response — not a different URL
