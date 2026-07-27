---
{
  "title": "Silent nginx Config Bugs That Pass nginx -t",
  "domain": "devops",
  "tags": ["nginx", "configuration", "security", "debugging", "silent-failures"],
  "language": "en",
  "status": "published",
  "source": "https://dev.to/shinagawa-web/nginx-t-passed-but-the-behavior-is-wrong-config-patterns-that-break-silently-outside-the-syntax-2nnc",
  "created": "2026-07-27",
  "confidence": 0.9
}
---

## Problem

You run `nginx -t` and get "syntax is ok, test is successful". You reload with `nginx -s reload` with no errors. The error log is clean. But nginx behaves differently than your config intends—and sometimes in security-breaking ways.

**Concrete scenario:** You add `add_header X-Custom-Header "value";` in a location block to set a custom header, intending to inherit parent block headers. After reload, only your new header appears; all parent headers vanish. Or you use `alias /var/www/;` in a location without a trailing slash in the location path, creating an unintended directory traversal.

## Root Cause

nginx config validation (`nginx -t`) only checks syntax grammar. It does NOT validate:

1. **Semantic correctness** - whether config is interpreted as intended
2. **Security implications** - whether directives create vulnerabilities
3. **Runtime behavior** - whether reload operations serve old vs new config

Four classes of silent failures pass validation:

- **if blocks in locations** treat implicit nested location context differently
- **add_header inheritance** drops all parent headers when child adds any header
- **alias path traversal** when location path and alias path have mismatched trailing slashes
- **reload race conditions** where old workers serve requests during graceful reload

## Solution

### 1. Audit add_header inheritance patterns

```nginx
# WRONG - child add_header drops all parent headers
server {
  add_header X-Parent "parent-value";
  
  location /api {
    add_header X-Child "child-value";
    # Result: only X-Child appears, X-Parent is dropped
  }
}
```

```nginx
# CORRECT - repeat parent headers in child, or restructure
server {
  location /api {
    add_header X-Parent "parent-value";
    add_header X-Child "child-value";
    # Result: both headers appear
  }
}
```

### 2. Validate alias path consistency

```nginx
# WRONG - location has no trailing slash, alias has trailing slash
location /downloads {
  alias /var/www/downloads/;
}
# Request: GET /downloads/../../../etc/passwd
# Vulnerability: traversal possible
```

```nginx
# CORRECT - both have trailing slashes
location /downloads/ {
  alias /var/www/downloads/;
}
# Or both without trailing slashes
location /downloads {
  alias /var/www/downloads;
}
```

### 3. Remove if blocks from location context

```nginx
# WRONG - if block changes context
location /api {
  if ($request_method = POST) {
    return 405;
  }
  proxy_pass http://backend;
}
```

```nginx
# CORRECT - use limit_except or separate blocks
location /api {
  limit_except GET HEAD {
    deny all;
  }
  proxy_pass http://backend;
}
```

### 4. Handle reload race conditions

```nginx
# After changing config, verify old workers are gone
# Step 1: Apply new config
sudo nginx -t
sudo nginx -s reload

# Step 2: Wait for graceful shutdown
sleep 5

# Step 3: Verify only new workers exist
sudo ps aux | grep '[n]ginx'
# All processes should show recent start time

# Step 4: Check new config is active
curl -I http://localhost | grep X-Custom-Header
```

## Verification

### Test add_header inheritance bug

```bash
# Create test nginx config
cat > /tmp/test-nginx.conf << 'EOF'
http {
  server {
    add_header X-Parent "from-parent";
    
    location /inherit {
      add_header X-Child "from-child";
    }
    
    location /no-child {
      # No add_header here
    }
  }
}
EOF

# Validate passes
sudo nginx -t -c /tmp/test-nginx.conf
# Output: syntax is ok, test is successful

# Start nginx with this config and test
curl -I http://localhost/inherit
# Shows only X-Child (BUG: X-Parent missing)

curl -I http://localhost/no-child
# Shows X-Parent (correct)
```

### Test alias traversal vulnerability

```bash
# Create vulnerable config
cat > /tmp/alias-test.conf << 'EOF'
server {
  location /files {
    alias /var/www/files/;
  }
}
EOF

# Validation passes
sudo nginx -t -c /tmp/alias-test.conf
# Output: syntax is ok, test is successful

# But traversal works
curl http://localhost/files/../../../etc/passwd
# VULNERABLE: may expose /etc/passwd
```

### Test reload race condition

```bash
# Get initial worker PIDs
PIDS_BEFORE=$(ps aux | grep '[n]ginx: worker' | awk '{print $2}')
echo "Workers before reload: $PIDS_BEFORE"

# Trigger reload
sudo nginx -s reload

# Check immediately
sleep 1
PIDS_AFTER=$(ps aux | grep '[n]ginx: worker' | awk '{print $2}')
echo "Workers after reload: $PIDS_AFTER"

# Old PID may still exist and serve requests
echo "Old PIDs still running: $(comm -23 <(sort <<< "$PIDS_BEFORE") <(sort <<< "$PIDS_AFTER"))"
```

## Notes

- **nginx -t only validates syntax, not behavior** — always test config changes in staging
- **add_header is not inherited by default** — if you override in a child block, explicitly repeat parent headers
- **alias requires matching trailing slash patterns** — mismatches create traversal vectors
- **Graceful reload has a window** — old workers continue serving until current requests finish; this can be 30+ seconds
- **Security implications are silent** — a traversal vulnerability won't appear in error logs or validation

## References

- https://nginx.org/en/docs/http/ngx_http_headers_module.html#add_header
- https://nginx.org/en/docs/http/ngx_http_core_module.html#alias
- https://nginx.org/en/docs/control.html (reload signal behavior)
- CWE-22: Improper Limitation of a Pathname to a Restricted Directory ('Path Traversal')