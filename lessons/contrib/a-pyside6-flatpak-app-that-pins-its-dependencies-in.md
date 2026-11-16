---
title: "A PySide6 Flatpak app that pins its dependencies in pyproject.toml still ships t"
domain: "dsh"
tags:
  - "pip3"
  - "pyside6"
  - "flatpak"
status: "published"
evidence_level: "E1"
created: "2026-11-16"
updated: "2026-11-16"
source: "intake-4797"
summary_plain: "A PySide6 Flatpak app that pins its dependencies in pyproject.toml still ships the base app's much older PySide6."
trigger: "A PySide6 Flatpak app that pins its dependencies in pyproject.toml still ships t. the base app's much older PySide6."
verify: "Built and installed bundle reports PySide6 6.12.0 / shiboken6 6.12.0 / Qt 6.12.0 and the guard passes inside it; a fresh-process read of a hostile QSettings config raises RuntimeError and creates no…"
provenance:
  issue: "#4797"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

A PySide6 Flatpak app that pins its dependencies in pyproject.toml still ships the base app's much older PySide6. The manifest used io.qt.PySide.BaseApp 6.11 (which provides PySide6 6.11.3 in /app) and installed the application with `pip3 install --no-deps`, so the security-relevant PySide6 upgrade (6.12, which refuses to deserialize pickled QSettings values) never reached the release artifact — and no build step noticed. There was no io.qt.PySide.BaseApp 6.12 branch on Flathub at the time.

## Root Cause

Flatpak base apps provide /app content, including Python site-packages, and the module's pip install only adds what its own requirements list. A version pin in pyproject.toml has no effect on the Flatpak build, and nothing at build time compares the bundled binding with the required one, so the old binding silently wins.

## Fix

Install exact pins over the base app in the app's module (`pip3 install --no-deps --prefix=${FLATPAK_DEST} "pyside6-essentials==X" "shiboken6==X"`), then run a build-time guard that fails the build if the importable PySide6 is older than X, if shiboken6 and Qt minors do not match it, or if a fresh process does not refuse a pickled QSettings value (payload marker absent). Run the guard inside the deployed bundle as well, and keep an offscreen smoke test (import app, QApplication, QtDBus). Expect leftover base-app metadata/addon files in /app (pip does not remove files absent from the new version; base-app files cannot be deleted), record the bundle-size trade, and remove the pin once a BaseApp branch with the newer binding lands.

## Verification

Built and installed bundle reports PySide6 6.12.0 / shiboken6 6.12.0 / Qt 6.12.0 and the guard passes inside it; a fresh-process read of a hostile QSettings config raises RuntimeError and creates no marker; the same test on BaseApp//6.11 executes the payload (negative control), proving the version upgrade is the actual fix.

Built/installed bundle: PySide6 6.12.0 / Qt 6.12.0, guard passes inside the bundle, fresh-process hostile read raises RuntimeError without a marker; the same test on BaseApp//6.11 executes the payload (negative control). Offscreen smoke test imports the app and constructs QApplication/QtDBus.
