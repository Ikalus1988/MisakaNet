---
{
  "title": "Regex greedy matching — debugging unintended captures",
  "domain": "development",
  "tags": ["regex", "debug", "greedy", "pattern"],
  "status": "published",
  "lang": "en",
  "source": "uncledad96-glitch",
  "translated_from": "lessons/contrib/regex-greedy-matching.md",
  "created": "2026-08-02",
  "updated": "2026-08-02"
}
---

# Regex greedy matching — debugging unintended captures

## Problem

A regex that looks correct returns too much text, or the wrong match, because `*` and `+` are greedy by default. Example: extracting a URL from Markdown returns the entire paragraph instead of the link target.

## Root Cause

1. Greedy quantifiers (`.*`, `.+`) consume as much as possible while still allowing the overall pattern to match.
2. The engine backtracks, but only enough to satisfy the trailing token — which can still cross intended boundaries.
3. Dot (`.`) does not match newlines by default, so multiline inputs behave differently than expected.

## Solution

### 1. Prefer non-greedy quantifiers

```python
import re

text = "[text](https://example.com) and [more](https://other.com)"

# Greedy — captures everything between the first `](` and the last `)`
re.search(r"\]\((.*)\)", text).group(1)
# 'https://example.com) and [more](https://other.com'

# Non-greedy — stops at the first `)`
re.search(r"\]\((.*?)\)", text).group(1)
# 'https://example.com'
```

### 2. Use character classes when possible

```python
# Bad: .* spans across unwanted content
re.search(r'const\s+(\w+)\s*=.*;', source)

# Better: stop at the first semicolon
re.search(r'const\s+(\w+)\s*=[^;]*;', source)
```

### 3. Handle multiline input explicitly

```python
# If input spans lines, decide whether . should match newline
re.search(r"start(.*?)end", text, re.DOTALL)      # . matches \n
re.search(r"start(.*?)end", text, re.MULTILINE)   # ^/$ match line boundaries
re.search(r"(?s)start(.*?)end", text)             # inline DOTALL
```

### 4. Debug with a step-by-step matcher

```python
import regex  # third-party, supports partial match and better debugging

m = regex.search(r"\]\((.*?)\)", text, regex.DEBUG)
# Shows each token and whether it matched
```

## Verification

```bash
python3 -c "
import re
text = '[a](url1) [b](url2)'
greedy = re.search(r'\]\((.*)\)', text).group(1)
nongreedy = re.search(r'\]\((.*?)\)', text).group(1)
print('greedy: ', greedy)
print('nongreedy: ', nongreedy)
assert nongreedy == 'url1'
"
```

## Notes

- Greedy is not "wrong" — it is correct for the engine's definition. Choose the quantifier based on the desired boundary.
- When parsing LLM output, avoid regex when a structured decoder (JSON, TOML, XML) is available.
