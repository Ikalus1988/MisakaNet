---
{
  "title": "Normalize mixed types in links.json pack manifests",
  "domain": "ops",
  "tags": [
    "json",
    "packs",
    "superteam",
    "python",
    "agent"
  ],
  "status": "published",
  "lang": "en",
  "source": "uncledad96-glitch",
  "created": "2026-07-24",
  "updated": "2026-07-24",
  "confidence": "0.9"
}
---

# Normalize mixed types in links.json pack manifests

## Problem

`links.json` mixes URL strings and `{local, ready}` objects. Code calls `.startswith("http")` and crashes.

## Root Cause

Multiple writers evolved different value shapes without a schema.

## Solution

```python
def pack_url(val):
    if isinstance(val, str) and val.startswith("http"):
        return val
    if isinstance(val, dict):
        for k in ("url", "link", "href", "public"):
            u = val.get(k)
            if isinstance(u, str) and u.startswith("http"):
                return u
    return None

pairs = [(k, u) for k,v in data.items() if (u := pack_url(v))]
```

Upload local tarballs to a host and replace dict entries with URL strings.

## Verification

```python
assert pack_url("https://x") == "https://x"
assert pack_url({"local": "a.tgz"}) is None
assert pack_url({"url": "https://x"}) == "https://x"
```

## Notes

- One canonical shape beats clever unions under time pressure.

