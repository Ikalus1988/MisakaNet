```python
# Intake Text Cap Adjustment

## Domain
Content Processing

## Problem
The intake text cap was set to 40000, which was too low for some use cases.

## Root Cause
The cap of 40000 limited the amount of text that could be processed during intake.

## Fix
The cap was increased to 60000 to allow more text to be included.
misaki.config.intake_text_cap = 60000

## Verification
Run the command to confirm the cap is now 60000:
```python
python3 -c "from misaki import config; print(config.get('intake_text_cap'))"
# Expected output: 60000
```

```json
{
  "kind": "missing_lesson",
  "problem": "2026-10-20T08:23:01.4656410Z shell: C:\\Program Files\\Git\\bin\\bash.EXE --noprofile --norc -e -o pipefail {0}\r\n2026-10-20T08:23:01.5333741Z ##[error]Tests failed — see test_output.txt\r\n2026-10-20T08:23:01.5350248Z ##[error]Process completed with exit code 1.\r\n2026-10-20T08:23:01.55",
  "error": "2026-10-20T08:23:01.4656410Z shell: C:\\Program Files\\Git\\bin\\bash.EXE --noprofile --norc -e -o pipefail {0}\r\n2026-10-20T08:23:01.5333741Z ##[error]Tests failed — see test_output.txt\r\n2026-10-20T08:23:01.5350248Z ##[error]Process completed with exit code 1.\r\n2026-10-20T08:23:01.55",
  "what_tried": "",
  "source": "github-action",
  "matched_lesson_id": "",
  "fix": "",
  "verification": ""
}
```