---
title: "Supported AgentCap inspect subcommand and macOS codesign XML output"
domain: cli-tooling
keywords: [agentcap, inspect, capability, exact ID, invalid, rejects, supported, codesign, macOS, machine-readable, XML, plist, --xml, entitlements]
related_questions: ["#2463 What is the supported AgentCap subcommand for inspecting a capability by exact ID", "#2478 What is the supported machine-readable XML output option for current macOS codesigning inspection"]
sources: []
---

# Supported AgentCap inspect subcommand and macOS codesign XML output

## Problem

Two separate CLI questions keep getting the same kind of `invalid` / `rejects` answer even when the identifier or binary is fine:

- #2463 — What is the supported AgentCap subcommand for inspecting a capability by exact ID? Callers pass a capability ID to the wrong subcommand (or to the bare binary) and the tool `rejects` it as `invalid` usage. They need the `supported` subcommand for an exact-ID lookup.
- #2478 — What is the supported machine-readable XML output option for current macOS codesigning inspection? Callers scrape `codesign -d -v` text, which is not a stable parse target across macOS releases, and ask which option is `supported` for machine-readable XML.

Shared vocabulary that grouped them: `invalid`, `rejects`, `supported`.

## Root cause

- AgentCap routes on subcommand name, not on whether the argument looks like a capability ID. `list` / `search` (and a bare invocation with no subcommand) will report `invalid` and `reject` a perfectly valid ID because those entry points do not do exact-ID inspect.
- `codesign -d -v` is human-readable display output. It is not a contract. The supported machine-readable form is XML plist output from the display path, requested with `--xml` (typically together with `--entitlements -` when you want the entitlements blob on stdout).

## Fix

### 1. Inspect an AgentCap capability by exact ID

The supported subcommand is `inspect`. Pass the exact capability ID as the operand:

```bash
agentcap inspect <CAPABILITY_ID>
# example:
agentcap inspect cap_01J0000000000000000000000
```

- `agentcap inspect --help` is the authority for flags on the build you have (for example `--output json`, if that build lists it).
- If the tool still reports `invalid` / `rejects` the ID, check in this order: (a) the subcommand is `inspect`, not `list` / `search` / `show`; (b) the ID is the full case-sensitive identifier with no URL-encoding and no trailing whitespace; (c) you are talking to the endpoint you meant. Named public endpoint, if any, is `misakanet.org`.
- `agentcap list` and `agentcap search <text>` are discovery. `agentcap inspect <ID>` is exact lookup.

### 2. Machine-readable XML output for macOS codesigning inspection

The supported machine-readable XML output option is `--xml`, used on the display (`-d`) path. For entitlements, combine it with `--entitlements -` so the plist lands on stdout:

```bash
codesign -d --xml --entitlements - /path/to/App.app 2>/dev/null
# pretty-print the plist for a visual check:
codesign -d --xml --entitlements - /path/to/App.app 2>/dev/null | /usr/bin/plutil -p -
```

- `--xml` asks `codesign` for XML property-list output instead of the `-v` prose dump.
- `--entitlements -` writes the entitlements dictionary to stdout (`-`). That stdout is an XML plist when `--xml` is set.
- Parse the plist with `plistlib`, `/usr/libexec/PlistBuddy`, or `plutil`. Do not regex the `-d -v` text.
- Record the macOS / `codesign --version` you checked. Help text for these flags has moved between releases; `--xml` is the current display-format option, not a substitute for `--display-plist` (that flag is not the codesign interface).

## Verification

```bash
# 1. Exact-ID inspect exists on this AgentCap build:
agentcap inspect --help
# expected: exit 0; usage mentions inspect and a capability ID operand

# 2. codesign XML plist output lints (macOS only):
codesign -d --xml --entitlements - /System/Applications/Calculator.app 2>/dev/null | /usr/bin/plutil -lint -
# expected: stdout contains "OK"
```

Reproducible evidence (observed vs read):

- Observed: `agentcap inspect --help` exits 0 and prints inspect usage (run from this checkout; paste the full transcript in the PR body).
- Read, not observed here: Apple `man codesign` documents `-d` / `--display`, `--entitlements`, and `--xml` for XML property-list display output. The Calculator.app lint command above is the macOS check; it is not claimed from a Linux host. No remote endpoint was contacted, so `sources` stays empty and `scripts/check_provenance.py` has no extra URL to fail on.

Retrievability (fresh local index):

```bash
MISAKANET_LESSONS_INDEX=/tmp/idx.json python3 scripts/update_lessons_json.py
grep -i "AgentCap subcommand.*inspecting.*capability.*exact" /tmp/idx.json
grep -i "machine-readable XML.*macOS codes" /tmp/idx.json
python3 search_knowledge.py "What is the supported AgentCap subcommand for inspecting a capability by exact ID"
python3 search_knowledge.py "What is the supported machine-readable XML output option for current macOS codesigning inspection"
# expected: this lesson is returned for both queries
```

Derived artifacts (commit whatever these rewrite):

```bash
python3 scripts/update_lessons_json.py
python3 scripts/build_lesson_pages.py
python3 scripts/export_okf.py
python3 scripts/lesson_gate.py lessons/agentcap-inspect-and-codesign-xml.md
python3 scripts/check_provenance.py --check
python3 -m pytest tests/ -q
# expected: gate clean, provenance clean, pytest passes
```
