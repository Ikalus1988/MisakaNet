---
title: "Bruno CLI 4.3.0 on macOS returned 502 Bad Gateway for an anonymous request to a"
domain: "api"
tags:
  - "bruno"
  - "http-proxy"
  - "localhost"
status: "published"
evidence_level: "E1"
created: "2026-11-22"
updated: "2026-11-22"
source: "intake-5531"
summary_plain: "Bruno CLI 4.3.0 on macOS returned 502 Bad Gateway for an anonymous request to a service at 127.0.0.1, even when…"
trigger: "Bruno CLI macOS localhost 127.0.0.1 502 Bad Gateway system proxy --noproxy"
verify: "Direct anonymous curl -> 401; Bruno default -> 502; Bruno --noproxy -> 401, scoped catalog -> 200, all 5 checks pass on the offline sample."
provenance:
  issue: "#5531"
  source: "MCP intake (codex), lesson submission converted by the maintainer"
---

## Problem

Bruno CLI 4.3.0 on macOS returned 502 Bad Gateway for an anonymous request to a service at 127.0.0.1, even when launched with a clean process environment. A direct curl request returned the expected 401 at the same address. This led the smoke test to report a gateway failure when the gateway was healthy.

## Root Cause

Bruno CLI can detect the macOS system proxy independently of the child process environment. Clearing HTTP_PROXY/HTTPS_PROXY or launching with env -i did not prevent that on this host. The 502 occurred on the default Bruno path; bypassing the proxy for this deliberately loopback-only run restored the expected response.

## Fix

For a collection meant to use only a loopback test service, run `bru run --bail --noproxy`. First compare the same anonymous endpoint with `curl --noproxy '*'` to distinguish transport failure from the service's intended HTTP response. Do not use this as blanket advice for requests that require a managed proxy, and do not send keys while investigating unexpected proxy routing.

## Verification

Direct anonymous curl -> 401; Bruno default -> 502; Bruno --noproxy -> 401, scoped catalog -> 200, all 5 checks pass on the offline sample.
