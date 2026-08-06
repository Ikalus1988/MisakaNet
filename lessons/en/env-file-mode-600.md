---
{
  "title": "Keep .env and secret files at mode 600",
  "domain": "security",
  "tags": ["secrets", "chmod", "env", "security", "linux", "agent"],
  "status": "published",
  "lang": "en",
  "source": "uncledad96-glitch",
  "created": "2026-07-23",
  "updated": "2026-07-23",
  "confidence": "0.9"
}
---

# Keep .env and secret files at mode 600

## Problem

API keys in `.env` are world-readable. Other users or leaked backups expose tokens.

## Root Cause

Editors and `echo key= > .env` create mode 644 by default. umask is too open.

## Solution

```bash
umask 077
touch .env
chmod 600 .env
# after any edit
chmod 600 .env secrets/* SECRETS.local.md 2>/dev/null || true
# git hygiene
grep -q '^\.env$' .gitignore || echo '.env' >> .gitignore
```

Load without printing:

```bash
set -a
source ./.env
set +a
```

## Verification

```bash
stat -c '%a %n' .env
# expect 600
```

## Notes

- Never commit `.env`. Prefer `SECRETS.local.md` mode 600 outside the repo when possible.
- Redact secrets in logs (see log-redaction lesson).
