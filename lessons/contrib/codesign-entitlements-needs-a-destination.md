---
title: "codesign --entitlements prints a Usage banner unless you give it a destination"
domain: development
tags: [macos, codesign, entitlements, xml, plist, security, signing, cli]
status: published
evidence_level: E3
summary_plain: "codesign -d --entitlements needs '-' or a file path; bare --entitlements /path prints Usage, not entitlements"
trigger: "codesign entitlements Usage banner xml format machine readable plist signing"
verify: "codesign -d --entitlements - --xml /System/Applications/Calculator.app | head -c 5 shows '<?xml'; bare form prints 'Usage: codesign'"
---

## Problem

`codesign --display --entitlements /path/to/binary` prints **nothing about entitlements** — it prints the `codesign` Usage banner and exits 0. There is no error message pointing at the real problem, so it reads like a permissions or signing issue rather than a syntax one.

```
$ codesign --display --entitlements /bin/ls
Usage: codesign -s identity [-fv*] [-o flags] [-r reqs] [-i ident] path ... # sign
       codesign -v [-v*] [-R=<req string>|-R <req file>] path|[+]pid ...   # verify
       codesign -d [options] path ...                                      # display contents
```

This also happens on a fully signed app, so "the binary must not be signed" is the wrong first guess:

```
$ codesign -d --entitlements /System/Applications/Calculator.app
Usage: codesign -s identity ...
```

## Root Cause

`--entitlements` requires a **destination argument**. It is not a boolean flag:

- `--entitlements -` → write to stdout
- `--entitlements /out.plist` → write to a file

Without a destination, argument parsing fails and `codesign` falls through to its generic Usage banner — which is why the symptom looks unrelated to the flag you typed.

Once you supply a destination, a second switch picks the encoding:

| Command | Output |
|---|---|
| `codesign -d --entitlements - <path>` | **human-readable** `[Dict]` / `[Key]` / `[Value]` |
| `codesign -d --entitlements - --xml <path>` | **plist XML** (parseable by `plutil`/`xmllint`) |
| `codesign -d --entitlements out.plist <path>` | XML written to `out.plist` |
| `codesign -d --entitlements :- <path>` | XML + deprecation warning — see below |

Note the destination is a separate token **before** the path. Both `--display` and `-d` work as the display verb.

## Solution

Machine-readable XML to stdout:

```bash
codesign -d --entitlements - --xml /path/to/binary
```

Human-readable (the form people usually want for eyeballing):

```bash
codesign -d --entitlements - /path/to/binary
```

Useful variants:

```bash
# Pretty-print via plutil
codesign -d --entitlements - --xml /path/to/binary | plutil -p -

# Save for CI diffing
codesign -d --entitlements - --xml /path/to/binary > entitlements.plist

# Does this one entitlement exist?
codesign -d --entitlements - --xml /path/to/binary | grep -c "com.apple.security.app-sandbox"

# Compare two binaries
diff <(codesign -d --entitlements - --xml /AppA) <(codesign -d --entitlements - --xml /AppB)
```

CI gate sketch:

```bash
#!/bin/bash
EXPECTED=("com.apple.security.app-sandbox" "com.apple.security.files.user-selected.read-write")
XML=$(codesign -d --entitlements - --xml "$1" 2>/dev/null)
for ent in "${EXPECTED[@]}"; do
    echo "$XML" | grep -q "$ent" || { echo "MISSING: $ent"; exit 1; }
done
echo "All expected entitlements present"
```

## The deprecated `:-` syntax

`codesign -d --entitlements :- <path>` is **not** a human-readable mode — it emits the same XML as `--xml`, and warns:

```
warning: Specifying ':' in the path is deprecated and will not work in a future release
```

Treat `:-` as a legacy spelling of the XML destination and move to `--entitlements - --xml`.

## Gotcha: a binary with no entitlements

On a binary that has none (e.g. `/bin/ls`), the human-readable form prints only the `Executable=...` line and `--xml` prints nothing. Empty output there means "no entitlements", not "wrong syntax" — don't add flags chasing it.

## Verification

All commands below were run on macOS 26.5.2 (Build 25F84), arm64.

```bash
# Bare form: Usage banner (this is the bug being documented)
codesign --display --entitlements /System/Applications/Calculator.app | head -1
# -> Usage: codesign -s identity [-fv*] ...

# Human-readable via '-'
codesign -d --entitlements - /System/Applications/Calculator.app | head -3
# -> Executable=/System/.../Calculator
# -> [Dict]
# ->         [Key] com.apple.private.coreservices.canmaplsdatabase

# XML via '- --xml'
codesign -d --entitlements - --xml /System/Applications/Calculator.app | head -c 5
# -> <?xml

# Deprecated form: XML + warning
codesign -d --entitlements :- /System/Applications/Calculator.app 2>&1 | head -2
# -> Executable=...
# -> warning: Specifying ':' in the path is deprecated ...
```
