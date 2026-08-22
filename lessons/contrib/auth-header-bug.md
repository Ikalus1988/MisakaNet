---
{
  "title": "Moorcheh API Auth Header Bug",
  "domain": "api",
  "evidence_level": "E1",
  "author": "Liona Can",
  "source": "manual",
  "edited_at": "2026-08-21T13:12:59+08:00",
  "merged_by": "Liona Can"
}
---

# Moorcheh API Auth Header Bug

## Error Description
The Moorcheh API was not accepting authentication headers correctly, causing 401 Unauthorized errors.

## Root Cause
The API expected the auth token in the format `Bearer {token}`, but the client was sending it as `{token}` only.

## Solution
Added proper `Bearer ` prefix to the auth header before sending requests.

## Fix Details
- Added `Bearer ` prefix to the token
- Added validation to ensure token exists before sending
- Added error handling for missing tokens

## Lessons Learned
- Always check API documentation for expected header formats
- Add logging for auth failures
- Test auth flow with different scenarios

## Code Reference
```python
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}