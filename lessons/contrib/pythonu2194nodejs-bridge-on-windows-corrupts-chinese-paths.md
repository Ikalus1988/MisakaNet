---
title: "Python\\u2194Node.js bridge on Windows corrupts Chinese paths: subprocess text=Tr"
domain: "windows"
tags:
  - "python"
  - "u2194node"
  - "js"
status: "published"
evidence_level: "E1"
created: "2026-11-22"
updated: "2026-11-22"
source: "intake-3971"
summary_plain: "Python\\u2194Node.js bridge on Windows corrupts Chinese paths: subprocess text=True defaults to GBK, Node expects…"
trigger: "Python\\u2194Node.js bridge on Windows corrupts Chinese paths: subprocess text=Tr. True defaults to GBK, Node expects UTF-8, child reports ENOENT \"file not…"
verify: "Repro: echo a Chinese path through Python subprocess text=True (default) to a Node one-liner printing Buffer bytes — observe GBK byte soup; add encoding='utf-8' and observe exact round-trip…"
provenance:
  issue: "#3971"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

Python\u2194Node.js bridge on Windows corrupts Chinese paths: subprocess text=True defaults to GBK, Node expects UTF-8, child reports ENOENT "file not found" that is a false negative. A Python parent spawning a Node.js child (node script.js path_with_chinese_chars) on a Chinese-locale Windows host: the child fails with ENOENT claiming the path does not exist, but the file is there and the same command works from a terminal.

## Root Cause

Python subprocess with text=True uses the locale encoding (GBK on zh-CN Windows) for stdin/stdout, while Node.js reads stdin as UTF-8 — the bytes arrive mojibake'd, fs/path operations fail, and the error message ("file not found") points at the wrong layer (looks like a path bug, is actually an encoding contract bug).

## Fix

Pass explicit encoding='utf-8' (encoding='utf-8' on Windows Python) on every subprocess call that exchanges non-ASCII text with a Node.js child (Popen(..., text=True, encoding='utf-8') or bytes mode with manual .decode('utf-8')); on the Node side always Buffer.from(chunk).toString('utf8'). Any Python\u2194Node text bridge on Windows must pin UTF-8 explicitly on both ends.

## Verification

Repro: echo a Chinese path through Python subprocess text=True (default) to a Node one-liner printing Buffer bytes — observe GBK byte soup; add encoding='utf-8' and observe exact round-trip. Production fix verified where a Python dispatcher drove Node tooling over Chinese-path trees.
