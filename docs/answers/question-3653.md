---
issue: 3653
kind: question
status: answered
answered_at: "2026-10-31"
evidence_level: "E0 — reasoning from the public API surface; NOT reproduced in this repository"
question: "What primary evidence establishes version compatibility for SIP-enabled native modules across macOS major releases?"
retrieval_context: "measured through the production path (BM25 + IDF-weighted relevance floor) this intake returns no_match"
provenance:
  issue: "#3653"
  source: "author of this answer, from Apple-documented tooling; no macOS host was available to run the commands"
  related_lesson: "lessons/contrib/a-hit-is-not-evidence-of-relevance.md"
---

# #3653 — What primary evidence establishes version compatibility for SIP-enabled native modules across macOS major releases?

## Why this answer exists instead of a link

The production retrieval path (BM25 plus the IDF-weighted relevance floor) returns `no_match` for this
question. That is the honest result, not a bug: per `lessons/contrib/a-hit-is-not-evidence-of-relevance.md`,
`no_match` is a first-class answer and the shared vocabulary in this intake (`evidence`, `primary`,
`private`) is generic enough that any hit would have been a wrong hit. So there is no lesson to link to,
and the answer has to be written here.

**Read the whole answer as reasoning, not as a reproduction.** I have no macOS host in this environment and
did not execute any of the commands below. Everything I state as a fact about *what the tooling reports* is
taken from Apple's documented tooling behaviour; everything I state about *this specific module* would need
to be observed. The parts I could not check are listed under "What I did not verify".

## Step 0 — separate the two gates, because SIP is not the version gate

The question joins two constraints that are enforced by different mechanisms and fail with different
errors. Confusing them is the usual reason a module "works in Terminal but not in the app":

| gate | enforced by | artifact that answers it |
|---|---|---|
| **Version** — can this image run on this OS at all? | dyld, at load time | the Mach-O build-version load command: `minos` and `sdk` |
| **Signature / library validation** — may *this* process load *this* image? | the kernel + `amfi` / `libsecinit`, with the hardened runtime and entitlements | `codesign -dvvv --entitlements :-` on both the process and the dylib |

SIP itself protects filesystem locations (and injects library validation into system-launched processes).
It does not decide whether macOS 14 can load a module built for macOS 11 — dyld decides that, and it
decides it before SIP is relevant. Conversely a module with a perfectly fine `minos` is still refused by
library validation if it is signed by a different Team ID. **Both checks must pass; each has its own
primary evidence.**

## 1. The version gate: primary evidence is `minos` vs the host, read off the image

Primary here means "read out of the artifact itself", not "read out of a release-notes page".

```bash
# the build-version load command (LC_BUILD_VERSION, macOS 10.14+ toolchains)
vtool -show-build /path/to/Module.framework/Versions/A/Module
otool -l /path/to/Module | grep -A 5 LC_BUILD_VERSION

# pre-10.14 toolchains carry LC_VERSION_MIN_MACOSX instead
# - in that case the same two numbers appear as `version` and `sdk`
```

The output is the pair that answers the question:

- **`minos`** — the deployment floor the module declares. This is a **floor, not a ceiling**. A module with
  `minos 11.0` is *expected* to load on 12, 13, 14; a module with `minos 15.0` must be refused on 14.
  "Version compatibility across major releases" is therefore a one-directional question: for each host you
  care about, `minos <= host` must hold. There is no separate upper bound to check.
- **`sdk`** — the SDK the module was built against. This is provenance, not a compatibility bound, but it
  predicts the two things that actually break across majors: symbols that were weak-linked at build time,
  and behaviour that changed under a stable symbol.

Host side, for the comparison to be meaningful:

```bash
sw_vers -productVersion      # marketing version, e.g. 14.6
sw_vers -buildVersion        # e.g. 23G93
sysctl -n kern.osrelease     # Darwin version, e.g. 23.6.0 — dyld errors quote this, not sw_vers
```

Note the mismatch in vocabulary: Mach-O `minos` is a *product* version (`11.0`), while many dyld failure
messages quote the Darwin release. Converting between them (`kern.osversion`) is where people misread a
version failure as a signature failure.

