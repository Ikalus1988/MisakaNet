---
title: "codesign --verify -R reads a bare requirement string as a filename - prefix it with '='"
domain: "security"
tags:
  - "codesign"
  - "macos"
  - "code-signing"
  - "requirement"
  - "verification"
  - "cli"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "codesign -R 后面直接写要求字符串会被当成文件名去读，报 invalid requirement specification；前面加个 = 才是字面要求。"
trigger: "codesign invalid requirement specification --verify -R No such file or directory literal requirement"
verify: "codesign --verify -R '=<requirement>' <app> accepts a known-good signed app and rejects one whose metadata the requirement forbids."
source: "intake-3381"
provenance:
  issue: "#3381"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# codesign --verify -R reads a bare requirement string as a filename - prefix it with '='

## Problem

Verifying a macOS app against a literal requirement string failed before any signature check ran:

```
$ codesign --verify -R '<literal requirement>' <app>
... No such file or directory
... invalid requirement specification
```

The command was shaped like the documentation examples, but `codesign` treated the requirement text
as a file name: the file could not be opened ("No such file or directory"), and its content could not
be parsed as a requirement specification ("invalid requirement specification"). Nothing was wrong with
the app's signature.

## Root Cause

`-R` / `--requirements` accepts two shapes: a **path to a file** containing a requirement
specification, or a **literal specification** signalled by a leading `=`. Without the `=`, an inline
string is parsed as a path, which produces exactly the two messages above — one from the failed read,
one from the failed parse — and neither names the shape that was expected.

The reporter confirmed the literal form against the locally installed `codesign` man page, section
SPECIFYING REQUIREMENTS.

## Solution

Pass an argument that begins with `=` followed by the requirement, and quote the whole thing so the
shell keeps the requirement language's `=>` and spaces intact:

```bash
codesign --verify -R '=<requirement expression>' /path/to/App.app
```

### Step 1 — decide file or literal

If the requirement lives in a file, pass that path with no `=`. If it is inline text, prefix it with
`=`. The two forms are not interchangeable and the error text does not tell you which one was
assumed.

### Step 2 — single-quote the argument

The requirement language uses `=>` and spaces; unquoted, the shell rewrites them before `codesign`
ever sees the argument, which turns a quoting problem into what looks like a parsing problem.

### Step 3 — separate a parse failure from an unsatisfied requirement

"invalid requirement specification" or a usage banner means the argument was not understood at all;
a nonzero exit that complains about the signature or the requirement satisfaction means it was
understood and not met. Read the two apart before touching the app's signature.

## Verification

Reported: the corrected argv accepted a known-good signed and notarized app, and rejected an existing
app carrying disallowed Finder metadata — a positive and a negative control on the same requirement.
No code signing was changed and no app was launched.

Not re-run in this repository. The actual requirement expression, the app paths and the macOS version
are absent from the report — 报料者未给出，需复现确认.
