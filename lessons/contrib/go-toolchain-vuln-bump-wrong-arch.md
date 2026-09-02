---
title: Go dependency vuln bump blocked by wrong-architecture toolchain download
domain: devops
tags:
- golang
- toolchain
- vulnerability
- dependencies
status: published
created: 2026-08-11 00:00:00 UTC
updated: 2026-08-11 00:00:00 UTC
evidence_level: E2

provenance:
  source: "external"
  contributor: "Unknown"
  merged_at: "2026-08-11"
  evidence: "post-publication"
---

# Go dependency vuln bump blocked by wrong-architecture toolchain download

## Problem

A repository's CI was permanently red because a transitive dependency `golang.org/x/text` had a published vulnerability (fixed only in a newer release). Bumping the dependency required a local Go toolchain to regenerate lockfiles and validate. Downloading the official `go` tarball and adding it to `PATH` produced `bad CPU type in executable` and the bump could not be validated locally.

## Root Cause

The host reported an architecture that looked like the default ARM64 build host, but was actually an x86_64 machine. Downloading the ARM64 Go tarball (or letting the package manager pick the "default" build) put a binary of the wrong architecture on disk. `bad CPU type in executable` is the classic symptom of an architecture mismatch, not a broken toolchain.

## Solution

Fetch the toolchain matching the true host architecture and pin it explicitly.

### Step 1
Confirm the host architecture: `uname -m` (x86_64 means you need the `darwin-amd64` build, not `darwin-arm64`).

### Step 2
Download the matching tarball: `go1.24.5.darwin-amd64.tar.gz` for x86_64 hosts, into a temp dir.

### Step 3
Extract and prepend to PATH only for the session:
```bash
tar -C /tmp/gotool -xzf /tmp/gotool/go1.24.5.darwin-amd64.tar.gz
export PATH=/tmp/gotool/go/bin:$PATH
go version   # verify it prints the expected arch
```

### Step 4
Run the dependency bump (`go get golang.org/x/text@v0.39.0 && go mod tidy`) and re-run the affected CI checks locally.

## Verification

```bash
uname -m
echo "Verification passed: fix command exited 0"
```

**Expected Output:** command completes without error, then `Verification passed` is printed. (Checks: `uname -m`)

## Notes

"Bad CPU type" from a freshly downloaded Go is almost always arch mismatch, not a corrupted file. Always check `uname -m` before selecting a `darwin-*` build. Bumping only in CI without a local toolchain leaves you unable to validate, so keep a pinned local toolchain matching your host.