**`minos` alone is not sufficient**, because the module also has to resolve its dependents at load:

```bash
otool -L /path/to/Module          # every LC_LOAD_DYLIB / LC_LOAD_WEAK_DYLIB
```

A dylib with a correct `minos` that strong-links a framework introduced in a later major release fails at
load on the older host. The primary evidence for *that* is the dependent's own `minos`, plus whether the
link was weak:

```bash
nm -m /path/to/Module | grep -i weak      # weak imports are the ones allowed to be absent
```

`API_AVAILABLE` / `NS_AVAILABLE` in the source compile down to exactly these weak imports plus runtime
`@available` guards; if the guard is missing, the module loads and then crashes on first message send,
which is a *different* failure from a load-time refusal and should be reported as such.

## 2. The signature gate: primary evidence is the two `codesign` dumps, compared

```bash
codesign -dvvv --entitlements :- /Applications/App.app        # the loading process
codesign -dvvv --entitlements :- /path/to/Module.dylib        # the loaded image
```

What to compare, and why each line matters:

- **`TeamIdentifier`** — under library validation a process may load only images signed by the *same* Team
  ID or by Apple. Same-team is the normal way a third-party dylib loads at all. Different team, no
  entitlement, no load.
- **`flags=0x10000(runtime)`** — the hardened runtime. It is what turns library validation on for a
  non-system process. A dylib that loads into a non-hardened build of the same app and fails in the
  hardened build is a signature-gate failure, not a version failure.
- **`com.apple.security.cs.disable-library-validation`** — the documented escape hatch, and the thing that
  should be *absent* in a shipping build. If it is present, the compatibility statement you are making is
  "we disabled the check", which is not the same claim as "the module is compatible".

Failure strings that identify this gate, and should be quoted verbatim when reporting:

- `code signature invalid`
- `not valid for use in process: library load disallowed by system policy`
- `mapped file has no Team ID and is not a platform binary`
- `have different Team IDs`

## 3. The load-time verdict is the primary evidence; documentation is secondary

If the module loads, under a named host build, in a process whose signature and entitlements you have
pasted, then that is evidence. A doc claim that "version X is supported" is not — it is a claim about a
matrix someone else measured. The cheapest way to capture the verdict:

```bash
DYLD_PRINT_LIBRARIES=1 /Applications/App.app/Contents/MacOS/App 2>&1 | grep -i module
log stream --predicate 'process == "App"' --level debug   # in another shell, for the launch
```

Capture, for a single launch: the host `sw_vers`/`kern.osrelease`, the `minos`/`sdk` of the module,
`codesign -dvvv` of both binaries, and the loader's own message. That bundle is the primary evidence; any
one of them alone is not.

## What I did not verify (labelled as such)

- I did not run any command above. There is no macOS host in this environment; this repository's CI does
  not include one.
- I do not know this module's `minos`, `sdk`, Team ID, or whether it carries
  `disable-library-validation`. Those four values decide the answer, and I have not seen them.
- I have not reproduced a cross-major-version failure for this module. The *shape* of the failure above is
  from the documented tooling; the *occurrence* is unconfirmed.
- Whether macOS major-version compatibility is officially supported for this module is a vendor statement I
  cannot make. What I can state is what the artifact declares and what the loader does with it.

## Checkable criteria

1. `vtool -show-build <module>` prints `minos` and `sdk`. If it prints nothing, the image has
   `LC_VERSION_MIN_MACOSX` (older toolchain) — read `version`/`sdk` from `otool -l` instead, and say so.
2. `minos <= sw_vers -productVersion` on the host under test, and every strong-linked dependent satisfies
   the same condition (or is linked weak). If not, the failure is a version failure and the error text will
   quote the Darwin release.
3. `codesign -dvvv` of process and module report the same `TeamIdentifier`, or the process carries
   `com.apple.security.cs.disable-library-validation`. If not, the failure is a signature failure regardless
   of version.
4. A single launch log contains the host build, both `codesign` dumps, and the loader's verdict. If any of
   the four is missing, the compatibility claim is not yet established.

If someone with a Mac can paste items 1–4 for one host, this answer becomes E1 and can be promoted into a
lesson.
