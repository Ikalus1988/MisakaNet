---
title: "A signature or manifest assembled before the last build ships stale, and the pipeline stays green"
domain: "ci"
tags:
  - "ci"
  - "release"
  - "signing"
  - "artifacts"
  - "build-order"
  - "updater"
  - "tauri"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "签名/清单组装完，流水线又跑了一次打包：主产物被换掉而签名没重生成，旧签名配新包，目录里零报错。"
trigger: "updater signature verification failure while all release files exist and the build is green"
verify: "Manifest signature equals the .sig file byte for byte and companion mtimes are not older than the installer; run one extra build after signing and both checks must fail."
source: "intake-3724"
provenance:
  issue: "#3724"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# A signature or manifest assembled before the last build ships stale, and the pipeline stays green

## Problem

A release pipeline produces a main artifact (installer / release package) together with companion
files: a `.sig` signature, a hash manifest, and a `latest.json` metadata file. When the
signing/manifest-assembly step runs and the pipeline then executes **one more packaging build**, the
main artifact is overwritten while the companion files are not regenerated. The result is an old
signature attached to a new package: verification fails at install or update time, even though the
build directory shows no error at all — every file is present, every size looks normal, and neither
the eye nor `ls` reveals anything wrong.

The reported occurrence, with its timestamps:

- the signing build at **17:43** produced Package A + Signature A + Manifest A;
- at **18:48** a `tauri build` embedded in the gate suite overwrote the package with Package B;
  Signature A and Manifest A stayed where they were;
- nothing failed until the next real-device update, which then failed signature verification.

The reported error text, verbatim:

```
updater signature verification failure / 旧签名配新包，验签必败但目录零报错
```

## Root Cause

**The order is unconstrained.** The release script performs "sign and assemble the manifest", while
the gate/test suite embeds a packaging build of its own. Nothing in the pipeline fixes which of the
two runs last, so whichever runs later wins the main artifact — and only the main artifact. A
packaging step rewrites the package and has no reason to know that a signature beside it exists, so
it silently discards the correspondence instead of failing.

**Every artifact-level check that does exist keeps passing.** Presence checks pass (the `.sig` is
there), size checks pass (it is the right size for a signature), timestamp checks pass if they only
ask "newer than the commit" or "not older than yesterday". What has actually happened is a **fork**:
two artifact sets that were each correct at a different moment, now shipped together. No single file
is wrong; the relationship between them is.

**The failure is externally invisible by construction.** The build is green because the last command
succeeded; the update is broken because the signature does not match the bytes it is supposed to
cover. The distance between the cause and the symptom is the length of a release cycle, so the
17:43→18:48 fork only surfaces on the next real-device update.

## Solution

**Pin "assemble signature/manifest" strictly after the last action that generates the main
artifact.** The safe shape is: all builds (including any packaging step a gate embeds) happen first,
then signing and manifest assembly happen once, at the tail, and nothing after them writes the
artifact.

**If the gate still re-packages, the tail must re-assemble the manifest.** The reporter's mechanism
is the packager's `--skip-build` mode — recompute the manifest over the current artifact without
rebuilding it. That restores the invariant after a late build instead of forbidding it.

**Write the ordering into the release script, not into human memory.** A rule that lives in a
runbook is satisfied until the first person who has not read the runbook runs the gate.

**Reject the release on either of two automatable criteria** (the reporter's):

1. **Signature identity.** The manifest file's embedded `signature` field equals the full content of
   the `.sig` file, byte for byte.
2. **Same-batch mtimes.** The main artifact and its companion signature/manifest share a batch: each
   companion's mtime is greater than or equal to the main artifact's, and all of them fall within the
   time window of a single build.

The checks themselves are reconstructed here from the criterion — the report states the criterion,
not a script — so the shapes below are minimal, not the project's own:

```bash
python3 - <<'PY'
import json, pathlib
sig = pathlib.Path('<artifact>.sig').read_text().strip()
manifest = json.loads(pathlib.Path('latest.json').read_text())
assert manifest['signature'] == sig, 'manifest signature does not match the .sig content'
PY
```

```bash
python3 - <<'PY'
import os, sys
main = os.path.getmtime('<artifact>')
for companion in ('<artifact>.sig', 'latest.json'):
    if os.path.getmtime(companion) < main:
        sys.exit(f'{companion} is older than the artifact it is supposed to cover')
PY
```

**The general statement, which is what makes this reusable:** for any "main artifact + companion
proof" combination — signature, hash, manifest — the companion proof must be generated strictly
later than the **last** generation of the main artifact. Otherwise the two silently fork, and nothing
outside the release can tell.

## Verification

The reporter's criterion: cross-check both items above, and then **force the failure on purpose** —
let the gate run one more packaging build after signature assembly and confirm that both checks
report. A check that has never failed is not known to work.

What does **not** count as verification: the pipeline being green, all files existing, sizes looking
normal, or the installer opening on the build machine. All four passed in the reported case while
signature verification was guaranteed to fail.

## Notes

- Evidence E1: reporter-reported from a real release, not reproduced in this repository. The release
  script, the packager version and the project name are not recorded in the intake — 报料者未给出，
  需复现确认 those if the same fork must be traced.
- The timestamps (17:43 for the signed build, 18:48 for the gate's `tauri build`) are the reporter's
  and are kept because they are the evidence that the two steps ran an hour apart.
- This is an ordering bug, not a signing bug. Changing the signing tool or the key changes nothing;
  moving the assembly step changes everything.
- The same shape reappears with hash manifests, SBOMs and provenance attestations attached to
  artifacts: any file that *describes* another file is invalid the moment the described file is
  regenerated.
