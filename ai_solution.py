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
{{
  "kind": "missing_lesson",
  "problem": "2026-10-20T08:56:35.4342664Z shell: /usr/bin/bash --noprofile --norc -e -o pipefail {{0}}\n2026-10-20T08:56:35.4451647Z ##[error]Tests failed — see test_output.txt\n2026-10-20T08:56:35.4461023Z ##[error]Process completed with exit code 1.\n2026-10-20T08:56:35.4507600Z \u001b[36;1m# value w",
  "error": "2026-10-20T08:56:35.4342664Z shell: /usr/bin/bash --noprofile --norc -e -o pipefail {{0}}\n2026-10-20T08:56:35.4451647Z ##[error]Tests failed — see test_output.txt\n2026-10-20T08:56:35.4461023Z ##[error]Process completed with exit code 1.\n2026-10-20T08:56:35.4507600Z \u001b[36;1m# value w",
  "what_tried": "",
  "source": "github-action",
  "matched_lesson_id": "",
  "fix": "",
  "verification": ""
}}
```