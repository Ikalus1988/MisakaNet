# Cloudflare Managed robots.txt for MisakaNet

## Overview
Configure robots.txt to allow AI agents access to public content while protecting private areas.

## Recommended Configuration (Selective Mode)

### robots.txt Content
```
# MisakaNet - AI Agent Friendly
# Allow all verified bots to access public content

User-agent: *
Allow: /public/
Allow: /open/
Allow: /docs/
Allow: /api/search
Allow: /api/summary
Disallow: /api/
Disallow: /private/
Disallow: /member-only/
Crawl-delay: 1

# AI Crawlers - Full Access to Open Content
User-agent: GPTBot
Allow: /open/
Allow: /docs/
Allow: /api/
Disallow: /private/

User-agent: ClaudeBot
Allow: /open/
Allow: /docs/
Allow: /api/
Disallow: /private/

User-agent: Googlebot
Allow: /
Disallow: /api/private/

User-agent: Bingbot
Allow: /
Disallow: /api/private/

# Sitemap
Sitemap: https://misakanet.org/sitemap.xml
```

## Cloudflare Configuration Steps

### 1. Enable Managed robots.txt
1. Log in to Cloudflare Dashboard
2. Go to Security > Bots > AI Crawl Control
3. Click "Managed robots.txt"
4. Select "Selective" mode
5. Paste the content above
6. Save

### 2. Verify Configuration
```bash
# Check robots.txt
curl -sS https://misakanet.org/robots.txt

# Test GPTBot access
curl -H "User-Agent: GPTBot/1.0" https://misakanet.org/open/

# Test ClaudeBot access
curl -H "User-Agent: ClaudeBot/1.0" https://misakanet.org/docs/
```

### 3. Monitor Directives
- Go to AI Crawl Control > Directives
- Filter by crawler: GPTBot, ClaudeBot
- Check robots.txt compliance

## Path Structure

### Public Paths (Allow All)
- `/public/` - Public content
- `/open/` - Open access content
- `/docs/` - Documentation
- `/api/search` - Search API
- `/api/summary` - Summary API

### Private Paths (Disallow)
- `/api/` - Private API endpoints
- `/private/` - Private content
- `/member-only/` - Member-only content

## Testing Checklist

- [ ] GPTBot can access `/open/`
- [ ] ClaudeBot can access `/docs/`
- [ ] Googlebot can access `/public/`
- [ ] Unknown bots get challenge on private paths
- [ ] Sitemap is accessible
- [ ] Crawl-delay is respected

## Monitoring

After deployment, monitor in:
- AI Crawl Control > Directives
- AI Crawl Control > Metrics
- Security > Bots > Analytics
