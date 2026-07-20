{
  "title": "Cron Job Not Running / Not Taking Effect — Troubleshooting Guide",
  "domain": "devops",
  "tags": ["cron", "scheduler", "not-running", "debug", "linux"],
  "status": "published",
  "source": "translated-contrib",
  "lang": "en",
  "translated_from": "cron-job-not-running.md"
}

# Cron Job Not Running / Not Taking Effect

## Problem

After setting up `crontab -e`, the job never executes. No output, no logs, no process.

## Root Cause

1. Cron's environment variables are completely different from an interactive shell (no PATH, no HOME, etc.)
2. Cron syntax error (wrong order of `* * * * *` fields)
3. Missing trailing newline at the end of the crontab file

## Fix

```bash
# 1. Check if cron daemon is running
sudo systemctl status cron
# or
ps aux | grep cron

# 2. Print current crontab
crontab -l

# 3. Write a test job to confirm cron is working
crontab -e
# Add this line:
* * * * * echo "CRON_ALIVE: $(date)" >> ~/cron_test.log 2>&1

# 4. Check logs (varies by distro)
sudo tail -f /var/log/syslog | grep CRON
# or
sudo journalctl -u cron -f

# 5. Common fix: explicitly set PATH in crontab
# Add these lines at the top of your crontab:
PATH=/usr/local/bin:/usr/bin:/bin
SHELL=/bin/bash
HOME=/home/yourname

# 6. Complete recipe for running Python scripts in cron
*/5 * * * * cd /path/to/project && /usr/bin/python3 script.py >> /tmp/script.log 2>&1
```

## Verification

```bash
cat ~/cron_test.log  # Should have one new line per minute
```

## Key Takeaways

- Cron runs in a minimal environment — always set PATH, SHELL, and HOME explicitly
- The five fields are: minute hour day-of-month month day-of-week (not second first)
- Always redirect output (`>> file 2>&1`) or you'll never know what went wrong
- Test with a simple echo job before trusting complex pipelines
