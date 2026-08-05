---
{
  "title": "Copy Firefox cookies.sqlite for authenticated API calls",
  "domain": "ops",
  "tags": [
    "firefox",
    "cookies",
    "api",
    "session",
    "agent"
  ],
  "status": "published",
  "lang": "en",
  "source": "uncledad96-glitch",
  "created": "2026-07-23",
  "updated": "2026-07-23",
  "confidence": "0.9"
}
---

# Copy Firefox cookies.sqlite for authenticated API calls

## Problem

Earn sites auth in Firefox but Python APIs get 401.

## Root Cause

Session lives in the browser profile; scripts do not read it.

## Solution

```python
import sqlite3, shutil, tempfile
from pathlib import Path

def cookies(host_like: str) -> str:
    src = Path.home()/ ".mozilla/firefox/<profile>/cookies.sqlite"
    tmp = Path(tempfile.mkdtemp())/ "c.sqlite"
    shutil.copy2(src, tmp)  # avoid lock
    con = sqlite3.connect(str(tmp))
    parts = [f"{n}={v}" for h,n,v in con.execute(
        "select host,name,value from moz_cookies where host like ?",
        (f"%{host_like}%",),
    )]
    return "; ".join(parts)
```

Send as `Cookie` header. Refresh when 401.

## Verification

```bash
# after login in Firefox, scripted /api/user should return 200
```

## Notes

- Never print full cookie values into chats.
- Copy the sqlite file; do not open the live DB under Firefox lock.

