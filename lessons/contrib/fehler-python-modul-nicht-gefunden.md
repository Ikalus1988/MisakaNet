---
{
  "title": "ModuleNotFoundError in Python trotz pip install",
  "domain": "python",
  "tags": "[python, pip, module, path, virtualenv]",
  "language": "de",
  "status": "published",
  "source": "manual",
  "created": "2026-07-29",
  "confidence": 0.9,
  "verified_date": "2026-07-29",
  "author": "Liona Can",
  "edited_at": "2026-08-21T13:12:59+08:00",
  "merged_by": "Liona Can"
}
---

## Problem

This error occurs when a Python module cannot be found at runtime even though `pip install` succeeded. Running a script fails with:

```
$ python script.py
Traceback (most recent call last):
  File "script.py", line 1, in <module>
    import requests
ModuleNotFoundError: No module named 'requests'
```

But `pip list` shows the package as installed. This failure often happens after switching between projects or installing new packages.

## Root Cause

The root cause is almost always a mismatch between the Python environment where `pip install` was run and the environment executing `python script.py`.

The three most common scenarios:

1. **Virtual environment not activated**: `pip install` ran inside an active `venv`, but `python script.py` runs outside it.
2. **Multiple Python installations**: The system has several Python versions (3.9, 3.10, 3.11). `pip` installed into one, `python` uses another.
3. **`pip install --user` vs. system-wide**: The package was installed with `--user` into a local path, but `PYTHONPATH` does not include that path.

## Solution

**1. Identify which Python and pip are in use**
```bash
which python
python --version
which pip
pip --version
```
Ensure `python` and `pip` point to the same version.

**2. Use a virtual environment correctly**
```bash
python -m venv .venv
source .venv/bin/activate      # Linux/Mac
.venv\Scripts\activate          # Windows
```
Then install and run:
```bash
pip install requests
python script.py
```

**3. With multiple Python versions, use the explicit interpreter**
```bash
python3.11 -m pip install requests
python3.11 script.py
```
Or use `pip3`:
```bash
pip3 install requests
python3 script.py
```

**4. Check PYTHONPATH**
```bash
python -c "import sys; print('\n'.join(sys.path))"
```
Confirm that the site-packages path for your Python installation appears in the list.

**5. Install with --target as a last resort**
```bash
python -m pip install --target=$HOME/.local/lib/python3.11/site-packages requests
export PYTHONPATH=$HOME/.local/lib/python3.11/site-packages:$PYTHONPATH
```

## Verification

- Run `which python` and `which pip` — both should point to the same installation
- Execute `python -c "import requests; print(requests.__version__)"` without errors
- Inside a virtual environment, confirm `pip list` shows the package
- Test with a full script that uses the imported package

## Notes

- Always create a dedicated virtual environment per project with `python -m venv`
- Do not commit `.venv/` to your repository (add it to `.gitignore`)
- On Windows, use `py -3.11` instead of `python3.11`
- Re-run `pip install -r requirements.txt` whenever `requirements.txt` changes
- Reference: [Python venv documentation](https://docs.python.org/3/tutorial/venv.html)
