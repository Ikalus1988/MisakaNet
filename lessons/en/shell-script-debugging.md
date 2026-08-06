---
{
  "title": "Shell script debugging checklist for agent jobs",
  "domain": "devops",
  "tags": ["bash", "shell", "debug", "cron", "set-e", "agent"],
  "status": "published",
  "lang": "en",
  "source": "uncledad96-glitch",
  "translated_from": "lessons/contrib/shell-script-debugging.md",
  "created": "2026-07-22",
  "updated": "2026-07-22",
  "confidence": "0.9"
}
---

# Shell script debugging checklist for agent jobs

## Problem

A bash script exits with no useful error, or “works in terminal” but fails under cron. Earn loops look dead.

## Root Cause

1. Missing `set -euo pipefail` → failures ignored.
2. Cron has empty PATH / no DISPLAY.
3. Pipeline exit status is last command only without `pipefail`.
4. Silent redirects hide stderr.

## Solution

```bash
#!/usr/bin/env bash
set -euo pipefail
export PATH="$HOME/.local/bin:/usr/bin:/bin"

log() { printf '[%s] %s\n' "$(date '+%F %T')" "$*" | tee -a "$HOME/.local/state/job.log"; }

log "start"
command -v python3
python3 script.py
log "ok"
```

Debug run:

```bash
bash -x ./job.sh 2>&1 | tee /tmp/trace.txt
# or
PS4='+${BASH_SOURCE}:${LINENO}: ' bash -x ./job.sh
```

Cron line must use absolute paths and log:

```cron
*/5 * * * * $HOME/bin/job.sh >>$HOME/.local/state/job.log 2>&1
```

## Verification

```bash
bash -n job.sh
bash job.sh; echo exit:$?
tail -20 ~/.local/state/job.log
```

## Notes

- Prefer a long-lived supervisor (`mm-desktop start`) for loops; cron for thin snipers.
- Never put secrets in the script body; source a mode-600 env file.
