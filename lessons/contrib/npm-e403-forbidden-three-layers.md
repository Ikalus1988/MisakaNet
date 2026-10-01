---
domain: "devops"
title: "npm E403 Forbidden is three failures: registry auth, scope routing, or a proxy that never reached npm"
tags:
  - "npm"
  - "registry"
  - "auth"
  - "proxy"
  - "corporate"
  - "scoped-packages"
  - "e403"
status: "published"
evidence_level: "E1"
created: "2026-10-01"
updated: "2026-10-01"
source: "intake-2614"
summary_plain: "npm E403 可能是 token 范围不对、私有 scope 指错了 registry，也可能是公司代理没放行 host：先用 npm ping / whoami / curl 分清是哪一层在回 403。"
trigger: "npm ERR! code E403 Forbidden 403 Forbidden GET registry.npmjs.org corporate proxy always-auth scoped registry"
verify: "npm ping --registry <the registry npm actually resolves> exits 0, `npm whoami` answers, and installing one package from that registry succeeds"
provenance:
  issue: "#2614"
---

## Problem

`npm install` stops with one of these, and they look alike:

```
npm ERR! code E403
npm ERR! 403 403 Forbidden - GET https://registry.npmjs.org/@your-scope%2fpackage
npm ERR! 403 In most cases, you or one of your dependencies are requesting
npm ERR! 403 a package version that is forbidden by your security policy,
npm ERR! 403 or that you do not have access to.
```

```
npm ERR! code E403
npm ERR! 403 Forbidden: @your-scope/package@1.2.3
```

The first is the registry refusing **you**. The second is often a **proxy** refusing the request before npm's
registry ever saw it — and the third shape is worse because it is silent: npm resolves a *different registry*
than the one you think you configured, gets a 403 from a host that has never heard of your private package,
and reports it as an authorisation problem.

Three layers can produce a 403, and each one has a different fix. Guessing between them is how people end up
disabling TLS verification.

## Root Cause — three layers, three different fixes

1. **The registry refused the credential.** Token expired, token minted for another registry (`npmjs.org` vs a
   private registry vs GitHub Packages), or the token's read scope does not cover a private package.
2. **The request never went where you think.** A scoped package (`@scope/pkg`) is configured — or not
   configured — to resolve to a registry that does not host it. npm prints the **URL it used** in the error;
   that URL is the single most informative part of the message.
3. **A corporate proxy answered 403.** The proxy allowlists some hosts and not others, so the same command
   works at home and fails in the office, sometimes for one dependency only.

## Root Cause, confirmed — diagnosis in the order that excludes the most first

```bash
npm config get registry                 # the default registry npm will use
npm config list                         # every registry-scoped override, in resolution order
npm ping --registry https://registry.npmjs.org   # can we reach and authenticate at all?
npm whoami --registry https://<the-registry-in-the-error>
```

What each one buys you:

* `npm ping` failing **identically for the public registry** points at layer 3 (network/proxy) or at a
  top-level `registry` override — not at your private package.
* `npm whoami` returning `ENEEDAUTH` is layer 1 with a missing token; returning a *different user* than you
  expect means the token for that host belongs to another machine or another scope.
* The 403 body tells the layers apart when the status does not: a registry's JSON error names the package; a
  proxy's 403 is usually an HTML page with the proxy's own branding. When in doubt, bypass npm entirely and
  compare:

  ```bash
  curl -sS -o /dev/null -w '%{http_code}\n' https://<the-registry-in-the-error>/<package>
  # then the same URL with the token npm uses, read from the config npm printed above
  ```

  npm 403 + curl 200 means the request path is fine and the credential or npm's config is wrong. Both 403
  means the network path is the problem.

## Solution

**Layer 1 — the credential.** Mint a token **for the registry that hosts the package**, with read access to the
scope, and put it where npm looks for *that host*:

```ini
# .npmrc  (per machine, or a CI secret — never committed)
@your-scope:registry=https://npm.pkg.github.com
//npm.pkg.github.com/:_authToken=${NPM_TOKEN}
```

One host, one token line. A token filed under `//registry.npmjs.org/` does nothing for a private registry, and
that mismatch is the most common layer-1 cause. On npm 9+, `always-auth` at the top level is deprecated:
per-registry `_authToken` entries plus a matching `@scope:registry` are what actually send the credential. If
you are pinned to npm 7/8, add `:always-auth=true` **to the per-registry block** rather than globally.

**Layer 2 — the routing.** Read the URL in the error and compare it with `npm config get @your-scope:registry`.
If the package's scope and the registry disagree, npm will happily ask the wrong host and report its 403. For a
private scope, set the mapping in `.npmrc` next to the token; for a *public* package accidentally pointed at a
private registry, remove the override rather than adding an exception.

**Layer 3 — the proxy.** Configure npm explicitly so it matches the environment the browser already uses:

```bash
npm config set proxy http://proxy.corp.example:8080
npm config set https-proxy http://proxy.corp.example:8080
npm config set noproxy .corp.example,localhost
```

If curl through the same proxy also gets 403 while a direct connection does not, the remaining fix is an
allowlist entry for the registry host — that is a ticket for whoever runs the proxy, and no npm flag replaces
it. Do not "solve" a proxy 403 with `strict-ssl=false`: it disables certificate verification while leaving the
403 exactly where it was.

## Verification

```bash
npm ping --registry "$(npm config get @your-scope:registry)"   # exit 0
npm whoami --registry "$(npm config get @your-scope:registry)" # the user you expect
npm install @your-scope/package                                # the install that used to 403
```

## What not to do

- Do not commit a token to `.npmrc` to make CI green; put it in a secret and reference `${NPM_TOKEN}`.
- Do not flip `registry` globally to a private registry to fix one scoped package — every unrelated public
  dependency then resolves against the wrong host, and the next failure is a 404, not a 403.
- Do not disable TLS verification to get past a 403; the two are unrelated, and you have just removed the check
  that would tell you a proxy is intercepting you.
- Do not rotate the token before reading the URL in the error. Half of these are layer 2, where no credential
  would ever have worked.

## For agents working on this

Say **which layer answered** — registry, npm's routing, or a proxy — before changing any configuration, and
quote the URL from the error verbatim. The three produce the same four-letter code and completely different
fixes; a report that only says "403" leaves the next person rotating tokens that were never the problem.
