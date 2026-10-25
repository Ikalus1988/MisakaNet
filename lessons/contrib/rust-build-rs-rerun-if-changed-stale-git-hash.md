---
domain: "development"
title: "build.rs that only watches itself keeps serving a stale GIT_HASH after every commit"
tags:
  - "rust"
  - "cargo"
  - "build-rs"
  - "rerun-if-changed"
  - "git-hash"
  - "version-metadata"
  - "vergen"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
source: "intake-3523"
summary_plain: "build.rs 只声明监视 build.rs 自己，提交后 Cargo 不重跑它，编进二进制的 GIT_HASH 就永远停在旧提交上。"
trigger: "cargo:rerun-if-changed=build.rs only, GIT_HASH stale after commit, /api/version hasNew always true"
verify: "After one new commit and a rebuild, /api/version GIT_HASH equals `git rev-parse HEAD` and BUILD_TS is the new build time; the client's version check stops reporting hasNew."
provenance:
  issue: "#3523"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# build.rs that only watches itself keeps serving a stale GIT_HASH after every commit

## Problem

A Rust service injects version metadata at build time from `build.rs`: a `GIT_HASH` and a `BUILD_TS`,
compiled in and served at `/api/version`. The build script declared exactly one dependency:

```rust
println!("cargo:rerun-if-changed=build.rs");
```

Symptoms, as reported:

- `/api/version` returns a `GIT_HASH` and `BUILD_TS` that do not match the version actually deployed;
- the front end polls `/api/version`, compares it to what it is running, and gets `hasNew = true` on
  every poll, so the "a new version is available" banner is permanently lit and cannot be cleared.

No functional failure — nothing crashes, nothing 500s. The service just keeps telling every user, with
total confidence, that they are out of date. Users reload over and over for nothing.

**How it was pinned down:** the reporter checked the real hash embedded in the running binary through
its symbol table / DWARF, not through the HTTP endpoint. The binary's own metadata was the stale value,
so the deployed artifact really was built from a different commit — version skew was an illusion
created by the reporting path. That rule-out matters: the first hypothesis was "the client is newest
and the server is genuinely behind".

## Root Cause

**Cargo's default watch set is everything in the package; the first `rerun-if-changed` you emit
replaces it.** From the Cargo build-script documentation: if a build script emits *any*
`rerun-if-changed` instruction, Cargo uses **only** those paths to decide whether to re-run it, instead
of the default "any file in the package changed".

So this single line did not *add* a dependency on `build.rs` — `build.rs` was already tracked, Cargo
re-runs a build script whenever the script itself changes. It **narrowed** the watch set to one file
that could never fire an extra time. Everything else in the package, `.git/` included, stopped
invalidating the build script.

The chain is then mechanical:

| step | state |
|---|---|
| `git commit` moves HEAD | repository changed |
| `git rev-parse HEAD` inside the package dir has a new answer | source of truth moved |
| no watched path changed, so `build.rs` is not re-run | old `env!("GIT_HASH")` value is reused |
| the crate is recompiled from cached build-script output | binary embeds the **old** hash |
| `/api/version` serves the old hash | client concludes it is newer → `hasNew` forever |

The build did not fail; it succeeded and lied. That is the signature of a stale build-script output: a
green build, a deployed binary, and metadata from a previous commit.

**Why the hash looked plausible rather than obviously wrong:** it was the hash of a commit that really
existed and had really been built. Only comparing it against `git rev-parse HEAD` for the deployed
commit — or against the hash embedded in the binary — reveals the gap.

## Solution

### Step 1: make the metadata's source a watched input

The version comes from git, so the watched paths must be the files git writes:

