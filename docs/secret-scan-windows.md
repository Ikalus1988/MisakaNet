# Local CI Secret-Scan Troubleshooting on Windows

This guide helps Windows contributors resolve crashes and errors when running the local secret-scan audit script (`scripts/check_worker_secrets.py`).

---

## ❓ What is the Secret-Scan failure?

MisakaNet includes a security gate script at `scripts/check_worker_secrets.py` that scans for hardcoded secrets and verifies env var checks. This script is run automatically in the pre-push and PR checks.

On Windows, running the script directly can crash with the following error:

```text
Traceback (most recent call last):
  File "scripts\check_worker_secrets.py", line 209, in <module>
    sys.exit(main())
  File "scripts\check_worker_secrets.py", line 132, in main
    print("\U0001f50d Worker Secret & Env Handling Audit")
UnicodeEncodeError: 'charmap' codec can't encode character '\U0001f50d' in position 0: character maps to <undefined>
```

### Root Cause
This occurs because the Windows console (PowerShell or Command Prompt) defaults to a regional encoding (such as `GBK`, `CP936`, or `CP1252`). When the Python script attempts to print emojis (like `🔍` or `✅`), the default encoder fails to map these Unicode characters to the console's character page, throwing a `UnicodeEncodeError`.

---

## 🚀 Copy-Paste Fixes for Windows

Use any of the following methods to run the script successfully on Windows:

### Method 1: Use Python's UTF-8 Mode (Recommended)
You can force Python to run in UTF-8 mode by passing the `-X utf8` flag:

```bash
python3 -X utf8 scripts/check_worker_secrets.py
```

### Method 2: Set the `PYTHONIOENCODING` Environment Variable
You can explicitly configure Python to output in UTF-8.

#### In PowerShell:
```powershell
$env:PYTHONIOENCODING="utf-8"
python3 scripts/check_worker_secrets.py
```

#### In Command Prompt (cmd):
```cmd
set PYTHONIOENCODING=utf-8
python3 scripts/check_worker_secrets.py
```

#### In Git Bash:
```bash
export PYTHONIOENCODING=utf-8
python3 scripts/check_worker_secrets.py
```

### Method 3: Use the `PYTHONUTF8` Environment Variable
Enable UTF-8 mode globally in your shell session.

#### In PowerShell:
```powershell
$env:PYTHONUTF8=1
python3 scripts/check_worker_secrets.py
```

#### In Git Bash:
```bash
export PYTHONUTF8=1
python3 scripts/check_worker_secrets.py
```
