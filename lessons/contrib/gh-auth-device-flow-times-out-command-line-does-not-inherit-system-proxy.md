---
domain: "network"
title: "`gh auth login` times out while the same browser opens github.com — the command line does not inherit the system proxy"
tags: [gh-cli, device-flow, proxy, macos, scutil, timeout, oauth, network]
status: "published"
evidence_level: "E2"
summary_plain: "A shell does not inherit the macOS system proxy, so gh auth login times out while the browser works fine."
trigger: "gh auth login timeout; failed to authenticate via web browser; dial tcp i/o timeout on github.com/login/device while the browser opens it fine"
verify: "curl -s -o /dev/null -w '%{http_code}' https://github.com/login/device returns 302 with https_proxy set and 000 without it; gh auth status then shows the account."
provenance:
  issue: "#3339"
  source: "MCP intake (dsh), contributor-reported"
---

# `gh auth login` times out while the same browser opens github.com — the command line does not inherit the system proxy

## Problem

On macOS, `gh auth login` never completes. The device-flow request fails before any code is shown:

```
failed to authenticate via web browser: Post "https://github.com/login/device/code":
dial tcp 20.205.243.166:443: i/o timeout
```

Every variation failed the same way — `--web`, explicit `--hostname github.com`, `--git-protocol
https`, reinstalling `gh` over Homebrew. The same machine's browser opens `github.com` and the
device-authorisation page instantly, so the natural reading — "GitHub is down" or "the CLI is
broken" — is wrong in both directions, and it is wrong in a way that sends people to reinstall
things for an hour.

## Root Cause

**A GUI application inherits the system proxy; a shell does not.** On macOS the Clash/Surge-style
proxy is configured in System Settings, and the browser picks it up through the system network
stack. A process started from a terminal gets whatever `http_proxy` / `https_proxy` are exported in
that shell — usually nothing — so the browser goes through the proxy and the CLI goes direct.

The network is not down, and that is measurable without guessing:

```bash
curl -s -o /dev/null -w '%{http_code}\n' https://api.github.com          # 200  (direct works)
curl -s -o /dev/null -w '%{http_code}\n' https://github.com/login/device  # 000  (timeout)
https_proxy=http://127.0.0.1:7890 \
  curl -s -o /dev/null -w '%{http_code}\n' https://github.com/login/device  # 302
```

`api.github.com` answering 200 while `github.com` times out is the discriminator: the egress path
works, only the *main site* domain is blocked on the direct route, and adding the proxy fixes it.
`scutil --proxy` shows the system proxy is configured while `env | grep -i proxy` in the same shell
is empty — that pair is the whole diagnosis.

## Solution

Export the proxy for the command, or once in the shell profile:

```bash
https_proxy=http://127.0.0.1:7890 http_proxy=http://127.0.0.1:7890 \
  gh auth login --hostname github.com --git-protocol https --web
```

Two details that decide whether this works:

- **Take the port from what is actually listening.** `scutil --proxy` prints the configured
  host/port; common defaults are Clash `7890`, Surge `1080`/`6152`. A configured-but-dead port fails
  the same way as no proxy at all.
- **Let the terminal finish.** The device flow prints `✓ Logged in as <user>` and only then writes
  `~/.config/gh/hosts.yml`. Closing the window when the browser says "device connected" aborts the
  polling, and the credential never lands — which looks exactly like "authorisation failed".

`https_proxy` alone is usually enough; exporting `http_proxy` too covers the redirects that fall
back to plain HTTP.

## Verification

```bash
curl -s -o /dev/null -w '%{http_code}\n' https://github.com/login/device   # 302, not 000
gh auth status                                                             # shows the account
gh auth token | head -c 8                                                  # non-empty
test -f ~/.config/gh/hosts.yml && echo credential persisted
```

Counter-evidence that it is still broken: the browser says "device connected" while `gh auth
status` reports no account and `~/.config/gh/` was never created. That is the polling step not
having run to completion — rerun and wait for the CLI's own `✓` line rather than closing the
window.

## Notes

- The same shape appears on Linux behind a corporate proxy, and with any CLI that speaks to
  `github.com` directly (`gh`, `npm publish`, `pip`): the browser proves the *human* path works,
  never the shell's.
- Diagnose by comparing two endpoints on the same host, not by restarting the proxy. A timeout on
  one domain with 200 on another is a routing distinction; a timeout on all of them is the network.
- Related, same shape on a different host: `lessons/contrib/lesson-08-pip-https-proxy-clash.md`
  (pip inside WSL, proxy reachable by host IP rather than `127.0.0.1`).
