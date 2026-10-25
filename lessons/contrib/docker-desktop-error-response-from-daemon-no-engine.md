---
title: "Docker Desktop \"unable to start\" on Windows when wsl.exe is broken: use Docker Engine inside a WSL2 distro"
domain: "docker"
tags:
  - "docker-desktop"
  - "wsl"
  - "windows"
  - "docker-engine"
  - "daemon"
  - "wsl2"
  - "named-pipe"
  - "hyper-v"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "Docker Desktop 起不来、vm/init.log 全空，但 wsl -d <发行版> 能进 shell：wsl.exe 的 CLI 层坏了，绕开 Desktop，改用发行版里的 Docker Engine。"
trigger: "Error response from daemon: Docker Desktop is unable to start; wsl --status The file cannot be accessed by the system"
verify: "At the same moment: `wsl -d Ubuntu-24.04 -u root docker ps -a` prints a container table and `docker compose version` prints a version, while Windows-side `docker ps -a` still fails."
source: "intake-3791"
provenance:
  issue: "#3791"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# Docker Desktop "unable to start" on Windows when wsl.exe is broken: use Docker Engine inside a WSL2 distro

## Problem

On a Windows host, Docker Desktop refused to start:

```
Error response from daemon: Docker Desktop is unable to start
```

It repeated indefinitely, and the guest VM's init log was always **completely empty** — the reporter's
`vm/init.log` never contained a single line of boot output. On the same host, `wsl.exe` subcommands
failed:

```
> wsl --status
The file cannot be accessed by the system.

> wsl --list
The file cannot be accessed by the system.

> wsl --update
The file cannot be accessed by the system.
```

None of the usual repairs changed either symptom:

- enabling the `HypervisorPlatform` Windows optional feature (it was Disabled, while
  `VirtualMachinePlatform` and the WSL feature were Enabled);
- multiple reboots;
- disabling Credential Guard and Memory Integrity (HVCI) through Core Isolation;
- a full clean uninstall and reinstall of Docker Desktop, including deleting `%APPDATA%\Docker`,
  `%LOCALAPPDATA%\Docker`, the `%ProgramData%` Docker data, and the install directory.

The observation that separated the layers: `wsl -d Ubuntu-24.04 -u root` still dropped into a working
Linux shell on that same machine, at the same time that `wsl --status` and `wsl --list` failed.

## Root Cause

**The `wsl.exe` launcher/CLI was broken at the OS level** — the reporter's conclusion from the
asymmetry above, not a Docker Desktop setting. Docker Desktop's WSL2 backend provisions its VM through
that `wsl.exe` path, so when the launcher is broken the VM is never created. That is why `vm/init.log`
is empty rather than showing a failed boot: there was no boot to log. Feature toggles, HVCI changes and
a full reinstall do not repair a corrupted `wsl.exe`, which is why none of them moved the needle.

Launching a named distro directly still works (`wsl -d <DistroName>` reaches a working Linux shell), so
the Linux side of WSL is usable even though the subcommand path Docker Desktop relies on is not. That
asymmetry is what makes a bypass possible: run the engine *inside* the distro instead of asking Docker
Desktop to build a VM on the Windows side.

## Solution

### Step 1: prove the asymmetry before changing anything

```powershell
wsl --status
wsl --list
wsl -d Ubuntu-24.04 -u root
```

If the third command gives you a Linux shell while the first two fail, the rest of this lesson applies.
If `wsl -d <DistroName>` also fails, this is a different failure — the distro or the WSL subsystem
itself — and the bypass below will not work.

### Step 2: install Docker Engine inside the distro

```powershell
wsl --install -d Ubuntu-24.04     # only if the distro does not exist yet
wsl -d Ubuntu-24.04 -u root
```

Inside the distro, install the engine from that distro's packages:

```bash
apt-get update
apt-get install -y docker.io        # or the docker-ce packages from Docker's apt repo
```

### Step 3: fix the socket permission inside the distro

If `docker ps -a` returns `permission denied ... unix:///var/run/docker.sock`, either add your user to
the `docker` group and start a fresh WSL session:

```bash
sudo usermod -aG docker "$USER"
# exit the distro and re-enter it: wsl -d Ubuntu-24.04
```

or run as root, which is what the reporter used for the verification:

```powershell
wsl -d Ubuntu-24.04 -u root docker ps -a
```

The group change needs a new session; re-entering the distro is the step people skip.

### Step 4: use the distro as the container host, not Docker Desktop

Run `docker` through `wsl -d <DistroName>` from PowerShell/cmd, and stop treating Docker Desktop's
Windows-side VM management as the thing to repair. Windows-side `docker` talks to Docker Desktop's
named pipe; while Docker Desktop cannot start, that pipe has nothing behind it, and no Docker-side
configuration change can alter that. Anything that hardcodes the Windows-side `docker.exe` (IDE
extensions, scripts that assume Docker Desktop's named pipe) keeps failing until Docker Desktop itself
is repaired.

## Verification

At the same moment, from the same machine:

```powershell
# Windows side — still broken
docker ps -a

# WSL distro side — the workaround
wsl -d Ubuntu-24.04 -u root docker ps -a
wsl -d Ubuntu-24.04 -u root docker compose version
```

Expected from the reporter's run: the Windows-side command still failed with "Docker Desktop is unable
to start", while the WSL-side `docker ps -a` returned a normal (empty) container table and
`docker compose version` printed `Docker Compose version v5.6.1`.

That divergence **is** the pass criterion. This fix is a bypass, not a repair, so the Windows-side
failure is expected to remain; the containers are managed by the distro's own daemon from now on.

## Notes

- Evidence E1: the reporter measured the divergence on their own machine; it was not reproduced in this
  repository.
- Opposite case of `wsl-status-fails-but-docker-desktop-works` (intake #3767): there the same `wsl.exe`
  error appeared while Docker's CLI still answered, and the conclusion was "do not fix a working
  Docker". Probe the Docker side first — if `docker ps` from Windows works, you do not need this
  migration.
- Do not reinstall Docker Desktop again on the strength of this lesson. The reporter already did a full
  clean reinstall, and it changed neither `wsl.exe` nor the daemon error.
- The report does not record a successful repair of `wsl.exe` itself, and it does not name the corrupted
  Windows component. The lesson covers the bypass, not the OS repair.
- Containers started through `wsl -d <DistroName>` are managed by the distro's own daemon; Docker
  Desktop's WSL integration and named pipe are not part of that path.
