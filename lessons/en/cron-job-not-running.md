---
{
  "title": "Cron job not running — checklist that actually finds it",
  "domain": "devops",
  "tags": ["cron", "crontab", "systemd", "linux", "scheduler", "ops"],
  "status": "published",
  "lang": "en",
  "source": "uncledad96-glitch",
  "created": "2026-07-21",
  "updated": "2026-07-21",
  "confidence": "0.9"
}
---

# Cron job not running — checklist that actually finds it

## Problem

You added a crontab line, but the job never fires. Logs stay empty. Earn snipers / refresh scripts appear "dead" overnight.

## Root Cause

Typical causes stacked together:

1. Wrong user crontab (root vs user)
2. `%` in command not escaped
3. Minimal PATH inside cron
4. Job exits immediately on missing env (`MM_WORKSPACE`, secrets)
5. Laptop/desktop asleep; no RTC wake
6. `crontab` installed but `cron` daemon not running

## Solution

```bash
# 1. daemon up?
systemctl status cron || systemctl status crond

# 2. what is installed for this user?
crontab -l

# 3. absolute paths + PATH
# bad:  mm-snipe
# good:
# */1 * * * * export PATH="$HOME/.local/bin:/usr/bin:/bin"; $HOME/.local/bin/mm-snipe >>$HOME/.local/state/hermes-moneymaker/snipe.log 2>&1

# 4. percent signs
# use \% inside crontab or wrap in bash -c

# 5. manual run as same user
$HOME/.local/bin/mm-snipe; echo exit:$?

# 6. watch logs
tail -f $HOME/.local/state/hermes-moneymaker/snipe.log
```

For long-lived earn loops, prefer a supervised process (`mm-desktop start`) plus a thin sniper cron — do not double-schedule the same heavy job every minute without a PID lock.

## Verification

```bash
# after one schedule period
ls -la $HOME/.local/state/hermes-moneymaker/*.log
grep -i error $HOME/.local/state/hermes-moneymaker/snipe.log | tail
```

## Notes

- Desktop Linux may not run user cron while logged out depending on distro.
- systemd user timers are an alternative when linger is enabled.
