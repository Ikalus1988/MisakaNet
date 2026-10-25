---
title: "A green compile says nothing about reachability: the fix shipped in code no user ran"
domain: "testing"
tags:
  - "typescript"
  - "tsc"
  - "false-green"
  - "build-artifact"
  - "reachability"
  - "release"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "A clean compile only says the code compiles: the function may be uncalled and the new module may never be imported."
trigger: "tsc --noEmit passed and the release claimed both bugs fixed"
verify: "Call the loader production uses and the defect count must read 0/N; the built bundle must contain the component and its real slot keys."
source: "intake-2744"
provenance:
  issue: "#2744"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# A green compile says nothing about reachability: the fix shipped in code no user ran

## Problem

Two bugs survived a fully green compile and shipped in a release whose notes claimed both were
fixed. In both cases the developer changed a real function, watched `tsc --noEmit` pass, and
wrote a confident claim — and in both cases the code a user actually executes never reached the
change.

**Shape A — the fix landed in the wrong function.** A parser bug (a YAML block-scalar indicator
leaking into output) was fixed in `parse_frontmatter`. The analyzer's load path imports
`_parse_simple_frontmatter` — same file, different function. 12 of 251 records still had the
defect after release.

**Shape B — the module was never imported.** A new UI layer was written (slot declarations,
React components), compiled clean, and was not imported by the entry point. It never reached the
bundle. The shipped entry still registered `null` as the component and used slot keys that do not
exist in the platform's catalog. Searching the built file for the component name returned 0
occurrences:

```bash
grep -c 'MyComponent' dist/index.mjs    # 0
```

The reporter's one-line error statement:

```text
tsc --noEmit passed and the release claimed both bugs fixed; a user reproducing against the published package found both still present
```

The issue body is cut off inside the second command of its Solution block (`grep -c 'MyComponent'
dist/inde`), and the repository, component name and release tag were not given — they need to be
reproduced on the real project.

## Root Cause

`tsc --noEmit` answers exactly one question: *does this code compile?* It never asks:

- is it reachable from the entry point?
- does the code path a user hits actually execute it?
- does the built artifact contain it?

A file that compiles and is never imported is a false green. So is a fix verified by
unit-calling the function you changed while production calls a different one.

Both defects were eventually caught by someone reproducing against the **published package**,
not against the source tree.

## Solution

Verify the artefact and the load path, not the file you edited.

```bash
# Shape A: assert the fix on the path production uses
# (call the real entry point / loader, not the function you patched)
python3 -c "from pkg.evaluator import load_patterns; a=load_patterns('.'); \
  print(sum(1 for p in a.values() if p.get('field','').startswith('|')), '/', len(a))"
# -> 0/N is the claim; anything else means the fix missed the path

# Shape B: assert the code is in the built output
npm run build
grep -c 'MyComponent' dist/index.mjs
```

Also confirm that the entry point imports the module. A clean compile of a file nothing imports
proves nothing about the release.

## Verification

- **Shape A:** calling the real loader reports `0/251` defective records. It reported `12/251`
  after the release — which is the number the release notes should have been quoting.
- **Shape B:** the built bundle contains the component and the real slot keys — 3 and 6
  occurrences, versus 0 for the component name before the fix.
- **Both criteria must be observed on the loader or on the built file.** If the check you run
  reads the source file you edited, it is not the check this lesson is about, and it will go
  green on a release that ships nothing.
