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

## Verification
Run the command to confirm the cap is now 60000:
```python
python3 -c "from misaki import config; print(config.get('intake_text_cap'))"
# Expected output: 60000
```

```