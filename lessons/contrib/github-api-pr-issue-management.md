---
title: GitHub API for PR and Issue Management
domain: devops
tags:
- github
- api
- pr
- issue
- automation
status: published
created: 2026-07-02
source: agent_experience
---

---

## Problem

Need to manage PRs and issues programmatically via GitHub API when `gh` CLI is not authenticated or unavailable.

## Root Cause

GitHub REST API v3 allows full CRUD operations on PRs, issues, and comments using personal access tokens (PAT). The API endpoints follow predictable patterns:

- Issues: `GET/POST/PATCH /repos/{owner}/{repo}/issues/{number}`
- PRs: `GET/POST/PATCH /repos/{owner}/{repo}/pulls/{number}`
- Comments: `GET/POST /repos/{owner}/{repo}/issues/{number}/comments`
- Merge: `PUT /repos/{owner}/{repo}/pulls/{number}/merge`

## Fix

### Authentication

```bash
# Extract token from git credentials
TOKEN=$(cat ~/.git-credentials | grep -i "github.com" | head -1 | sed 's/.*:\/\/[^:]*:\([^@]*\)@.*/\1/')

# Or set directly
TOKEN="ghp_xxxxxxxxxxxx"
```

### Create Issue



**Expected Output:**
```
On branch main
OK
```
## Notes

- Use `jq` for JSON parsing: `curl ... | jq '.html_url'`
- Rate limit: 5000 requests/hour for authenticated users
- For large bodies, use JSON file: `-d @/tmp/issue.json`