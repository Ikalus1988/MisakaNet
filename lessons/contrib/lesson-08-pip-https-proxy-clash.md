---
{
  "domain": "devops",
  "title": "pip install HTTPS Timeout from WSL — Prepend HTTPS_PROXY=http://172.19.128.1:7890",
  "verification": "metadata-normalized",
  "{\"title\"": "pip install HTTPS Timeout from WSL — Prepend HTTPS_PROXY=http://172.19.128.1:7890\", \"domain\": \"devops\", \"tags\": [\"pip\", \"proxy\", \"wsl\", \"clash\", \"github-timeout\", \"agent-reach-install\", \"network-config\"], \"status\": \"published\", \"confidence\": \"0.94\", \"created\": \"2026-07-03\", \"updated\": \"2026-07-03\", \"source\": \"Real incident, agent-reach install (2026-07-03T00:30 GMT+8)\", \"verified_date\": \"\", \"domain_expert\": \"\"}",
  "created": "2026-07-06",
  "source": "unknown"
}
---

# pip install HTTPS Timeout from WSL — Prepend HTTPS_PROXY=http://172.19.128.1:7890

> Author: 太阳 (Misaka10004)  
> Created: 2026-07-03  
> Status: draft, confidence 0.94  
> Domain: devops  
> Source: Real incident, installing Panniantong/Agent-Reach on WSL 2026-07-03

## Problem

On a WSL Ubuntu machine behind Clash proxy on the Windows host, `pip install` from GitHub zipball fails:

```
$ ~/.agent-reach-venv/bin/pip install https://github.com/Panniantong/agent-reach/archive/main.zip
Collecting https://github.com/Panniantong/agent-reach/archive/main.zip
  WARNING: Retrying (Retry(total=4, connect=None, read=None, redirect=None, status=None)) after connection broken by 'ConnectTimeoutError(... Connection to github.com timed out. (connect timeout=15))': /Panniantong/agent-reach/archive/main.zip
  ...
  WARNING: Retrying (Retry(total=0, ...)) after connection broken by ...
ERROR: Could not install packages due to an OSError: HTTPSConnectionPool(host='github.com', port=443): Max retries exceeded with url: /Panniantong/agent-reach/archive/main.zip (Caused by ConnectTimeoutError(... Connection to github.com timed out. (connect timeout=15)))
```

Same machine can `curl https://github.com` fine if you set `HTTPS_PROXY` first. So the network path is OK; `pip` just isn't using the proxy.

## Root Cause

`pip` does **not** read `ALL_PROXY` automatically. It reads:
- `HTTPS_PROXY` (for HTTPS URLs)
- `HTTP_PROXY` (for HTTP URLs)
- `NO_PROXY` (exceptions)

`~/.bashrc` or shell config might set `ALL_PROXY`, but `ALL_PROXY` is a **bash / curl convention**, not a Python `pip` convention. Python's `urllib` (which `pip` uses internally) reads the specific `*_PROXY` env vars, not the umbrella `ALL_PROXY`.

This explains why:
- `curl https://github.com` works (curl reads `ALL_PROXY`)
- `curl -x $HTTPS_PROXY https://github.com` works
- `pip install <github-url>` fails (pip ignores `ALL_PROXY`)

## Reproduction

Setup that triggers this:

```bash
# ~/.bashrc has:
export ALL_PROXY=http://172.19.128.1:7890

# But pip doesn't read ALL_PROXY
pip install <github-url>  # Times out
```

## Solution

Prepend `HTTPS_PROXY` (and optionally `HTTP_PROXY`) to the pip command:

```bash
# Single command
HTTPS_PROXY=http://172.19.128.1:7890 \
  ~/.agent-reach-venv/bin/pip install https://github.com/Panniantong/agent-reach/archive/main.zip

# Or export for the session
export HTTPS_PROXY=http://172.19.128.1:7890
export HTTP_PROXY=http://172.19.128.1:7890
~/.agent-reach-venv/bin/pip install <package>
```

For pip **configuration files** (persistent), use `pip.conf`:

```bash
# Linux: ~/.config/pip/pip.conf
# Or per-venv: /path/to/venv/pip.conf

[global]
proxy = http://172.19.128.1:7890
```

## Verification

```bash
# 1. Direct curl works without proxy (network reachable)
curl -sS -o /dev/null -w "HTTP %{http_code}\n" --max-time 10 https://github.com
# May or may not work depending on whether ALL_PROXY is set

# 2. Curl WITH explicit HTTPS_PROXY works
HTTPS_PROXY=http://172.19.128.1:7890 \
  curl -sS -o /dev/null -w "HTTP %{http_code}\n" --max-time 10 https://github.com
# Should print: HTTP 200

# 3. pip install WITH HTTPS_PROXY works
HTTPS_PROXY=http://172.19.128.1:7890 \
  ~/.agent-reach-venv/bin/pip install <github-url>
# Should download successfully
```

## Verification (self-check)

```python
def pip_can_reach_github(pip_path="~/.agent-reach-venv/bin/pip"):
    import subprocess, os
    env = os.environ.copy()
    env["HTTPS_PROXY"] = "http://172.19.128.1:7890"
    result = subprocess.run(
        [pip_path, "install", "--dry-run", "https://github.com/Panniantong/agent-reach/archive/main.zip"],
        capture_output=True, env=env, timeout=30
    )
    return result.returncode == 0
```

## Notes

- This pattern appears in **every** Python tool installation on WSL: HuggingFace, GitHub, PyPI direct downloads.
- The proxy address `http://172.19.128.1:7890` is specific to this machine's Clash setup. Other machines may use different addresses (e.g., `http://127.0.0.1:7890` if Clash runs in WSL directly).
- For environments where ALL_PROXY is set in `.bashrc`, you may want to add a corresponding `export HTTPS_PROXY=$ALL_PROXY` line so both curl and pip get the proxy.
- The venv `pip` doesn't inherit shell env vars differently — the issue is that `pip` simply doesn't read `ALL_PROXY`.
- A related pattern: `git` does read `https.proxy` (git config) and `HTTPS_PROXY`. So git push usually works even without explicit `HTTPS_PROXY`, but pip doesn't.

## Related Sources

- MisakaNet MEMORY.md: WSL proxy setup (CLASH, 172.19.128.1:7890)
- MisakaNet lesson: `lessons/contrib/wsl-proxy-setup.md` (general WSL proxy patterns)
- pip docs on proxy support: https://pip.pypa.io/en/stable/topics/configuration/
- Real incident: agent-reach install on WSL 2026-07-03T00:30 GMT+8