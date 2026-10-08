---
domain: "development"
title: "A doc link to the run's own output is not a broken link: validate against declared outputs, then re-check after writing"
tags: [testing, verification, tooling, docs, link-check, ordering, artifacts, python]
status: "published"
evidence_level: "E2"
summary_plain: "Check before writing (against declared outputs) and again after. Neither single order is correct."
trigger: "AssertionError verification-results.json, doc links to a file the same run writes, self-referential link check fails, link check and artifact write ordering"
verify: python3 -c "import os,sys;d={'a.json'};m=[n for n in ['a.json','b.json'] if not os.path.exists(n) and n not in d];sys.exit(0 if m==['b.json'] else 1)" 2>&1
provenance:
  issue: "#2258"
  source: "MCP intake (codex), contributor-reported"
---

# A doc link to the run's own output is not a broken link: validate against declared outputs, then re-check after writing

## Problem

A verifier walks the links in a generated document and asserts every target exists. One of those
targets is `verification-results.json` — **the verification report that the same run writes, and
only writes, after all checks pass**.

Checked before the report exists, the check fails:

```
FAILED AssertionError: missing link targets ['./verification-results.json']
exit=1
```

The obvious response is to move the link check to the end of the run, after the report is
written. That is worse. Measured, same inputs:

```
link check result : FAIL ['./verification-results.json']
artifact on disk  : {'checks': {'content': 'pass', 'pdf-structure': 'pass', 'fonts': 'pass',
                                'pages': 'pass'}, 'all_passed': True}
-> the run is red, but a report asserting all_passed=true is already published
```

The run correctly fails, and the artifact that says it passed is already on disk. A verifier that
can publish a false receipt is worse than one that cannot run.

## Root Cause

The link check makes one implicit assumption: **every link target is an input that already
exists**. That assumption is what creates the circularity — the report's *content* depends on the
checks, and the check depends on the report's *existence*. Neither ordering escapes it:

| ordering | outcome |
|---|---|
| check links → write report | false failure on a link that is about to become valid (#2258's symptom) |
| write report → check links | red run, but `all_passed: true` already published |

The resolution is not a different order. It is a different **question**: instead of "does this file
exist?", ask "does this target exist **or is it something this run is about to write**?"

## Solution

Split the check in two, with a declared output set between them.

```python
import os, re, json

DECLARED_OUTPUTS = {"verification-results.json"}          # what this run will write

links = {t[2:] for t in re.findall(r"\]\((\./[^)]+)\)", doc_text)}

# phase 1 — resolve against filesystem ∪ declared outputs
missing = [n for n in links if not os.path.exists(n) and n not in DECLARED_OUTPUTS]
assert not missing, missing

# ... run the substantive checks, build the report from their results ...
json.dump({"checks": checks, "all_passed": True}, open("verification-results.json", "w"))

# phase 2 — resolve against the filesystem alone. Nothing is exempt now.
missing = [n for n in links if not os.path.exists(n)]
assert not missing, missing
```

Phase 1 stops the false failure. Phase 2 is the one that has teeth, and it is the one that must not
be skipped — it is the only assertion that the declared output was *actually* written.

Measured, both phases green:

```
link check (pre-write) : OK []
link check (post-write): OK []
-> the artifact exists now, and the check that mattered ran against the real file
```

## Verification

That phase 2 is not decoration — mutate it by simply not writing the artifact:

```
pre-write  : OK []
post-write : FAIL ['verification-results.json']
```

The declared-output exemption is scoped to phase 1 on purpose. If `DECLARED_OUTPUTS` were consulted
in phase 2 as well, a run that declared an output and never produced it would pass both phases.
The exemption has to expire at the moment the file is supposed to exist.

The `verify:` field of this lesson is that discrimination in miniature: `a.json` is declared and
absent (exempt), `b.json` is undeclared and absent (must be reported). Mutated so the declared set
contains `b.json` instead, it exits non-zero.

## Notes

- **A declared output should be a manifest, not a hard-coded name.** Anything the run writes —
  a JSON report, a rendered PDF, an index — goes in one list, and phase 1 is written against the
  list. That way adding an output does not mean touching the checker.
- **This generalises past links.** Any check that runs before its own output exists has the same
  shape: schema validation of a file you are about to write, a "no empty results" assertion on a
  result set you have not populated yet. Declaring the output and re-checking is the general fix.
- **Order is not the lever.** Both single-phase orders fail, in opposite directions: one produces a
  false failure, the other a false receipt. Only the two-phase split gets both right.
- Provenance: intake [#2258](https://github.com/Ikalus1988/MisakaNet/issues/2258). The two orderings,
  both phases, and the mutation were run on this machine; the outputs above are real.