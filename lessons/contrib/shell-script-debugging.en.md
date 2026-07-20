{
  "title": "Shell Script Debugging — set -x and Common Pitfalls",
  "domain": "devops",
  "tags": ["bash", "shell", "debugging", "set", "trap"],
  "status": "published",
  "source": "translated-contrib",
  "lang": "en",
  "translated_from": "shell-script-debugging.md"
}

# Shell Script Debugging — `set -x` and Common Pitfalls

## Problem

A bash script silently fails at line 47. No error message, no exit code — the script just stops producing output and hangs.

```bash
#!/bin/bash
result=$(curl -s https://api.example.com/data)
items=$(echo "$result" | jq '.items[]')
for item in $items; do
  process "$item"  # ← silently fails here
done
echo "Done"  # ← never reaches this line
```

## Root Cause

1. **Missing `set -e`**: Without `set -e`, the script continues past command failures, producing corrupted state
2. **Unquoted variable expansion**: `$items` undergoes word splitting — a single item containing spaces becomes multiple arguments
3. **No error handling on `curl`**: If the API returns a 500, `$result` is empty but the script doesn't check
4. **`jq` exits non-zero on invalid JSON**: Without `set -e` or explicit checking, this goes unnoticed

## Fix

```bash
#!/bin/bash
set -euo pipefail  # Exit on error, undefined vars, pipe failures
set -x             # Print each command before execution (debug mode)

# Add error handling
trap 'echo "ERROR at line $LINENO: command=$BASH_COMMAND"' ERR

result=$(curl -sS --fail https://api.example.com/data || {
  echo "API request failed" >&2
  exit 1
})

# Validate JSON before processing
if ! echo "$result" | jq empty 2>/dev/null; then
  echo "Invalid JSON response" >&2
  exit 1
fi

# Read items safely with null-delimiter
while IFS= read -r item; do
  process "$item"
done < <(echo "$result" | jq -r '.items[]')

echo "Done"
```

### Debugging Checklist

| Issue | Symptom | Fix |
|-------|---------|-----|
| Unset variable | `$VAR` expands to empty string | `set -u` |
| Pipe failure hidden | `false \| true` exits 0 | `set -o pipefail` |
| Variable not exported | Child process can't see it | `export VAR` or `VAR=val cmd` |
| Word splitting | "a b" becomes two args | Always quote: `"$var"` |
| Stale file descriptor | `/dev/fd/N` points to nothing | Use process substitution `<(cmd)` |

## Verification

```bash
# Test error handling
bash -x script.sh 2>&1 | tee debug.log
# Check exit code
echo "Exit: $?"

# Point-fix: run specific line range
bash -x script.sh 2>&1 | grep -A5 "line 47"
```

## Key Takeaways

- Start every script with `set -euo pipefail`
- Use `set -x` during development, remove or guard with `[[ -n "$DEBUG" ]]` in production
- `trap ... ERR` catches failures before `set -e` exits
- Always quote variable expansions: `"$var"`, not `$var`
- `curl --fail` ensures HTTP errors produce non-zero exit codes
