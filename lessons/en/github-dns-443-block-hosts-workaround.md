---
{
  "title": "GitHub DNS pollution / port 443 blocked — hosts fallback IP solution",
  "domain": "devops",
  "tags": ["git", "github", "TLS", "network", "DNS", "hosts", "connectivity"],
  "status": "published",
  "lang": "en",
  "source": "wasim-builds",
  "translated_from": "lessons/contrib/github-dns-443-block-hosts-workaround.md",
  "created": "2026-07-31",
  "updated": "2026-07-31"
}
---

# GitHub DNS pollution / port 443 blocked — hosts fallback IP solution

> English translation of `lessons/contrib/github-dns-443-block-hosts-workaround.md`

## Problem

`git push` / `git fetch` continuously times out or reports TLS handshake errors:

```
fatal: unable to access 'https://github.com/...':
  GnuTLS recv error (-110): The TLS connection was non-properly terminated.
```

Retrying does not help; this is not a transient issue.

## Root Cause

DNS resolution works, but the resolved IP has **port 443 blocked by the ISP/firewall**. ICMP ping works but HTTPS handshake fails.

Typical symptoms:

| Check | Result |
|-------|--------|
| `ping github.com` | OK |
| `getent hosts github.com` | returns IP |
| `curl -I https://github.com` | timeout |
| `timeout 3 bash -c 'echo > /dev/tcp/<IP>/443'` | unreachable |

## Fix

### 1. Verify whether the currently resolved IP is reachable

```bash
GITHUB_IP=$(getent hosts github.com | awk '{print $1}')
timeout 3 bash -c "echo > /dev/tcp/$GITHUB_IP/443" && echo "reachable" || echo "unreachable"
```

### 2. Scan GitHub fallback IPs for port 443

GitHub official IP ranges (partial):

```
140.82.112.0/20    # primary services
185.199.108.0/22   # Pages/CDN
192.30.252.0/22    # legacy range
```

Scan script:

```bash
for ip in 140.82.112.3 140.82.112.4 140.82.113.3 140.82.114.3 \
          140.82.121.3 140.82.121.4 \
          185.199.108.153 185.199.109.153 185.199.110.153; do
  timeout 3 bash -c "echo > /dev/tcp/$ip/443" 2>/dev/null \
    && echo "OK $ip" || echo "FAIL $ip"
done
```

### 3. Write to hosts — only add github.com, NOT api.github.com

**Critical trap: `api.github.com` has a different real IP than `github.com`.**

| Domain | Real IP | Description |
|--------|---------|-------------|
| `github.com` | 140.82.112.x/20 | Web/Git services |
| `api.github.com` | **20.205.243.168** | REST API services (separate IP range) |

If `api.github.com` is pointed to `github.com`'s IP in hosts, API requests get a **301 redirect** (TLS SNI routing misidentifies API requests as web requests), causing `curl -X POST https://api.github.com/user/repos` and all API calls to fail.

**Correct format:**

```bash
# add only github.com
echo "<reachableIP> github.com" | sudo tee -a /etc/hosts

# WRONG — api.github.com has its own IP
echo "<reachableIP> github.com api.github.com" | sudo tee -a /etc/hosts

# if API calls are required, use --resolve to bypass hosts:
curl --resolve "api.github.com:443:20.205.243.168" \
  -H "Authorization: token $TOKEN" \
  https://api.github.com/user
```

**If hosts already has the wrong entry:**

```bash
# remove api.github.com from /etc/hosts
sudo sed -i 's/ github.com api.github.com/ github.com/' /etc/hosts
# or delete the line and rewrite it
```

### 4. Verify

```bash
git fetch origin main
# should return branch info normally → fix successful
```

## Temporary push bypass without sudo (no hosts edit required)

When the IP in hosts temporarily fails and you lack sudo to edit hosts:

```bash
# scan for a reachable IP first
python3 -c "import socket;s=socket.create_connection(('140.82.112.3',443),timeout=5);s.close();print('OPEN')"

# use http.curloptResolve to skip hosts and specify IP directly
git -c "http.curloptResolve=github.com:443:140.82.112.3" push

# also works for git clone
git -c "http.curloptResolve=github.com:443:140.82.112.3" clone https://github.com/user/repo.git
```

Principle: `http.curloptResolve` is equivalent to curl's `--resolve` option. It forces domain resolution to a specific IP at the libcurl level, bypassing system hosts and DNS.

## Notes

- `/etc/hosts` changes take effect immediately, no restart needed
- If git is configured with a proxy (`git config --global http.proxy`), troubleshoot the proxy first
- hosts entries do not conflict when DNS is working normally; can be used as a permanent solution
- Reachable IPs may vary by ISP/region; scan on-site

## One-click scan script

```bash
cat > ping_github.sh << 'SCRIPT'
#!/bin/bash
for ip in 140.82.112.3 140.82.112.4 140.82.113.3 140.82.114.3 \
          140.82.121.3 140.82.121.4 \
          185.199.108.153 185.199.109.153 185.199.110.153; do
  timeout 3 bash -c "echo > /dev/tcp/$ip/443" 2>/dev/null \
    && echo "OK $ip:443" || echo "FAIL $ip:443"
done
SCRIPT
chmod +x ping_github.sh
```

## Related

- `github-dns-443-block-hosts-workaround` (Chinese original)
