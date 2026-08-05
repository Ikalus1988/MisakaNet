---
{
  "title": "python-venv: ModuleNotFoundError for tiktoken (and friends)",
  "domain": "python",
  "tags": ["python", "venv", "tiktoken", "ModuleNotFoundError", "pip"],
  "status": "published",
  "lang": "en",
  "source": "uncledad96-glitch",
  "translated_from": "lessons/contrib/python-venv-tiktoken-module-not-found.md",
  "created": "2026-07-22",
  "updated": "2026-07-22",
  "confidence": "0.9"
}
---

# python-venv: ModuleNotFoundError for tiktoken (and friends)

## Problem

`import tiktoken` (or another wheel-heavy package) fails with `ModuleNotFoundError` even after `pip install`, usually inside an agent venv.

## Root Cause

1. Install went to a different Python than the one running the script.
2. venv not activated in the job environment.
3. Build isolation / missing wheel on arch → silent fallback install failed.

## Solution

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install tiktoken
python -c "import tiktoken; print(tiktoken.__file__)"
```

Pin the interpreter in systemd/cron:

```bash
/home/you/proj/.venv/bin/python -c "import tiktoken"
```

If wheels fail:

```bash
python -m pip install --only-binary=:all: tiktoken || \
  python -m pip install tiktoken --no-cache-dir
```

## Verification

```bash
.venv/bin/python -c "import tiktoken; enc=tiktoken.get_encoding('cl100k_base'); print(len(enc.encode('hi')))"
```

## Notes

- Always `python -m pip` with the same binary you execute.
- Log `sys.executable` at job start for overnight agents.
