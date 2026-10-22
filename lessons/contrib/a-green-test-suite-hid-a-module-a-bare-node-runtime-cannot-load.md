---
domain: "nodejs"
title: "A green test suite hid a module that a bare Node runtime cannot load, because the bundler rewrites the JSON import"
tags:
  - "nodejs"
  - "esm"
  - "json"
  - "import-attributes"
  - "vitest"
  - "bundler"
  - "ci_gates"
  - "verification"
status: "published"
evidence_level: "E0"
created: "2026-10-22"
updated: "2026-10-22"
source: "intake-3750"
summary_plain: "Tests were green, the standalone script could not start: the test toolchain rewrites JSON imports, the runtime does not."
trigger: "ERR_IMPORT_ATTRIBUTE_MISSING; needs an import attribute of type json; vitest green but a bare node script crashes on load"
verify: "Run the script under bare node and the test suite as two separate commands; each must report its own exit 0, not inherit one from a chained script."
provenance:
  issue: "#3750"
  source: "MCP intake (claude-code), contributor-reported"
---

## Problem

A verification script was listed in the project's "verification tool index" and therefore counted as a
release gate. It had never once run. A module it imports could not be loaded by the runtime the
script itself is started with:

```
TypeError [ERR_IMPORT_ATTRIBUTE_MISSING]: Module ".../table1_robots.json" needs an import
attribute of "type: json"
```

The failure was at **load time**, before any of the script's logic ran, so the script had no output
to produce and no exit status to speak of.

The reason it stayed invisible is the shape of the checks around it. The unit tests for the same
module were **12/12 green**, and the test runner is the reason: vitest (like Vite) transforms JSON
imports itself, so `import data from "./x.json"` resolves inside the test run. The script, started
directly by `node`, has no transform layer in front of it, and Node's ESM loader requires the
import attribute:

```js
import data from './x.json' with { type: 'json' }
```

So the test suite was answering a different question from the one the release gate was asking. It
certified that the module loads *under the test toolchain*. The gate needed an answer about the
module loading *under the runtime that will actually execute it*.

## Root Cause

**The transform layer is a second runtime, and it is a quieter one.** A bundler or a test runner
rewrites the import before Node sees it, so the source text that reaches the loader is not the
source text in the repository. Every compatibility rule the loader enforces — import attributes,
extension resolution, `type` fields, top-level-await constraints — is a rule the transform layer
may have already satisfied on the code's behalf. The code that the tests exercised is the code
*after* the transform; the code the script loads is the code *before* it.

That direction of error is the dangerous one. A missing import attribute is not a wrong answer, it
is a crash before the first line of logic — and a green suite in front of it reads as
confirmation.

**Three runtimes, one gate.** The project had a test runner, a bundler for the application, and a
bare `node` invocation for the standalone script. The gate list named the script; the checks named
the test runner. Nothing in the pipeline said "run the third one", so the third one was never
exercised, and "the tests are green" stood in for a gate that had never reported.

**The listing made it look covered.** A verification-tool index says what *is* checked, not what
*has been run*. An entry in that index is a claim about intent; the script's exit status is the
evidence, and there was none.

## Solution

### Step 1: Make the import attribute explicit, everywhere

Not only where the error pointed. The sweep is the fix — a single site that fails is a sample of
the same pattern, and the pattern is what breaks:

```bash
# every JSON import in the tree, not only the one that threw
grep -rnE "from ['\"][^'\"]+\.json['\"]" --include=*.mjs --include=*.js --include=*.ts .
```

Each one becomes:

```js
import data from './table1_robots.json' with { type: 'json' }
```

### Step 2: Run the script the way the gate will run it, by itself

The script's own exit status, not a neighbour's:

```bash
node scripts/verify-tool.mjs      # → exit 0, and it prints the result
```

### Step 3: Run the test suite as a separate command

```bash
npx vitest run                    # → exit 0
```

Two separate commands, each read from its own exit code. A chained `npm test && node script` is
worse than either alone, because the first failure hides the second's absence.

### Step 4: Make the gate list say which runtime it means

An entry in a verification index should name the runtime and the command, not only the script:

```
verify-tool — node scripts/verify-tool.mjs — bare Node, no bundler, no test runner
```

An index entry that cannot be run as written is a wish, not a gate.

## Verification

Both gates, run separately, each read from its own exit code:

```bash
node scripts/verify-tool.mjs   # → exit 0, prints the verification report
npx vitest run                 # → exit 0, 12/12
```

And the negative case, because a gate that cannot go red is not a gate: remove the import
attribute from one import and confirm the bare-node run fails with
`ERR_IMPORT_ATTRIBUTE_MISSING` while the suite stays green. That pair — one red, one green, on the
same tree — is the evidence that the two gates are actually different gates.

## Notes

- **Distinct from `green-tests-hid-a-build-only-type-error`** (`lessons/contrib/`), which covers the
  same class — a green suite standing in for a gate it never ran — with the type-checker as the
  unwitnessed gate. Here the unwitnessed gate is a *bare Node runtime* and the hidden requirement
  is a language-level import attribute, which a bundler satisfies silently.
- The report this lesson comes from (intake #3750) was filed against a different project: its
  `table1_robots.json` and its verification-tool index are not part of this repository, and the
  failure could not be reproduced here. What is reproducible here is the sweep: this repository's
  only ESM JSON import is `workers/email-register/src/index.js`, which imports
  `../../../misaka-protocol.json` with no import attribute. That file is a Cloudflare Worker
  bundled by wrangler, so the bundler rewrites the import and the module never reaches a bare
  Node loader — the same shape, currently safe only because of the bundle. A rule that says "a
  JSON import carries the attribute" would keep it safe if that file is ever executed directly.
- The general form: **the test toolchain's transform layer is a second runtime**. A green suite
  proves the code runs in the transformed shape, not in the shape the real runtime loads. Anything
  that is also loaded by a runtime without that transform has to be smoked there.
