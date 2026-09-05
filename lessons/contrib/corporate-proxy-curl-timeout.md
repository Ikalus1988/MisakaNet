---
title: 'curl Timeout Behind Corporate Proxy: SSL Inspection Breaks Certificate Validation'
domain: devops
tags:
  - proxy
  - curl
  - corporate-network
  - ssl
  - tls
  - mitm
status: published
created: '2026-09-05'
source: intake-issue-1458
evidence_level: E2
---

# curl Timeout Behind Corporate Proxy

## Problem

`curl` requests to external APIs timeout behind corporate proxy with SSL inspection enabled. Common in enterprise environments where all outbound traffic goes through a proxy that performs TLS man-in-the-middle inspection.

Symptoms:
- `curl: (60) SSL certificate problem: unable to get local issuer certificate`
- `curl: (35) OpenSSL SSL_connect: Connection reset by peer`
- Requests hang for 30-60 seconds then timeout

## Root Cause

Corporate proxy performs SSL man-in-the-middle inspection by:
1. Intercepting TLS handshake with its own CA certificate
2. Re-signing server certificates with corporate CA
3. curl validates against system CA store which doesn't include corporate CA

## Fix

**Option 1: Skip certificate verification (quick, less secure)**
```bash
curl --proxy-insecure https://api.example.com
# Or set permanently
export CURL_INSECURE=1
```

**Option 2: Add corporate CA to curl's trust store (recommended)**
```bash
# Find corporate CA (ask IT or check browser)
cp corporate-ca.crt /etc/ssl/certs/
# Or set per-request
curl --cacert /path/to/corporate-ca.crt https://api.example.com
# Or set permanently
export CURL_CA_BUNDLE=/path/to/corporate-ca.crt
```

**Option 3: Use system proxy settings**
```bash
curl --proxy http://proxy.corp:8080 https://api.example.com
# Or set permanently
export http_proxy=http://proxy.corp:8080
export https_proxy=http://proxy.corp:8080
```

## Verification

```bash
curl -sS -o /dev/null -w '%{http_code}' https://api.example.com
# Should return 200
```

## References

- [curl documentation: SSL CERTS](https://curl.se/docs/sslcerts.html)
- [Stack Overflow: curl behind corporate proxy](https://stackoverflow.com/questions/29822686)
