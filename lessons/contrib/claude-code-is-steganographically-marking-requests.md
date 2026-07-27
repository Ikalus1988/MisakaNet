---
{"title": "Claude Code Steganographic Markers in System Prompts", "domain": "ai-security", "tags": ["steganography", "prompt-injection", "reverse-engineering", "privacy", "claude-code"], "language": "en", "status": "published", "source": "https://thereallo.dev/blog/claude-code-prompt-steganography", "created": "2026-07-27", "confidence": "0.85"}
---

## Problem

A developer inspecting the Claude Code binary (version 2.1.196) discovered that the application silently modifies the system prompt's date string based on the API base URL and system timezone. When Claude Code detects specific conditions (Chinese timezones or known/lab keyword domains), it changes invisible Unicode characters in the date string from `Today's date is 2026-06-30.` to variations using different apostrophe characters (U+2019, U+02BC, U+02B9) and converts date separators from `-` to `/`. These changes are imperceptible to users but detectable by Anthropic's backend systems, creating a hidden communication channel.

## Root Cause

Claude Code implements prompt steganography through three detection mechanisms built into the date formatting function:

1. **Timezone Detection**: Checks if system timezone is `Asia/Shanghai` or `Asia/Urumqi`, triggering date separator changes (`-` to `/`)
2. **Domain Detection**: Compares `ANTHROPIC_BASE_URL` hostname against a base64+XOR-encoded domain list containing Chinese corporate domains, AI company domains, and proxy/reseller gateways
3. **Keyword Detection**: Scans hostname for AI lab keywords (deepseek, moonshot, minimax, xaminim, zhipu, bigmodel, baichuan, stepfun, 01ai, dashscope, volces)

The apostrophe character is selected based on condition combinations, allowing 4 different states to be encoded in a single request.

## Solution

To identify and audit these markers in Claude Code:

**Step 1: Extract and decode the domain/keyword lists from the binary**

```bash
# Find the base64-encoded strings in the Claude Code binary
strings /path/to/claude-code-binary | grep -E "^[A-Za-z0-9+/]{50,}={0,2}$" > potential_b64.txt

# Extract the obfuscated lists (XOR key is 91)
```

**Step 2: Decode the XOR-obfuscated domain list**

```javascript
const Kup = 91;

function Gla(encoded) {
  let bytes = Buffer.from(encoded, "base64");
  let out = "";
  for (let byte of bytes) {
    out += String.fromCharCode(byte ^ Kup);
  }
  return out.split(",");
}

// The encoded domain list from the binary
const encodedDomains = "...base64_string_here...";
const decodedDomains = Gla(encodedDomains);
console.log(decodedDomains);
```

**Step 3: Monitor the marker-setting function**

```javascript
// Patch the Vla function to log when markers are being applied
const originalVla = Vla;
Vla = function(date) {
  let marker = Zup();
  console.log("Marker detection:", {
    cnTZ: marker?.cnTZ,
    known: marker?.known,
    labKw: marker?.labKw,
    host: marker?.host
  });
  return originalVla(date);
};
```

**Step 4: Extract steganographic markers from API requests**

```python
import re
import unicodedata

def extract_markers(system_prompt_text):
    """Extract steganographic markers from system prompt"""
    # Find the date string and analyze apostrophe character
    date_match = re.search(r"Today(.)s date is", system_prompt_text)
    if date_match:
        apostrophe = date_match.group(1)
        char_code = ord(apostrophe)
        
        # Map Unicode values to conditions
        markers = {
            0x0027: "normal",           # '
            0x2019: "known_domain",     # '
            0x02BC: "lab_keyword",      # ʼ
            0x02B9: "known_lab"         # ʹ
        }
        
        condition = markers.get(char_code, "unknown")
        
        # Check date separator
        date_match = re.search(r"(\d{4})([-/])(\d{2})\2(\d{2})", system_prompt_text)
        if date_match and date_match.group(2) == "/":
            condition += "_cn_timezone"
        
        return condition
    return None
```

## Verification

**Command 1: Check your system timezone and base URL configuration**

```bash
echo "Current timezone: $(date +%Z)"
echo "ANTHROPIC_BASE_URL: ${ANTHROPIC_BASE_URL:-not set}"
```

Expected output:
```
Current timezone: UTC
ANTHROPIC_BASE_URL: not set
```

**Command 2: Inspect Claude Code binary for XOR-encoded strings**

```bash
strings /Applications/Claude\ Code.app/Contents/MacOS/claude-code | \
  grep -E "^[A-Za-z0-9+/]{100,}={0,2}$" | head -5
```

**Command 3: Verify date formatting markers in intercepted requests**

```bash
# Capture API request and extract date string
curl -i https://api.anthropic.com/v1/messages \
  -H "Content-Type: application/json" | \
  grep -o "Today.s date is [0-9/\-]*" | \
  od -c
```

Expected output (normal conditions):
```
T   o   d   a   y   '   s       d   a   t   e       i   s       2   0   2   6   -   0   6   -   3   0   .
```

Expected output (detected condition):
```
T   o   d   a   y  \u2019  s       d   a   t   e       i   s       2   0   2   6   /   0   6   /   3   0   .
```

## Notes

This steganographic technique is generalizable to other contexts:

- **Proxy Detection**: The domain list targets API gateway/proxy services used by unauthorized resellers, suggesting Anthropic wants to identify non-direct API usage
- **Regional Tracking**: Timezone and domain combinations create up to 4 bits of entropy per request, allowing backend systems to classify request origin and routing without explicit logging
- **Invisible Markers**: Unicode lookalike characters (U+2019, U+02BC, U+02B9) are nearly indistinguishable in monospace fonts, making manual detection difficult
- **Binary Obfuscation**: XOR encoding (key=91) with base64 is weak but sufficient to prevent casual inspection while remaining obfuscated in minified code
- **Broader Implications**: This pattern could be replicated in any client-side application to embed metadata in text sent to backend models without user awareness

## References

- **Source**: https://thereallo.dev/blog/claude-code-prompt-steganography
- **Hacker News Discussion**: https://news.ycombinator.com/item?id=40824855 (2445 points)
- **Decoded Domain List**: https://cdn.jsdelivr.net/gh/Thereallo1026/assets@main/assets/cc-domains.js