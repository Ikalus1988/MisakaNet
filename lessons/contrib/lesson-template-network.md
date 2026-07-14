---
{
  "title": "Network Domain Lesson Template",
  "domain": "network",
  "tags": ["http", "dns", "proxy", "ssl", "websocket", "timeout", "template"],
  "status": "published",
  "source": "template",
  "created": "2026-07-13",
  "confidence": "1.0"
}
---

## Problem

Describe the network-related issue encountered.

**Symptoms:**
- What error messages appeared?
- What behavior was observed?
- What environment was affected?

## Root Cause

Explain the technical root cause.

**Network layer affected:**
- [ ] HTTP/HTTPS
- [ ] DNS resolution
- [ ] Proxy/VPN
- [ ] SSL/TLS
- [ ] WebSocket
- [ ] TCP/UDP

## Solution

Step-by-step fix.

```bash
# Diagnostic commands
curl -v https://example.com
nslookup example.com
openssl s_client -connect example.com:443
```

### Step 1: Identify the issue
### Step 2: Apply the fix
### Step 3: Verify the fix

## Verification

```bash
# Test the fix
curl -I https://example.com
# Expected: HTTP/2 200
```

## Example: SSL Certificate Verification Failure Behind Corporate Proxy

**Problem:** Agent fails to connect to external APIs behind corporate proxy with SSL inspection.

**Symptoms:**
```
SSL: CERTIFICATE_VERIFY_FAILED
```

**Root Cause:** Corporate proxy performs SSL inspection (man-in-the-middle), replacing original certificates with its own. Python's certifi bundle doesn't include the corporate CA.

**Solution:**
```bash
# 1. Export corporate CA certificate
security find-certificate -a -p /Library/Keychains/System.keychain > corporate-ca.pem

# 2. Set SSL_CERT_FILE environment variable
export SSL_CERT_FILE=/path/to/corporate-ca.pem

# 3. Or add to Python certifi bundle
python3 -c "import certifi; print(certifi.where())"
# Append corporate-ca.pem to the bundle file
```

**Verification:**
```bash
python3 -c "import urllib.request; urllib.request.urlopen('https://example.com')"
# Should succeed without SSL error
```

## Related

- [SSL/TLS basics](https://developer.mozilla.org/en-US/docs/Web/Security/Transport_Layer_Security)
- [Corporate proxy configuration](https://docs.python.org/3/library/urllib.request.html#urllib.request.ProxyHandler)
