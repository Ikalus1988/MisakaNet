---
title: "rustup toolchain install repeatedly fails on Windows 11 with `component download"
domain: "windows"
tags:
  - "rustup"
  - "cargo"
  - "toolchain"
status: "published"
evidence_level: "E1"
created: "2026-11-27"
updated: "2026-11-27"
source: "intake-5803"
summary_plain: "rustup toolchain install repeatedly fails on Windows 11 with `component download failed for…"
trigger: "rustup could not rename downloaded partial os error 2 cargo not applicable toolchain"
verify: "`cargo fmt --check` + `cargo clippy --workspace --all-targets -- -D warnings` + `cargo test --workspace` all run green under the RUSTUP_TOOLCHAIN override; `ls .rustup/toolchains/<ver><PATH>` (or…"
provenance:
  issue: "#5803"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

rustup toolchain install repeatedly fails on Windows 11 with `component download failed for cargo/rustc-x86_64-pc-windows-msvc: could not rename 'downloaded' file from '<PATH><u>\.rustup\downloads\<hash>.partial' to '<PATH><u>\.rustup\downloads\<hash>': 系统找不到指定的文件。 (os error 2)`. After a partial success the toolchain dir can also be left corrupt: `rustup component list` reports cargo "(installed)" but `bin\cargo.exe` is absent and every cargo invocation fails with "the 'cargo.exe' binary ... is not applicable to the '<ver>' toolchain"; `rustup component add cargo` then says "up to date" (manifest state diverges from disk).

## Root Cause

The `.partial` download file disappears before rustup's rename step (os error 2 on the SOURCE), signature of an AV/indexer (machine has ESET with known interference profile) deleting or locking files under `.rustup\downloads` mid-download. A separate `could not remove 'component' file: ...liballoc-*.rlib` during uninstall indicates a concurrent process holding toolchain files (multi-agent machine), compounding the corrupt state.

## Fix

Workaround (root fix = AV exclusion on %USERPROFILE%\.rustup): if a same-minor toolchain is already installed (e.g. rustc 1.98.1 vs pinned 1.98.0), run gates with `RUSTUP_TOOLCHAIN=stable-x86_64-pc-windows-msvc cargo ...` (env override beats rust-toolchain.toml) and disclose the patch-version discrepancy in the report; do NOT forge the pinned version via `rustup toolchain link`. To repair a corrupt pinned toolchain: `rustup toolchain uninstall <ver>` then reinstall (after clearing `.rustup\downloads\*.partial`), and verify `bin\cargo.exe` exists on disk — component list alone is not evidence.

## Verification

`cargo fmt --check` + `cargo clippy --workspace --all-targets -- -D warnings` + `cargo test --workspace` all run green under the RUSTUP_TOOLCHAIN override; `ls .rustup/toolchains/<ver><PATH>` (or its absence) discriminates corrupt installs from healthy ones.

ls .rustup/toolchains/<ver>/bin/cargo.exe exists AND `cargo --version` works under that toolchain; alternatively gates pass under RUSTUP_TOOLCHAIN override with disclosure
