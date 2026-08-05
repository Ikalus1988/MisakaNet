---
{
  "title": "pip install timeout / SSL errors — practical recovery",
  "domain": "python",
  "tags": ["pip", "ssl", "timeout", "venv", "network", "python"],
  "status": "published",
  "lang": "en",
  "source": "uncledad96-glitch",
  "translated_from": "lessons/contrib/pip-install-timeout-ssl.md",
  "created": "2026-07-21",
  "updated": "2026-07-21",
  "confidence": "0.9"
}
---

# pip install timeout / SSL errors — practical recovery

> English structured lesson from `lessons/contrib/pip-install-timeout-ssl.md`

## Problem

`pip install` hangs, times out, or fails with SSL/TLS certificate errors. Agents cannot install dependencies; jobs die mid-setup.

## Root Cause

Common causes:

1. Slow or blocked PyPI mirror
2. Corporate TLS interception without trusted CA
3. Default timeouts too low on large wheels
4. Broken venv pointing at wrong Python/openssl

## Solution

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip setuptools wheel

# longer timeout + retries
pip install --default-timeout=100 --retries 5 -r requirements.txt

# optional: alternate index
pip install -r requirements.txt -i https://pypi.org/simple
```

If SSL verify fails and you control the environment:

```bash
# preferred: install corporate CA into certifi bundle
# last resort only (insecure):
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org PACKAGE
```

Pin versions after success:

```bash
pip freeze > requirements.lock.txt
```

## Verification

```bash
python -c "import pkgutil; print('ok')"
pip check
```

## Notes

- Prefer venv over system pip (PEP 668 on modern Ubuntu).
- Record mirror + timeout in the project README so overnight agents reuse the working path.
- Empty inventory on earn boards is unrelated — do not confuse network install failure with "no bounties".
