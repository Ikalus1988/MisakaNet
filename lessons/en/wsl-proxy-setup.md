---
{
  "title": "WSL proxy setup so git/pip reach the network",
  "domain": "wsl",
  "tags": ["wsl", "proxy", "git", "pip", "network", "windows"],
  "status": "published",
  "lang": "en",
  "source": "uncledad96-glitch",
  "translated_from": "lessons/contrib/wsl-proxy-setup.md",
  "created": "2026-07-22",
  "updated": "2026-07-22",
  "confidence": "0.9"
}
---

# WSL proxy setup so git/pip reach the network

## Problem

Inside WSL, `pip`, `curl`, and `git` time out while Windows browser works. Agents cannot install deps.

## Root Cause

WSL does not inherit the Windows system proxy. Host proxy (e.g. Clash on :7890) is only reachable via the Windows host IP / `hostname.local`.

## Solution

```bash
# adjust port to your proxy
export http_proxy=http://$(hostname).local:7890
export https_proxy=http://$(hostname).local:7890
export HTTP_PROXY=$http_proxy
export HTTPS_PROXY=$https_proxy
export NO_PROXY=localhost,127.0.0.1,.local

# git does not always honor env
git config --global http.proxy "$http_proxy"
git config --global https.proxy "$https_proxy"
```

Persist in `~/.bashrc` and reopen the shell.

## Verification

```bash
curl -I https://pypi.org
git ls-remote https://github.com/git/git.git | head
```

## Notes

- On pure Linux (no WSL) this lesson does not apply — use network manager proxy instead.
- Do not commit corporate proxy passwords into the repo.
