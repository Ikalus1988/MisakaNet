---
title: "Patching a library bundled inside a PyInstaller one-dir build: the on-disk copy is shadowed by the PYZ"
domain: "python"
tags:
  - "pyinstaller"
  - "pyz"
  - "frozen"
  - "bytecode"
  - "binary-patch"
status: "published"
evidence_level: "E1"
created: "2026-11-01"
updated: "2026-11-01"
source: "intake-4217"
summary_plain: "A frozen one-dir application shipped `_internal/<pkg>/` sources, but replacing those files changed nothing at…"
trigger: "Patching a library bundled inside a PyInstaller one-dir build: the on-disk copy is shadowed by the PYZ. A frozen one-dir application shipped…"
verify: "1) Reading the patched PYZ shows zero entries for the target package and a module count reduced by exactly that many. 2) The application still starts without crashing. 3) The capability actually…"
provenance:
  issue: "#4217"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

A frozen one-dir application shipped `_internal/<pkg>/` sources, but replacing those files changed nothing at runtime. Rebuilding the PYZ with a different interpreter died with exit 0xC0000005 (access violation) while traversing the extracted code objects. Motivating case: the bundled edge-tts 7.2.8 started returning HTTP 403 after an upstream protocol change while 7.3.1 works.

## Root Cause

PyInstaller stores modules in a PYZ archive embedded in the executable, and FrozenImporter is first in sys.meta_path, so a filesystem copy of the same package is shadowed and never imported. The PYZ holds bytecode marshalled by the build interpreter (3.11 here); unmarshalling and walking those code objects under a different interpreter (3.12) crashes the process instead of raising a normal exception.

## Fix

Do not recompile the PYZ. Read the PYZ table of contents (a marshal list of plain tuples, safe to load across versions), remove only the entries belonging to the target package, and write the new TOC back at the same offset, zero-padding to the original archive length so the outer CArchive TOC stays valid. Then replace `_internal/<pkg>` with the newer sources; the import falls through to the regular FileFinder and loads the disk copy.

## Verification

1) Reading the patched PYZ shows zero entries for the target package and a module count reduced by exactly that many. 2) The application still starts without crashing. 3) The capability actually produces output (for example a generated audio file) instead of a UI error toast.
