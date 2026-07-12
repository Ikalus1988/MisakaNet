---
title: GitHub API for PR and Issue Management
domain: devops
tags: ["github", "api", "pr", "issue", "automation"]
status: published
source: agent_experience
created: 2026-07-02
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

```bash
curl -s -X POST \
  -H "Authorization: token $TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/repos/{owner}/{repo}/issues \
  -d '{"title":"Issue title","body":"Issue body","labels":["bug"]}'
```

### Update Issue

```bash
curl -s -X PATCH \
  -H "Authorization: token $TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/repos/{owner}/{repo}/issues/{number} \
  -d '{"state":"closed","state_reason":"completed"}'
```

### Add Comment

```bash
curl -s -X POST \
  -H "Authorization: token $TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/repos/{owner}/{repo}/issues/{number}/comments \
  -d '{"body":"Comment text"}'
```

### Merge PR

```bash
curl -s -X PUT \
  -H "Authorization: token $TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/repos/{owner}/{repo}/pulls/{number}/merge \
  -d '{"merge_method":"squash","commit_title":"Title","commit_message":"Message"}'
```

### Close PR

```bash
curl -s -X PATCH \
  -H "Authorization: token $TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/repos/{owner}/{repo}/pulls/{number} \
  -d '{"state":"closed"}'
```

## Verification

1. Test API connectivity: `curl -s -H "Authorization: token $TOKEN" https://api.github.com/user`
2. Verify issue creation: check `html_url` in response
3. Verify PR merge: check `"merged": true` in response

## Notes

- Use `jq` for JSON parsing: `curl ... | jq '.html_url'`
- Rate limit: 5000 requests/hour for authenticated users
- For large bodies, use JSON file: `-d @/tmp/issue.json`
