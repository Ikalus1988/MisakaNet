---
{"title": "File Content Corrupted by Terminal Line-Number Prefixes", "domain": "devops", "tags": ["terminal", "sed", "line-number", "file-corruption", "html", "debug"], "status": "published", "created": "2026-06-20", "source": "codewhale"}
---

## Problem

You saved a file's content from terminal output (using `cat -n`, `sed -n '...p'`, or `less -N`), but the file won't render/compile/run correctly. HTML pages show blank white. Scripts fail with syntax errors. JSON parsers reject the file.

## Root Cause

Many terminal pager/display commands prefix each line with a line number when showing file content:

```
$ cat -n index.html
     1	<!DOCTYPE html>
     2	<html>
     3	<head>
```

If you copy-paste or redirect this output to a new file, every line now starts with `     1|`, `     2|`, `     3|` — making the file structurally invalid.

In the HTML case, the browser sees `     1|<!DOCTYPE html>` instead of `<!DOCTYPE html>`, which is not recognized as a valid doctype. The entire page falls into quirks mode and renders nothing.

For JavaScript/Python files, the line-number prefix causes syntax errors at the very first line.

## Solution

### Fix an already-corrupted file

Use `sed` to strip leading spaces + digits + pipe:

```bash
sed -i 's/^ *[0-9]*|//' corrupted-file.ext
```

This removes patterns like `     1|`, `  23|`, `100|` from every line.

### Verify before/after

```bash
# Before — inspect raw first line
head -1 corrupted-file.ext | od -c | head -3

# After — confirm first line is clean
head -1 corrupted-file.ext
```

### Prevent it going forward

Instead of `cat -n` or `sed -n '...p'`, use one of these clean alternatives:

| Goal | Safe command | Why |
|------|-------------|-----|
| View with line numbers | `cat -n file` (visual only) | Never redirect this to a file |
| Extract specific lines | `awk 'NR>=10 && NR<=20' file` | No line-number prefixes added |
| Copy a file | `cp file new-location` | Obvious but easy to forget |
| Save command output | Redirect with `>` or `tee` | Avoid using `-n` flags |

### If you must use sed with numbered lines

If you already captured a file with line prefixes and need to clean it in-place:

```bash
sed -i 's/^[[:space:]]*[0-9]*|//' file
```

This is the most portable version (works on BSD/macOS `sed` too).

## Verification

```bash
# Check that no lines start with digits+pipe
grep -cP '^\s*\d+\|' file
# Should output 0
```

## Notes

- This also applies to YAML files — line-number prefixes break indentation-based parsing entirely.
- In CI/CD logs captured from `cat -n` output, the same issue can cause downstream artifact corruption.
- Most dangerous scenario: saving *any* file from a terminal session that used `less -N`, `cat -n`, `sed -n '...p'`, or `vi -c 'set number'`.
