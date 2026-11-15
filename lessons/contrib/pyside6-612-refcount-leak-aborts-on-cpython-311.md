---
title: "PySide6 6.12 在 CPython 3.10/3.11 上崩于 none_dealloc：每次普通 Qt 调用漏掉一个 None 引用"
domain: "python"
tags:
  - "pyside6"
  - "refcount"
  - "cpython"
  - "abi3-wheels"
status: "published"
evidence_level: "E1"
created: "2026-11-15"
updated: "2026-11-15"
source: "intake-4931"
summary_plain: "PySide6 6.12 的 wheel 在 CPython 3.11 上每调用一次 void Qt 方法就漏一个 None 引用，随机 abrt；3.12+ 因单例 immortal 看不出来。"
trigger: "Fatal Python error: none_dealloc / bool_dealloc，而同一代码在 CPython 3.12 上不复现"
verify: "3.11.14 + 6.12.0：100 次 QLabel.setText 后 None 引用少 100；降到 6.11.3 增量 0 且退出码 0。"
provenance:
  issue: "#4931"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

PySide6 GUI app aborts at an arbitrary moment with `Fatal Python error: none_dealloc: deallocating None: bug likely caused by a refcount error in a C extension` (or `bool_dealloc` on finalization). The stack names innocent widget paint code, so the traceback misleads. Only CPython 3.10/3.11 is affected; 3.12+ looks healthy.

## Root Cause

PySide6 6.12.0 wheels leak one ref to the `None` singleton on every ordinary `void` Qt call and one ref to `True` on every `Signal.emit()` (PYSIDE-3474; PYSIDE-3424 moved the 6.12 build machines to Python >=3.12, so Py_RETURN_* assumes immortal singletons — CPython GH-134989). On CPython 3.12+ the singletons are immortal (PEP 683) and the corrupting Py_DECREF is a no-op; on 3.10/3.11 the refcount hits zero and the interpreter aborts. Wheels are still `cp310-abi3` and declare Python >=3.10,<3.16, so pip installs them on 3.11 without warning. No application-code workaround exists: every void Qt call leaks.

## Fix

Pin the PySide6 family below 6.12 on CPython < 3.12 with environment markers (`pyside6-essentials~=6.11.0; python_version < '3.12'` / `~=6.12.0; python_version >= '3.12'`, same for a dev `pyside6`), relock, and leave the project's declared Python range unchanged; remove the split once 6.12.1+ ships (upstream fix is build-only).

## Verification

CPython 3.11.14 + PySide6 6.12.0: 100 calls each of QLabel.setText / QColor.setAlpha / QWidget.resize each lose exactly 100 None refs; 100 Signal.emit() lose exactly 100 True refs; animated painted QLabel aborts with SIGABRT (exit 134) in 1-2 s. Same code on 6.11.3: zero deltas, clean exit. 3.12.3 + 6.12.0: clean exit, stable refcounts (immortal singletons). Regression tests: an in-process sys.getrefcount canary (delta 0, warm-up + GC paused, retained QObject) plus an offscreen subprocess animating the painted widget that must exit 0 with non-negative deltas; assert the installed version satisfies the pyproject marker branch. Verified 2026-11 on Linux; PyPI had no 6.12.1 yet at that time.
