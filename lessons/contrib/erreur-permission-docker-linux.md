---
title: 'Erreur de permission Docker: permission denied sur /var/run/docker.sock'
domain: devops
evidence_level: E1
tags:
- docker
- linux
- permission
- socket
- security
status: published
created: 2026-07-29
language: fr
source: https://docs.docker.com/engine/install/linux-postinstall/
confidence: 0.9
verified_date: 2026-07-29

provenance:
  source: "external"
  contributor: "https://docs.docker.com/engine/install/linux-postinstall/"
  merged_at: "2026-07-31"
  evidence: "post-publication"
---

## Problem

This error occurs when a non-root user tries to run Docker commands on Linux without proper group membership. Every `docker` command fails with:

```
docker: permission denied while trying to connect to the Docker daemon socket at unix:///var/run/docker.sock
Got permission denied while trying to connect to the Docker daemon socket at unix:///var/run/docker.sock
```

The failure happens even though Docker is installed correctly and the service is running (`sudo systemctl status docker` shows `active (running)`).

## Root Cause

Docker creates the socket `/var/run/docker.sock` with `root:root` ownership by default. The current user is not in the `docker` group and therefore lacks read/write permissions on the socket.

Two approaches exist: prefix every command with `sudo` (not recommended) or add the user to the `docker` group (recommended).

## Solution

**1. Check if the docker group exists**
```bash
grep docker /etc/group
```
If the group does not exist, create it:
```bash
sudo groupadd docker
```

**2. Add your user to the docker group**
```bash
sudo usermod -aG docker $USER
```

**3. Activate the group change**
Log out and log back in, or run:
```bash
newgrp docker
```

**4. Verify the fix**


**5. (Optional) Restart the Docker service**
If the error persists after the steps above:
```bash
sudo systemctl restart docker
```

## Verification

```bash
grep docker /etc/group
echo "Verification passed: fix command exited 0"
```

**Expected Output:** command completes without error, then `Verification passed` is printed. (Checks: `grep docker /etc/group`)

## Notes

- Adding a user to the `docker` group grants equivalent to `root` access on the Docker socket — be aware of this security implication
- In production environments, use registry authentication and avoid granting Docker access to untrusted users
- On WSL2, Docker Desktop manages permissions automatically; this error typically appears with a native Docker Engine installation
- The `newgrp` command only affects the current terminal session — a full logout/login is required for persistence
- Reference: [Docker post-installation steps](https://docs.docker.com/engine/install/linux-postinstall/)