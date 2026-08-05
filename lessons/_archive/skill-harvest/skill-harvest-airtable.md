---
domain: "archive"
title: "Airtable"
verification: "metadata-normalized"
source: "skill-pipeline"
status: "draft"
created: "2026-05-09"
---

## 背景

（此 lesson 从 skill `airtable` 自动提取，待补全）

## 根因

（待补充）

## 修复


# Airtable — Bases, Tables & Records

Work with Airtable's REST API directly via `curl` using the `terminal` tool. No MCP server, no OAuth flow, no Python SDK — just `curl` and a personal access token.

## Prerequisites

1. Create a **Personal Access Token (PAT)** at https://airtable.com/create/tokens (tokens start with `pat...`).
2. Grant these scopes (minimum):
   - `data.records:read` — read rows
   - `data.records:write` — create / update / delete rows
   - `schema.bases:read` — list bases and tables
3. **Important:** in the same token UI, add each base you want to access to the token's **Access** list. PATs are scoped per-base — a valid token on the wrong base returns `403`.
4. Store the token in `~/.hermes/.env` (or via `hermes setup`):
   ```
   AIRTABLE_API_KEY=pat_your_token_here
   ```

> Note: legacy `key...` API keys were deprecated Feb 2024. Only PATs and OAuth tokens work now.

## API Basics

- **Endpoint:** `https://api.airtable.com/v0`
- **Auth header:** `Authorization: Bearer $AIRTABLE_API_KEY`
- **All requests** use JSON (`Content-Type: application/json` for any POST/PATCH/PUT body).
- **Object IDs:** bases `app...`, tables `tbl...`, records `rec...`, fields `fld...`. IDs never change; names can. Prefer IDs in automations.
- **Rate limit:** 5 requests/sec/base. `429` → back off. Burst on a single base will be throttled.

Base curl pattern:
```bash
curl -s "https://api.airtable.com/v0/$BASE_ID/$TABLE?maxRecords=5" \
  -H "Authorization: Bearer $AIRTABLE_API_KEY" | python3 -m json.tool
```

`-s` suppresses curl's progress bar — keep it set for every call so the tool output stays clean for Hermes. Pipe through `python3 -m json.tool` (always present) or `jq` (if installed) for readable JSON.

## Field Types (request body shapes)

| Field type | Write shape |
|---|---|
| Single line text | `"Name": "hello"` |
| Long text | `"Notes": "multi\nline"` |
| Number | `"Score": 42` |
| Checkbox | `"Done": true` |
| Single select | `"Status": "Todo"` (name must already exist unless `typecast: true`) |
| Multi-select | `"Tags": ["urgent", "bug"]` |
| Date | `"Due": "2026-04-01"` |
| DateTime (UTC) | `"At": "2026-04-01T14:30:00.000Z"` |
| URL / Email / Phone | `"Link": "https://…"` |
| Attachment | `"Files": [{"url": "https://…"}]` (Airtable fetches + rehosts) |
| Linked record | `"Owner": ["recXXXXXXXXXXXXXX"]` (array of record IDs) |
| User | `"AssignedTo": {"id": "usrXXXXXXXXXXXXXX"}` |

Pass `"typecast": true` at the top level of a create/update body to let Airtable auto-coerce values (e.g. create a new select option on the fly, convert `"42"` → `42`).

## Common Queries

### List bases the token can see
```bash
curl -s "https://api.airtable.com/v0/meta/bases" \
  -H "Authorization: Bearer $AIRTABLE_API_KEY" | python3 -m json.tool
```

### List tables + schema for a base
```bash
curl -s "https://api.airtable.com/v0/meta/bases/$BASE_ID/tables" \
  -H "Authorization: Bearer $AIRTABLE_API_KEY" | python3 -m json.tool
```
Use this BEFORE mutati

## 验证

（待补充）
