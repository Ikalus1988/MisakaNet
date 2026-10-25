---
title: "A Feishu bitable attachment field rejects a doc-image file token; upload needs parent_type=bitable_file"
domain: "feishu"
tags:
  - "feishu"
  - "bitable"
  - "attachment-field"
  - "drive-medias"
  - "parent-type"
  - "file-token"
  - "mcp"
  - "open-api"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "飞书多维表格附件字段必须用 parent_type=bitable_file 上传得到的 file_token，文档图片的 token 会被 1254303 拒绝。"
trigger: "feishu bitable attachment field 1254303 parent_type=bitable_file upload_all 附件字段写不进去"
verify: "以 parent_type=bitable_file 上传拿到的 file_token 写入附件字段后，记录回读能看到该文件名且 size 大于 0。"
source: "intake-3568"
provenance:
  issue: "#3568"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# A Feishu bitable attachment field rejects a doc-image file token; upload needs parent_type=bitable_file

## Problem

A Feishu (Lark) bitable **attachment field** could not be filled through the MCP document-image upload
path. Two facts were reported together:

- Writing a `file_token` obtained from the *document image* upload path into a bitable attachment field
  is rejected every time with code `1254303`.
- The MCP `bitable_ops` tool exposed no action that calls `drive/v1/medias/upload_all` with
  `parent_type=bitable_file`, so there was no supported way to produce a token the attachment field
  would accept.

The reporter's own text at that point is redacted in the intake
(`<image file://[REDACTED:url_credential]>@host`); **报料者未给出被脱敏的那段原文，需复现确认**.

## Root Cause

A Feishu Drive file token is scoped by *what it was uploaded for*, decided at upload time by
`parent_type` + `parent_node`. A media uploaded for a document is a document image: its token is valid
in a document's image block and invalid everywhere else. A bitable attachment field requires a media
uploaded with `parent_type=bitable_file` and `parent_node=<app_token>` — a different parent, hence a
different token, hence a different endpoint call.

So the failure is not a permission or a format problem, and it does not improve with retries. Only the
value shape is a *separate* precondition (see the tried variants below): a correct parent with a
malformed value is still rejected, and a well-formed value with the wrong parent is still rejected.

## Solution

Three paths, in the order the reporter evaluated them:

**1. Call the Open API directly** (the path the reporter recommended):

```text
POST https://open.feishu.cn/open-apis/drive/v1/medias/upload_all
form-data:
  parent_type=bitable_file
  parent_node=<app_token>            # the bitable's app_token, not the doc token
  file=<binary>
```

The call needs `app_id`/`app_secret` or a `tenant_access_token`. Take the returned `file_token` and
write it into the attachment field in this exact shape:

```json
[{"file_token": "<file_token>"}]
```

**2. Browser UI automation** — Playwright on the bitable page: click the attachment cell → "add local
file" → inject the file. The reporter rejected this as too slow at 400-table scale, but it is a valid
fallback when credentials for path 1 are unavailable.

**3. Add the missing capability to the MCP tool** — an `upload_attachment` action on `bitable_ops`
that calls `upload_all` with `parent_type=bitable_file`. This is the fix if the tool, rather than the
API, is the constraint.

Value shape is not the bug but it is a second trap: the reporter tried `[{"file_token":"x"}]`,
`["x"]` and `{"file_token":"x"}` — only `[{"file_token":"x"}]` is well-formed, and a wrong parent is
rejected even with that correct shape. Fix the parent first, then the shape.

## Verification

Reporter-reported results:

- doc-image token → bitable attachment field: rejected 100% of the time, `1254303`.
- doc-image token → document image block: success. The same token works in its own home, which is what
  makes it look like the field is broken rather than the token being wrong.
- token uploaded with `parent_type=bitable_file` → bitable: reported as success, but the reporter marks
  it **"待 API 路径验证"** (still to be verified on the API path). Treat the end-to-end write through
  path 1 as unconfirmed; only the rejection is measured.
- value shapes: `[{"file_token":"x"}]` / `["x"]` / `{"file_token":"x"}` all tried; only the first is
  correctly formed, and a wrong parent is still rejected.

Checkable criterion for the fix (报料者未给出，需复现确认): upload with `parent_type=bitable_file`,
write the token to the attachment field, then read the record back — the cell must list the file with
the expected name and a non-zero size. Pass = the file is attached; fail = `1254303` returns, or the
cell stays empty.

## Notes

The reporter did not state which MCP server/binding `bitable_ops` lives in, nor the `app_token`
handling for path 1 — **报料者未给出，需复现确认**.

Do not generalize "doc-image token is invalid" into "tokens are not portable at all": the same token
was accepted by the document path. The scope is the `(parent_type, parent_node)` pair.
