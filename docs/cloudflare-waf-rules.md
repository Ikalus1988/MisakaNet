# Cloudflare WAF Rules for MisakaNet

## Overview
These rules enable AI agent-friendly access while maintaining security.

## Rule Set 1: Verified Bot Allowlist

### Rule 1: Allow All Verified Bots
- **Name:** Allow Verified Bots
- **Expression:** `cf.bot_management.verified_bot = true`
- **Action:** Allow
- **Priority:** 1
- **Description:** Allows all Cloudflare-verified bots to access the site

### Rule 2: Allow AI Agents on Public Content
- **Name:** Allow AI Agents on Public
- **Expression:** `(cf.verified_bot_category = "AI Agent" OR cf.verified_bot_category = "Search") AND http.request.uri.path ~ "^/public/"`
- **Action:** Allow
- **Priority:** 2
- **Description:** AI agents can access public content

### Rule 3: Allow AI Crawlers on Open Content
- **Name:** Allow AI Crawlers on Open
- **Expression:** `cf.verified_bot_category = "AI Crawler" AND http.request.uri.path ~ "^/(open|api|docs)"`
- **Action:** Allow
- **Priority:** 2
- **Description:** AI crawlers can access open content and API docs

### Rule 4: Rate Limit Unknown Agents
- **Name:** Rate Limit Unknown Agents
- **Expression:** `(cf.bot_score <= 29) AND (http.request.headers["Content-Type"] = ~"application/json") AND cf.bot_management.detection_ids absent`
- **Action:** Limit
- **Limit:** 100 req/min, 1000 req/day
- **Priority:** 3
- **Description:** Rate limit unknown agents making API requests

### Rule 5: Managed Challenge Unverified Bots
- **Name:** Managed Challenge Unverified
- **Expression:** `(cf.bot_score <= 49) AND NOT cf.bot_management.verified_bot AND NOT http.request.uri.path ~ "^/(api|documentation|help|open)"`
- **Action:** Managed Challenge
- **Priority:** 4
- **Description:** Interactive challenge for suspicious traffic

## Rule Set 2: Monitoring

### Rule 6: Alert High Rate AI Agent Bypass
- **Name:** Alert AI Agent Bypass
- **Expression:** `cf.verified_bot_category in ["Search", "Agent", "Training"] AND cf.bot_score == 99`
- **Action:** Alert
- **Notification:** bot-bypass-alert@example.com
- **Priority:** 10
- **Description:** Alert when AI bots bypass normal scoring

## Implementation Steps

1. Log in to Cloudflare Dashboard
2. Go to Security > WAF
3. Create Custom Rules
4. Add each rule with the expressions above
5. Test with: `curl -H "User-Agent: GPTBot/1.0" https://misakanet.org/`

## Testing

```bash
# Test Verified Bot Access
curl -H "User-Agent: GPTBot/1.0" https://misakanet.org/

# Test Public Content Access
curl -H "User-Agent: ClaudeBot/1.0" https://misakanet.org/public/

# Test Rate Limiting (should get 429 after 100 requests)
for i in {1..101}; do
  curl -H "User-Agent: UnknownBot/1.0" -H "Content-Type: application/json" https://misakanet.org/api/
done
```

## Monitoring

After deployment, monitor in:
- Security > WAF > Events
- Security > Bots > Analytics
- AI Crawl Control > Metrics
