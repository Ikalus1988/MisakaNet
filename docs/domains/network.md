# Network Domain

Lessons about network configuration, proxies, firewalls, and connectivity for MisakaNet nodes.

---

## network — WSL needs proxy for external access

**Problem:** `pip install`, `git clone`, and GitHub API calls fail from WSL due to no transparent proxy.

**Fix:** Export `HTTP_PROXY`/`HTTPS_PROXY` in `~/.bashrc`, or configure `.wslconfig` for Windows proxy passthrough.

**Verify:** `curl -I https://api.github.com` returns 200.

---

## network — workers.dev domain intermittent blocking

**Problem:** Cloudflare `*.workers.dev` domain is unreliable from some regions (DNS/SNI blocking).

**Fix:** Bind a custom domain to the Worker with Cloudflare proxy (orange cloud) enabled.

**Verify:** `curl -I https://your-domain.com/` returns 200 from the target region.

---

## network — firewall port open ≠ intranet tunnel

**Problem:** Opening port 8080 in Windows firewall does not make the service accessible from the internet.

**Fix:** Use Cloudflare Tunnel (`cloudflared`) or a reverse proxy for public access. Do NOT rely on port forwarding alone.

**Verify:** `curl -I https://tunnel.your-domain.com/` returns the expected service response.

---

*More: search lessons with `search_knowledge.py "network|proxy" --lessons`*
