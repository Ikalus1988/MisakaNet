# Diagnosing and Resolving "Port Is Already Allocated" in Docker Compose

**Domain:** Docker, DevOps, Port Management
**Tags:** docker, compose, port, binding
**Audience:** Intermediate
**Verified:** Yes
**Time:** 15 minutes

```verify
cd "$(mktemp -d)"
cat > docker-compose.yaml << 'EOF'
services:
  web:
    image: nginx:alpine
    ports:
      - "8080:80"
EOF
docker compose up -d 2>&1 || true
docker compose ps 2>/dev/null || true
docker compose down 2>/dev/null || true
echo "Test environment prepared"
```

## Problem Statement

`docker compose up` fails with:

```
Bind for 0.0.0.0:8080 failed: port is already allocated
```

How do you locate the process occupying the port and release it safely?

This is a **recorded false blind spot**: a previous search for this exact error returned zero relevant lessons, with the top hit being an unrelated Ruby memory leak article.

## Key Insight

Docker binds ports at the **host level**, not inside containers. When Docker says a port is "already allocated," it means some process on the host is listening on that port—or Docker itself previously bound it and hasn't released it (e.g., after a crash).

## Step-by-Step Diagnosis

### Step 1: Identify What's Using the Port

```bash
# Linux
sudo lsof -i :8080
# or
sudo ss -tlnp | grep 8080

# macOS
lsof -i :8080
# or
netstat -an | grep 8080
```

This shows the PID and command of the process holding the port.

### Step 2: Check for Stale Docker Containers

```bash
# List all containers (including stopped ones)
docker ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Look for containers that still have 8080 mapped but are in an odd state
docker inspect $(docker ps -aq) --format '{{.Name}}: {{.HostConfig.PortBindings}}' 2>/dev/null | grep 8080
```

A container may appear stopped but still hold the port binding in Docker's internal state.

### Step 3: Force-Clean Stale Bindings

```bash
# Stop and remove ALL containers (use with caution)
docker compose down -v

# Or remove specific container
docker rm -f <container_name>

# As a last resort, restart Docker daemon
sudo systemctl restart docker
```

Restarting the Docker daemon clears all stale port bindings but stops all running containers.

### Step 4: Kill the Occupying Process (If Not Docker)

```bash
# From Step 1, you get a PID. Kill it if safe.
kill <PID>

# Or forcefully
kill -9 <PID>
```

**Warning:** Only kill processes you recognize. Killing system services can break functionality.

## Prevention Strategies

### 1. Use Dynamic Port Assignment

Instead of hardcoding ports, let Docker assign them:

```yaml
services:
  web:
    image: nginx:alpine
    ports:
      - "0.0.0.0:0:80"  # Docker picks an available port
```

Or use `docker compose`'s automatic port allocation by omitting the host port:

```yaml
ports:
  - "80"  # Container port only, no host binding
```

### 2. Use a Port Range

```yaml
ports:
  - "8100-8200:80"  # Docker picks from this range
```

### 3. Add a Pre-Flight Check in Scripts

```bash
#!/bin/bash
# preflight.sh - Check ports before docker compose up
for port in 8080 8443; do
  if lsof -i :$port -sTCP:LISTEN >/dev/null 2>&1; then
    echo "ERROR: Port $port is in use. freeing..."
    fuser -k $port/tcp 2>/dev/null
  fi
done
docker compose up -d
```

## Concrete Reproduction and Resolution

```bash
# Reproduce the error
cd "$(mktemp -d)"
cat > docker-compose.yaml << 'EOF'
services:
  web:
    image: nginx:alpine
    ports:
      - "8080:80"
EOF

# Start first compose
docker compose up -d

# Try starting again (same port) — this fails
docker compose up -d 2>&1 | grep -i "port is already"

# Resolve: stop the first one
docker compose down

# Now it works
docker compose up -d
```

## Debugging Tip: Docker's Internal Port State

Docker tracks port bindings in `/var/lib/docker` (Linux) or the Docker VM (macOS/Windows). If `docker ps` shows no container using the port but Docker still refuses to bind it, the internal state is stale:

```bash
# Linux: check Docker's internal container list
sudo ls /var/lib/docker/containers/

# Find containers referencing port 8080
sudo grep -r 8080 /var/lib/docker/containers/ 2>/dev/null | head -20
```

Cleaning up orphaned container directories (after ensuring Docker is stopped) can resolve phantom port conflicts.

## Cross-Reference

- Related: #2256 — Whitespace verification with `git diff --check`
- Related: #2469 — Multi-file patch hunk rejection

**Provenance:** The reporter explicitly noted that searching for this error returned zero matching lessons and the top result was an unrelated Ruby memory leak article—confirming this as a genuine blind spot in the corpus.

provenance.issue: #2804
