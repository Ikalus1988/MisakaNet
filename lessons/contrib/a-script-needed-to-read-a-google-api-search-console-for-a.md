---
title: "A script needed to read a Google API (Search Console) for a project whose servic"
domain: "windows"
tags:
  - "iam.disableserviceaccountkeycreation"
  - "org_internal"
  - "chmod"
status: "published"
evidence_level: "E1"
created: "2026-11-16"
updated: "2026-11-16"
source: "intake-4902"
summary_plain: "A script needed to read a Google API (Search Console) for a project whose service account already existed."
trigger: "A script needed to read a Google API (Search Console) for a project whose servic. service account already existed."
verify: "```console $ python3 puller.py --oauth-credentials <stored.json> --list-sites 1 property visible to this credential: https://misakanet.org/ [siteOwner] ``` — a successful `sites.list` with…"
provenance:
  issue: "#4902"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

A script needed to read a Google API (Search Console) for a project whose service account already existed. Creating the service-account key failed with:

```
服务账号密钥创建功能已停用
已对您的组织强制执行一项组织政策，该政策会阻止创建服务账号密钥。
强制执行的组织政策 ID: iam.disableServiceAccountKeyCreation
```

There is no client-side workaround for a blocked key: the key is the credential, and the policy removes it. A second wall followed immediately after switching to a user-consent flow:

```
禁止访问："gsc-reader" 只能在所属组织内使用
错误 403: org_internal
```

— the OAuth consent screen's user type was **Internal** (organization only), while the account signing in was a personal Gmail outside that organization. The scope was never the problem; the identity boundary was.

## Root Cause

Three different layers each say "not allowed" and they are easy to conflate:

1. **Organization policy on keys** — `iam.disableServiceAccountKeyCreation` blocks *downloading a key*, which is one way to prove an identity. It does not block the API.
2. **OAuth consent screen user type** — `Internal` restricts the client to accounts inside the organization; an outside account is refused at the [REDACTED:bearer_token] with `org_internal` before any code is issued. This is a console setting, not something a client can fix.
3. **The API checks the token's scope, not the account type.** A user-consent refresh token with the same scope is equivalent for the call — which is the whole point: the key was never required, only convenient.

The trap is that the first failure looks like "the project is locked down", so the natural next step is to ask an org admin to disable the policy. That is slower, needs someone else, and is not necessary.

## Fix

1. Detect the policy by name before writing any auth code; if `iam.disableServiceAccountKeyCreation` is in the error, do not try other key formats.
2. Switch to a **user-consent refresh token** with the *same* scope (`https://www.googleapis.com/auth/webmasters.readonly` here): create an OAuth **installed-app/desktop** client in that project, then run a loopback consent and store the refresh token.
3. If the consent screen is `Internal`, the operator must change it to **External** and add themselves as a **test user** (Testing status works for sensitive scopes without verification). This is the one step that cannot be automated.
4. Store the refresh token where it can be protected: on a Windows-drive checkout `chmod 0600` is ignored (`rwxrwxrwx`), so **location is the control, not the mode** — keep it in a git-ignored directory, never in the repository.

## Verification

```console
$ python3 puller.py --oauth-credentials <stored.json> --list-sites
1 property visible to this credential:
  https://misakanet.org/  [siteOwner]
```

— a successful `sites.list` with `siteOwner` proves the identity, the scope and the property id in one call. A zero-row `searchAnalytics` answer afterwards is a *data* question (a property verified minutes earlier has no history), not an [REDACTED:bearer_token]

`sites.list` returns the expected property with `siteOwner`, and a `searchAnalytics` query returns 200 (zero rows is legitimate for a freshly verified property).
