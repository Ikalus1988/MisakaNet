---
{
  "title": "Claude Code Steganographically Marks Requests Based on API Base URL and Timezone",
  "domain": "security",
  "tags": ["steganography", "prompt-injection", "api-security", "reverse-engineering", "claude-code"],
  "language": "en",
  "status": "published",
  "source": "https://thereallo.dev/blog/claude-code-prompt-steganography",
  "created": "2026-07-27",
  "confidence": "0.85"
}
---

## Problem

A developer inspecting the Claude Code binary (version 2.1.196) for privacy reasons discovered that the application silently embeds hidden markers in system prompts. Specifically, when Claude Code constructs the system context for API requests, it modifies the date string sent to the model based on:

1. The `ANTHROPIC_BASE_URL` environment variable (detecting non-official API endpoints)
2. The system timezone (checking for Asia/Shanghai or Asia/Urumqi)

For example, a user running Claude Code from China with a proxy API endpoint would have their date string transformed from `Today's date is 2026-06-30.` to `Today´s date is 2026/06/30.` (notice the changed apostrophe and date separator). These visual changes are imperceptible in most monospace fonts, embedding metadata about the client's network configuration directly into the model's system context.

## Root Cause

The Claude Code binary contains a steganographic encoding function that:

1. Detects API base URLs via `ANTHROPIC_BASE_URL` environment variable
2. Extracts the hostname and checks it against XOR-obfuscated domain/keyword lists
3. Checks system timezone against hardcoded values (Asia/Shanghai, Asia/Urumqi)
4. Uses the detection results to select different Unicode apostrophe characters (U+0027, U+2019, U+02BC, U+02B9)
5. Conditionally replaces date separator `-` with `/` for specific timezones

The obfuscation lists are stored as base64-encoded strings XOR-decoded with key `91`, containing 70+ proxy domains, AI company domains, and Chinese corporate domains. This technique allows Anthropic to embed metadata about request origin in the model context without visible indication to users or the model.

## Solution

To detect and verify steganographic markers in Claude Code:

1. **Decode the obfuscated domain/keyword lists**

```javascript
const Kup = 91;

function decodeList(encoded) {
  let bytes = Buffer.from(encoded, "base64");
  let out = "";
  for (let byte of bytes) {
    out += String.fromCharCode(byte ^ Kup);
  }
  return out.split(",");
}

// Example: decode the keyword list
const keywordList = decodeList(/* base64 encoded string from binary */);
console.log(keywordList);
// Output: ["deepseek", "moonshot", "minimax", "xaminim", "zhipu", "bigmodel", ...]
```

2. **Extract and analyze the marker function from Claude Code binary**

```bash
# Decompile the Claude Code binary to identify the Zup() and edp() functions
# On macOS:
otool -L /Applications/Claude\ Code.app/Contents/MacOS/Claude\ Code

# On Linux:
ldd /opt/claude-code/claude-code

# Extract JavaScript bundle:
strings /Applications/Claude\ Code.app/Contents/MacOS/Claude\ Code | grep -A 5 "function Zup"
```

3. **Monitor environment variables and system context**

```bash
# Check your current ANTHROPIC_BASE_URL setting
echo $ANTHROPIC_BASE_URL

# Check your system timezone
timedatectl | grep "Time zone"
# or
date +%Z

# Monitor system prompts being sent (requires proxy/debugging)
export http_proxy=http://localhost:8080
export https_proxy=http://localhost:8080
# Then use mitmproxy to capture Claude Code requests
```

4. **Detect steganographic markers in captured requests**

```python
import json
import re

def check_apostrophe_markers(text):
    """Detect Unicode apostrophe variations used for steganography"""
    unicode_markers = {
        '\u0027': 'normal',       # Regular apostrophe
        '\u2019': 'known_domain', # Right single quotation mark
        '\u02BC': 'lab_keyword',  # Modifier letter apostrophe
        '\u02B9': 'known_and_lab' # Modifier letter prime
    }
    
    # Extract apostrophe from "Today's date is..."
    match = re.search(r"Today([\u0027\u2019\u02BC\u02B9])s date", text)
    if match:
        apostrophe = match.group(1)
        return unicode_markers.get(apostrophe, 'unknown')
    return None

def check_date_format(text):
    """Detect date separator variation"""
    if re.search(r'\d{4}/\d{2}/\d{2}', text):
        return 'slash_separator (Asia timezone)'
    elif re.search(r'\d{4}-\d{2}-\d{2}', text):
        return 'dash_separator (normal)'
    return None

# Test on captured system context
test_context = 'Today\u2019s date is 2026-06-30.'
print(f"Apostrophe type: {check_apostrophe_markers(test_context)}")
print(f"Date format: {check_date_format(test_context)}")
```

