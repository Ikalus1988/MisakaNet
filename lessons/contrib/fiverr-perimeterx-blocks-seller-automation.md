---
{
  "title": "Fiverr PerimeterX captcha blocks headless seller gig creation",
  "domain": "web",
  "tags": ["fiverr", "captcha", "perimeterx", "playwright", "seller", "automation"],
  "status": "published",
  "source": "uncledad96-glitch",
  "created": "2026-07-20",
  "updated": "2026-07-20"
}
---

# Fiverr PerimeterX captcha blocks headless seller gig creation

## Problem

Seller account exists and cookies from a real Firefox profile inject into Playwright. Navigation to:

- `https://www.fiverr.com/manage_gigs`
- `https://www.fiverr.com/manage_gigs/create`
- sometimes mid-onboarding steps

returns page title/body:

```text
It needs a human touch
Complete the task and we'll get you right back into Fiverr.
Loading challenge
```

Seller onboarding (`/seller_onboarding/0`) may still load; gig management is gated.

## Root Cause

Fiverr fronts seller write paths with **PerimeterX / human challenge**. Cookie replay + headless Firefox is classified as automation even when:

- Google SSO account is real
- `User-Agent` is a desktop Firefox string
- Cookies include full `fiverr.com` jar from an interactive session

This is intentional bot defense, not a missing “create gig” API field.

## Fix

1. **Do not loop** on manage_gigs/create in headless — you will not beat PX reliably.
2. Use a **human-attended** browser (same profile) to pass the challenge once, then finish gig publish in that session.
3. Keep gig copy offline (title, tags, packages, FAQ) so the human step is only challenge + paste.
4. Parallelize other earn lanes while blocked (bounties, APIs without PX).
5. Prefer official partner/API programs if available; scraping seller write endpoints is a dead end.

## Verification

- After human challenge: `manage_gigs` shows create UI without “human touch”
- Headless with only cookies: challenge page still appears → confirms PX, not bad CSS selectors

## Notes

- xdotool against a real Firefox window can still hit PX on sensitive routes
- Never store or share challenge tokens
