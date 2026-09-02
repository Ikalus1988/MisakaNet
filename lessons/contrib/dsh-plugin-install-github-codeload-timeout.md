---
title: DSH Plugin Install Failures — GitHub codeload Timeout vs npm Channel
domain: mcp
tags:
- dsh
- deepseek-harness
- plugin
- npm
- codeload
- github
- timeout
- install
status: published
created: '2026-09-01'
language: en
source: issue-1418
evidence_level: E0
---

## Problem

Installing a DSH (DeepSeek Harness) plugin from the [dsh-plugin.org](https://dsh-plugin.org) marketplace failed with `安装失败 — 请求超时：无法访问 GitHub 或网络不稳定` (request timeout: cannot reach GitHub or network unstable). The marketplace's registered install command was:

```bash
dsh plugin --profile web add github:ikalus1988/misakanet
```

## Root Cause

`dsh plugin add github:<owner>/<repo>` resolves through **codeload.github.com** to download the repository tarball. In some networks (especially in CN/GFW environments), `codeload.github.com` is blocked or times out while `api.github.com`, `raw.githubusercontent.com`, and `registry.npmjs.org` remain reachable. The install log shows:

```
[WARN] GET https://codeload.github.com/ikalus1988/misakanet/tar.gz/2932d914... error (23). Will retry in 10 seconds. 2 retries left.
[WARN] ... Will retry in 1 minute. 1 retries left.
```

Error code 23 = write error during curl download (network-level), not a plugin defect.

A second contributing factor: the marketplace metadata (`npmPackage` field) may be stale/empty, forcing the marketplace to fall back to the git channel even when an npm package exists.

## Fix

1. **Prefer the npm channel** when the plugin is published to npm (independent of GitHub codeload):

```bash
dsh plugin add misakanet   # from npm registry — fast, no GitHub dependency
```

2. Verify connectivity per endpoint before choosing a channel:

```bash
curl -sS -o /dev/null -w "%{http_code}\n" https://codeload.github.com/   # often blocked
curl -sS -o /dev/null -w "%{http_code}\n" https://registry.npmjs.org/    # usually OK
```

3. On Windows, note that `python3` may not exist — only `python`. Cross-platform plugin test helpers must detect this:

```js
const python = process.env.PYTHON || (process.platform === 'win32' ? 'python' : 'python3');
```

4. If you maintain a marketplace listing, keep `npmPackage` updated so the marketplace offers the npm channel.

## Verification

- `dsh plugin add misakanet` completes in ~1s (resolved, downloaded, added) when the package is on npm.
- `dsh plugin --profile <name> --dump-config` shows the `# == misakanet` layer for the installed bundle.
- The failing git-channel command reproduces the timeout deterministically in networks where codeload is blocked.
