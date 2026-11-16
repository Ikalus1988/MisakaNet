---
title: "A QSettings INI sanitizer that strips lines starting with `@Variant(` and contai"
domain: "dsh"
tags:
  - "model-variant"
  - "qsettings"
  - "ini"
status: "published"
evidence_level: "E1"
created: "2026-11-16"
updated: "2026-11-16"
source: "intake-4796"
summary_plain: "A QSettings INI sanitizer that strips lines starting with `@Variant(` and containing `PySide::PyObjectWrapper`…"
trigger: "A QSettings INI sanitizer that strips lines starting with `@Variant(` and contai. containing `PySide::PyObjectWrapper` reported \"0 removed\" (file considered…"
verify: "On PySide6 6.11.3 (real packaged runtime) a plain and an escaped config each execute a marker-creating payload when read directly with QSettings, while the version-gated path performs no…"
provenance:
  issue: "#4796"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

A QSettings INI sanitizer that strips lines starting with `@Variant(` and containing `PySide::PyObjectWrapper` reported "0 removed" (file considered clean) while PySide6 6.11 still unpickled the value when QSettings.value() parsed the section, so an attacker-writable settings file executed code. The same scan skipped files over a size cap, symlinked files and read-only config directories, and missed QSettings-quoted values such as `model="@Variant(...`. PySide6 6.12+ instead raises `RuntimeError: Failed to deserialize Python object from QDataStream...` without executing.

## Root Cause

QSettings stores a Python object set via setValue() as `@Variant(...PySide::PyObjectWrapper...)` containing pickle. The INI reader unescapes `\xHH` and strips double quotes BEFORE calling stringToVariant(), and QSettings itself quotes a value when the escaped payload contains a comma (0x2c is an ordinary pickle byte). A literal raw-byte match on the file text is therefore a parser differential: `\x40Variant(...` or `PySide::PyObject\x57rapper` is invisible to the scan but Qt still parses an @Variant and deserializes it. On PySide6 < 6.12 the unpickle happens while the section is parsed, so no try/except around value() can help.

## Fix

Treat the raw-byte scan as migration code, not a security boundary, and gate on the binding's behaviour. On a binding that rejects pickled QSettings values (PySide6 >= 6.12) sanitize the INI before constructing QSettings. On a binding that does not (PySide6 < 6.12) do not let QSettings read an attacker-writable file at all: move the existing file aside as a best-effort backup and back settings with an in-memory QSettings-compatible store (value/setValue/remove/contains, groups, sync, fileName); avoid a throwaway temp file because a same-uid process can replace any file the app can read.

## Verification

On PySide6 6.11.3 (real packaged runtime) a plain and an escaped config each execute a marker-creating payload when read directly with QSettings, while the version-gated path performs no settings-file read and executes nothing (read helper monkeypatched to raise is never called). On PySide6 6.12.0 the same configs raise RuntimeError and do not execute. Regression suite: opt-in test on the real old runtime with a negative control that must execute, plus escaped, quoted, oversized, symlinked and read-only cases.

PySide6 6.11.3: plain and escaped configs execute the payload when read directly; the fail-closed path reads no settings file and executes nothing. PySide6 6.12.0: same configs raise RuntimeError and do not execute. Opt-in real-runtime regression test included.
