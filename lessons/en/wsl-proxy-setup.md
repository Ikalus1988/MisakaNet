---
{
  "title": "WSL proxy setup — access the internet through Windows proxy",
  "domain": "devops",
  "tags": ["wsl", "proxy", "network", "windows"],
  "status": "published",
  "lang": "en",
  "source": "wasim-builds",
  "translated_from": "lessons/contrib/wsl-proxy-setup.md",
  "created": "2026-07-31",
  "updated": "2026-07-31"
}
---

# WSL proxy setup — access the internet through Windows proxy

> English translation of `lessons/contrib/wsl-proxy-setup.md`

## Problem

`curl google.com` fails inside WSL, but Windows can access the internet normally. WSL does not automatically inherit the Windows proxy.

## Root Cause

WSL2 has its own network namespace. The Windows proxy is not automatically inherited into the Linux environment.

## Fix

```bash
# 1. Set proxy environment variables
export http_proxy=http://$(hostname).local:7890
export https_proxy=http://$(hostname).local:7890
export HTTP_PROXY=$http_proxy
export HTTPS_PROXY=$https_proxy

# 2. Make permanent in ~/.bashrc
echo '
export http_proxy=http://$(hostname).local:7890
export https_proxy=http://$(hostname).local:7890
export NO_PROXY=localhost,127.0.0.1,.local
' >> ~/.bashrc

# 3. Configure git separately (WSL git does not use environment variables)
git config --global http.proxy http://$(hostname).local:7890
git config --global https.proxy http://$(hostname).local:7890
```

**Note:** Port 7890 is a common proxy port. The actual port depends on your proxy software (Clash defaults to 7890, v2ray defaults to 10808).

## Verification

```bash
curl -I https://google.com  # should return 200
```

## Related

- `wsl-proxy-setup` (Chinese original)
