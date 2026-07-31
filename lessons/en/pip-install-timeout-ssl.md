---
{
  "title": "pip install timeout / SSL error fix",
  "domain": "devops",
  "tags": ["pip", "network", "SSL", "timeout", "proxy"],
  "status": "published",
  "lang": "en",
  "source": "wasim-builds",
  "translated_from": "lessons/contrib/pip-install-timeout-ssl.md",
  "created": "2026-07-31",
  "updated": "2026-07-31"
}
---

# pip install timeout / SSL error fix

> English translation of `lessons/contrib/pip-install-timeout-ssl.md`

## Problem

`pip install` fails with `timeout`, `SSL: CERTIFICATE_VERIFY_FAILED`, or `Connection broken` errors.

## Root Cause

PyPI's default source is hosted overseas. Network instability or firewall blocks cause timeouts. pip's default timeout is 15 seconds, which is insufficient for large packages.

## Fix

```bash
# 1. Use a mirror (e.g., Tsinghua University mirror)
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

# 2. Increase timeout (temporary)
pip install --default-timeout=120 <package-name>

# 3. Disable SSL verification (emergency only, not recommended for production)
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org <package-name>

# 4. Rebuild from cache (if network is down but cache has partial data)
pip install --no-cache-dir <package-name>
```

## Verification

```bash
pip install requests -v  # should complete successfully
```

## Related

- `pip-install-timeout-ssl` (Chinese original)
