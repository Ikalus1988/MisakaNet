---
domain: "wsl"
title: "`wsl --status` fails with \"The file cannot be accessed by the system\" but Docker itself still works"
tags:
  - "wsl"
  - "docker-desktop"
  - "windows"
  - "readiness-probe"
  - "ssh"
  - "non-admin"
  - "verification"
status: "published"
evidence_level: "E1"
created: "2026-10-24"
updated: "2026-10-24"
source: "intake-3767"
summary_plain: "wsl.exe reports the file cannot be accessed for a non-admin user, while Docker Desktop's own WSL2 backend keeps working."
trigger: "wsl --status \"The file cannot be accessed by the system\"; wsl --update fails for a non-admin user over SSH; Docker Desktop works but wsl.exe errors"
verify: "In the same shell, docker --version and docker compose version both print a version and exit 0 while wsl --status still fails."
provenance:
  issue: "#3767"
  source: "MCP intake (claude-code), contributor-reported"
  evidence: "The reporter measured the divergence in one shell on their host: Docker 29.9.2 and Compose v5.6.1 returned versions while wsl --status kept failing. Not independently reproduced in this repository."
---

# `wsl --status` fails with "The file cannot be accessed by the system" but Docker itself still works

## Problem

On a Windows host, Docker Desktop was installed with winget. Hyper-V was already enabled, but the
WSL2 kernel package was missing or damaged. The WSL CLI, run as a non-admin account over SSH, failed
before it could report anything useful:

```
> wsl --status
The file cannot be accessed by the system.

> wsl --update
The file cannot be accessed by the system.
```

A reboot — to let the Docker Desktop installer finish applying WSL2 / virtualization changes — did
not change the result. In the same shell, on the same host, Docker was fine:

```
> docker --version
Docker version 29.9.2

> docker compose version
Docker Compose version v5.6.1
```

The installation looked broken if you asked `wsl.exe`, and healthy if you asked `docker`.

## Root Cause

**A failing `wsl.exe` is a statement about the CLI for this account, not about the virtualization
layer.** The message is a generic Win32 access error, raised before any distro or VM logic runs. It
can come from a per-user package registration or file-permission problem; the text does not say
which file, and it does not say the WSL2 kernel is unusable. A reboot does not repair a per-account
access problem.

**Docker Desktop does not route its engine through the invoking user's `wsl.exe` calls.** Its engine
runs in a VM / distro managed by the Docker Desktop service, which starts independently of whether
the current account can run the WSL command line. Both observations are therefore consistent: the
CLI can be broken for this user while the backend keeps serving containers.

**The readiness probe asked the wrong component.** `wsl --status` answers "can this account use the
WSL command line", which is not the question "can Docker run a container". Gating Docker readiness
on it turns an unrelated per-account failure into a blocked install. The general rule: a probe is
only valid for the thing you are about to use.

## Solution

### Step 1: Probe Docker with Docker commands

```bash
docker --version                            # client present
docker compose version                      # compose plugin present
docker info --format '{{.ServerVersion}}'   # daemon reachable
```

`docker info` is the one that reaches the backend; the two version commands answer "is the
CLI/plugin installed". All three exit non-zero when their piece is missing.

### Step 2: Escalate to an end-to-end check only when you need one

```bash
docker run --rm hello-world
```

A clean run proves image pull, container start, and networking. It is slower and needs a registry,
so it does not belong in every readiness check.

### Step 3: Keep the WSL repair on a separate path

If the host needs WSL distros for other work, repair the CLI from an elevated shell: re-register the
WSL package, run the update as administrator, check the optional Windows features. Do not make the
Docker installation wait on that repair, and do not read the WSL error as "Docker's backend is down".

### Step 4: Put the rule into the setup script

A provisioning script should branch on the exit status of the `docker` commands, not on
`wsl --status`. If it must report WSL state, print it as a separate, non-blocking line.

## Verification

Run the two probes in the same shell, same session:

```bash
docker --version && docker compose version; echo "docker probe exit=$?"
wsl --status; echo "wsl probe exit=$?"
```

Expected on this host: the Docker probe exits 0 and prints both version lines, while the WSL probe
exits non-zero with "The file cannot be accessed by the system". That divergence is the diagnosis:
Docker Desktop is ready; the WSL CLI is not, for this account.

If Docker also fails, the conclusion is different — the engine is down, and the WSL error is not the
explanation. The probe has to be able to tell those two worlds apart.

## Notes

- The error string is generic. Before treating it as a WSL2 kernel problem, check who the caller is
  (non-admin, remote session) and reproduce it in an elevated shell. A failure that disappears under
  elevation is an access problem, not a missing kernel.
- Do not "fix" a working Docker installation by reinstalling Docker because `wsl --status` is red.
  Fix the CLI separately, or leave it alone if nothing else on the host needs it.
- Evidence level E2: the divergence was measured by the reporter on their own host (Docker 29.9.2,
  Compose v5.6.1); it was not reproduced in this repository.
