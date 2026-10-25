---
title: "DSH web_fetch reports 'TypeError: fetch failed', which names the wrapper and hides the real cause"
domain: "dsh"
tags:
  - "dsh"
  - "web-fetch"
  - "network"
  - "undici"
  - "proxy"
  - "dns"
  - "diagnostics"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "DSH 里 web_fetch 报 fetch failed，只说明连接没建起来，真正的错因藏在 error.cause 里，要单独取出来看。"
trigger: "Error: web fetch failed: TypeError: fetch failed / DSH web_fetch 反复失败 / fetch failed 没有具体错误码"
verify: "复现后从 error.cause（code/errno）取到具体错因（如 ENOTFOUND / ECONNREFUSED / ETIMEDOUT / UND_ERR_*），且修复后同一 URL 的 web_fetch 返回正文而不是 fetch failed。"
source: "intake-2964"
provenance:
  issue: "#2964"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# DSH web_fetch reports 'TypeError: fetch failed', which names the wrapper and hides the real cause

## Problem

In a DSH (DeepSeek Harness) session the `web_fetch` tool failed **three times in one session**.
First failure `2026-10-07T03:59:42.194Z`, last `2026-10-07T04:11:25.486Z` — about twelve minutes
apart, so this was not a single blip on one call.

The calling argument, as recorded in the redacted session log:

```text
{"url": "https://github.com/awesome-dsh-plugin/awesome-dsh-plugin/blob/main/README.zh.md?plain=1"}
```

The verbatim error:

```text
Error: web fetch failed: TypeError: fetch failed
```

That is the whole of the error surface the reporter saw. There is no status code, no host, no
errno — which is exactly why the failure is hard to act on.

## Root Cause

The reporter supplied no root cause, and this repository has not reproduced the failure —
报料者未给出，需复现确认. What can be said without inventing anything is why the message is
uninformative, and therefore what has to be measured before a cause can be named.

`TypeError: fetch failed` is the **wrapper** error that Node's `fetch` (undici) throws when the
request never produced a response. The discriminating detail is deliberately one level down, on
`error.cause` (and on `error.cause.code` / `error.cause.errno`). The wrapper alone cannot
distinguish, among others:

- DNS resolution failure (`ENOTFOUND`, `EAI_AGAIN`);
- connection refused or a proxy that is not listening (`ECONNREFUSED`);
- connect/TLS timeout (`ETIMEDOUT`, `UND_ERR_CONNECT_TIMEOUT`);
- TLS verification failure (`CERT_*` / `UNABLE_TO_VERIFY_LEAF_SIGNATURE`);
- a proxy that requires configuration the process does not have.

Each of those has a different fix, and all five render as the same one-line message. Three
consecutive failures over twelve minutes also rules out the "one transient blip, retry will
work" reading.

Whether the specific URL above is a contributing factor is **unconfirmed**: a `github.com` blob
URL with `?plain=1` serves an HTML page, not raw Markdown. If the failure were an HTTP-status or
content-type problem it would surface as a response, not as `fetch failed`, so this is a
hypothesis to test rather than a conclusion — 报料者未给出，需复现确认.

## Solution

No fix was confirmed by the reporter (the intake's "Fix" section is empty). The reproducible
procedure below is the minimum needed to convert the wrapper message into a nameable cause; it
is a diagnosis plan, not a verified repair.

### Step 1 — get the cause, not the wrapper

Wrap the same call and print the underlying error object:

```js
try {
  const r = await fetch(url, { signal: AbortSignal.timeout(20_000) });
  console.log('status', r.status, 'type', r.headers.get('content-type'));
} catch (err) {
  console.log('name   ', err.name);              // TypeError
  console.log('message', err.message);            // fetch failed
  console.log('cause  ', err.cause?.code, err.cause?.errno, err.cause?.message);
}
```

The `cause` line is the one that carries the decision: `ENOTFOUND`/`EAI_AGAIN` is DNS,
`ECONNREFUSED` is the connection endpoint (frequently a proxy that is not up), `ETIMEDOUT` /
`UND_ERR_CONNECT_TIMEOUT` is reachability, `CERT_*` is TLS.

### Step 2 — split the process from the network

```bash
# does the same URL work outside the DSH process at all?
curl -sS -o /dev/null -w '%{http_code} %{time_total}s\n' '<the same URL>'

# what does this environment claim about proxies?
env | grep -iE '^(http_proxy|https_proxy|all_proxy|no_proxy)=' || echo 'no proxy vars set'
```

If `curl` succeeds while `web_fetch` fails, the fault is in the process environment (proxy
variables, CA bundle, DNS resolver order) rather than at the endpoint.

### Step 3 — retry deliberately, and record the verdict

Re-run the same tool call once after Step 1–2. Three failures spaced twelve minutes apart is
enough evidence that a blind retry is not the fix; the retry is only there to confirm the
diagnosis changed the outcome.

## Verification

The reporter did not supply a verification step — 报料者未给出，需复现确认. The criterion this
lesson can be checked against is:

- **before**: the tool result is `Error: web fetch failed: TypeError: fetch failed` with no
  code anywhere in the message;
- **diagnosed**: Step 1 prints a non-empty `err.cause.code` (for example `ENOTFOUND`,
  `ECONNREFUSED`, `ETIMEDOUT`, or an `UND_ERR_*` constant);
- **fixed**: the same `web_fetch` call returns page content, or returns a specific HTTP status,
  instead of `fetch failed`.

If Step 1 still prints `cause: undefined`, the failure never reached the network layer and the
next thing to check is the tool's own argument/serialization path — not the network.
