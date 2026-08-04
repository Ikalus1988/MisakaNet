---
{
  "title": "WSL2 memory leak — runaway host memory usage",
  "domain": "devops",
  "tags": ["wsl", "memory", "leak", "performance", "windows"],
  "status": "published",
  "lang": "en",
  "source": "uncledad96-glitch",
  "translated_from": "lessons/contrib/wsl2-memory-leak-fix.md",
  "created": "2026-08-02",
  "updated": "2026-08-02",
  "confidence": "0.9"
}
---

# WSL2 memory leak — runaway host memory usage

## Problem

After a few days, WSL2 consumes 8 GB+ of host RAM and Windows becomes sluggish. `free -h` inside WSL shows almost all memory in use, and `htop` reveals no single process holding the memory.

## Root Cause

WSL2 uses dynamic memory allocation and does not aggressively release memory back to Windows by default. Long-running processes (Python services, vector databases, Docker, Jupyter) allocate memory that is not returned to the host when the process exits. This is documented in the [WSL release notes](https://docs.microsoft.com/en-us/windows/wsl/faq#how-do-i-configure-wsl-to-use-less-memory).

Common causes stacked together:
1. No `.wslconfig` memory cap set.
2. VM cache not dropped after bulk file operations.
3. Stale WSL instance holding onto allocated pages across reboots.

## Solution

### 1. Inspect current memory state

```bash
free -h
cat /proc/meminfo | grep MemAvailable
ps aux --sort=-%mem | head -10
```

### 2. Cap WSL2 memory (Windows-side)

Create or edit `C:\Users\<username>\.wslconfig`:

```ini
[wsl2]
memory=4GB
swap=2GB
localhostForwarding=true
```

Then restart WSL from PowerShell:

```powershell
wsl --shutdown
wsl
```

### 3. Drop caches manually (Linux-side)

```bash
sudo sh -c 'echo 3 > /proc/sys/vm/drop_caches'
```

### 4. Restart WSL

```powershell
wsl --shutdown
```

## Verification

```bash
free -h
# Available memory should stay within the cap set in .wslconfig
```

Run `wsl -l -v` in PowerShell to confirm the WSL instance restarted cleanly.

## Notes

- If `htop` or `ps` shows a single process holding memory, kill it before dropping caches.
- WSL1 uses `drvfs` and does not have the same dynamic memory behavior.
- For Docker inside WSL2, also set memory limits in Docker Desktop settings.