5. **Audit the marker generation logic**

```javascript
// Reconstructed marker detection function
function auditMarkerGeneration() {
  const baseUrl = process.env.ANTHROPIC_BASE_URL;
  const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  
  // Simulate Zup() function
  const marker = {
    known: false,    // Matches known domain list
    labKw: false,    // Matches lab keyword list
    cnTZ: ['Asia/Shanghai', 'Asia/Urumqi'].includes(timezone),
    host: baseUrl ? new URL(baseUrl).hostname : null
  };
  
  // Simulate edp() function to get apostrophe
  const apostropheMap = {
    'false_false': '\u0027',  // Normal
    'true_false': '\u2019',   // Known domain
    'false_true': '\u02BC',   // Lab keyword
    'true_true': '\u02B9'     // Both
  };
  
  const apostropheKey = `${marker.known}_${marker.labKw}`;
  const apostrophe = apostropheMap[apostropheKey];
  
  console.log('Marker Detection:', marker);
  console.log('Selected Apostrophe:', apostrophe.charCodeAt(0).toString(16));
  
  return marker;
}

auditMarkerGeneration();
```

## Verification

Execute these commands to confirm steganographic marking:

```bash
# 1. Set up a test environment with proxy URL
export ANTHROPIC_BASE_URL="http://claude-code-hub.app"
export TZ="Asia/Shanghai"

# 2. Launch Claude Code and capture the system context
# Using mitmproxy to intercept HTTPS traffic:
mitmproxy -p 8080

# 3. In another terminal, configure Claude Code to use proxy
export http_proxy=http://localhost:8080
export https_proxy=http://localhost:8080

# 4. Trigger Claude Code to make a request and capture it
# The captured request should show modified markers

# 5. Extract and analyze the date string from captured request
# Expected with proxy + Shanghai timezone:
# - Date format: 2026/06/30 (slashes instead of dashes)
# - Apostrophe: U+02B9 (modifier letter prime)
# Visual in normal font: "Today´s date is 2026/06/30."

# 6. Verify by decoding the base64 domain list
python3 << 'EOF'
import base64

# Base64 encoded domain list (obfuscated)
encoded = "..." # from binary

bytes_data = base64.b64decode(encoded)
decoded = ""
for byte in bytes_data:
    decoded += chr(byte ^ 91)

print("Decoded domains:")
print(decoded.split(",")[:5])
# Should show: ['cn', 'baidu.com', 'alibaba-inc.com', ...]
EOF

# Expected output:
# Decoded domains:
# ['cn', 'baidu.com', 'alibaba-inc.com', 'alipay.com', 'antgroup-inc.cn']
```

## Notes

**Steganography in Production Systems**: This technique extends beyond Claude Code. Steganographic markers embedded in system contexts can be used for:

1. **Request Origin Tracking**: Identifying API resellers, proxy usage, and unauthorized endpoints without explicit logging
2. **Regional Routing**: Silently routing requests differently based on detected timezone/domain
3. **Compliance Obfuscation**: Marking requests that should receive different compliance filtering or rate limiting without user awareness
4. **Supply Chain Watermarking**: Embedding version/source information directly in model context for attribution

**Detection Methods**: Organizations using Claude Code or similar tools should:

1. Monitor `ANTHROPIC_BASE_URL` overrides and proxy configurations
2. Analyze system prompts sent to models for Unicode variation anomalies
3. Extract and decode any obfuscated lists in binaries
4. Compare apostrophe characters (byte-level) in captured prompts across different network environments

**Implications**: Users on Chinese networks, behind proxies, or using alternative API endpoints have their network configuration silently exposed in every request's system context, raising privacy concerns about what metadata is being collected and how it's used downstream.

## References

- Source: https://thereallo.dev/blog/claude-code-prompt-steganography
- Hacker News Discussion: https://news.ycombinator.com/item?id=<story_id> (2445 points)
- Full decoded domain list: https://cdn.jsdelivr.net/gh/Thereallo1026/assets@main/assets/cc-domains.js
- Claude Code binary signature verification: Use `codesign -vvv` on macOS or `openssl` on Linux