```rust
fn main() {
    // HEAD is a small file; on a branch it points at refs/heads/<branch>,
    // whose content is what a commit actually changes.
    println!("cargo:rerun-if-changed=.git/HEAD");
    println!("cargo:rerun-if-changed=.git/packed-refs");

    let head_ref = std::fs::read_to_string(".git/HEAD").unwrap_or_default();
    if let Some(target) = head_ref.strip_prefix("ref: ") {
        println!("cargo:rerun-if-changed=.git/{}", target.trim());
    }

    // …then compute GIT_HASH / BUILD_TS and emit env!() values as before
}
```

Watching `.git/HEAD` alone is **not** sufficient, and this is the trap that outlives the first fix: on
a branch, a commit does not rewrite `.git/HEAD` — its content stays `ref: refs/heads/<branch>`. What
changes is the branch ref file. After `git gc` those refs may be packed into `.git/packed-refs`
instead, which is why the packed file is listed as well. And a `git checkout` that moves HEAD does not
by itself change the commit the branch points at, so it is not a substitute for the other two.

### Step 2: or stop deriving the value from the file system at all

Read the hash by invoking git from the build script and re-run on every build:

```rust
let hash = std::process::Command::new("git")
    .args(["rev-parse", "--short=8", "HEAD"])
    .output()
    .ok()
    .filter(|o| o.status.success())
    .map(|o| String::from_utf8_lossy(&o.stdout).trim().to_string())
    .unwrap_or_else(|| "unknown".into());
println!("cargo:rustc-env=GIT_HASH={}", hash);
println!("cargo:rerun-if-changed=build.rs");
```

This is correct but trades away incremental build time: running git on every build invalidates the
crate's build-script fingerprint each time. Acceptable for a small service; measure before doing it in
a large workspace.

### Step 3: or use a crate that already knows the edge cases

`vergen` (plus `vergen-gitcl` / `vergen-gix` depending on version) emits `GIT_HASH`, branch, dirty
state and timestamps with the `rerun-if-changed` plumbing for worktrees, `packed-refs` and detached
HEAD already handled. For a project that will keep needing this metadata, that is the lower-risk
choice than hand-maintaining a list of `.git` paths — every git layout edge case you forget becomes
another silent stale hash.

### Step 4: clear the stale artifact

Fixing the build script does not fix the binary that is already deployed. Rebuild and **redeploy**:

```bash
touch build.rs      # force one build-script re-run even before the new paths are watched
cargo build --release
```

## Verification

The reporter's criterion, made checkable:

1. Make a real commit, rebuild, redeploy.
2. `curl -sS http://127.0.0.1:<port>/api/version` and compare `GIT_HASH` against
   `git rev-parse HEAD` for the deployed commit; compare `BUILD_TS` against the build's start time.
3. The front end's `hasNew` returns to normal: it is `true` only when the served version genuinely
   differs from the one the client is running.

Cross-check that does not depend on the endpoint at all: read the hash out of the binary's symbol
table / DWARF as the reporter did. If the binary's hash and `git rev-parse HEAD` agree, the build path
is fixed; if they disagree, the endpoint is reporting the bin correctly and the build is still stale.

## Notes

- Evidence level E1: one operator's report with the build-script line and the verification method; not
  reproduced in this repository. The exact crate layout and the injected `env!` names come from the
  intake.
- **The failure mode is silent by construction.** A stale `rerun-if-changed` never produces a warning:
  the build is up to date *as far as Cargo knows*. Treat "metadata correct in dev, wrong in
  production" as a fingerprint problem before treating it as a deployment problem.
- If the repository is built from a git-less source tree (a release tarball, a Docker build context
  without `.git`), `.git/*` watch paths cannot exist. The build script's `unwrap_or_default` above
  yields `unknown`; decide explicitly whether that should be a build error rather than a served value.
- Emitting `rerun-if-changed` on a path that does not exist is not a dependable permanent trigger:
  prefer computing the ref path from `.git/HEAD`, as in Step 1, or let a crate own the logic.
- Directory watch semantics are recursive ("any file in that directory"), so pointing at `.git/` as a
  whole also works — at the cost of re-running on every object write, index update, and rebase step.
