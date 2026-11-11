---
title: "安装器 install 在 Windows 上因 github.com 不可达而失败：gh api 与 PyPI 却正常"
domain: "windows"
tags:
  - "cli"
  - "hub"
  - "install"
status: "published"
evidence_level: "E1"
public_analogue: "pipx / uv tool install — the public equivalents of a private wrapper that shells out to pip"
created: "2026-11-11"
updated: "2026-11-11"
source: "intake-4663"
summary_plain: "安装器 install 在 Windows 上因 github.com 不可达而失败：gh api 与 PyPI 却正常"
trigger: "安装器 install 在 Windows 上因 github.com 不可达而失败：gh api 与 PyPI 却正常"
verify: "The CLI runs, the bundled suites pass (5 unit + 5 E2E), a demo project renders SVG/PNG via mermaid.ink, `export share` returns a mermaid.live URL, and `安装器 launch mermaid ...` forwards through…"
provenance:
  issue: "#4663"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

安装器 install <name> fails on Windows when github.com is unreachable, even though `gh api` and PyPI work.

## Root Cause

1. 安装器 shells out to `pip install "git+https://github.com/HKUDS/CLI-Anything.git#subdirectory=<name>/agent-harness"` and captures pip output with `text=True` under the local GBK code page. A non-GBK byte crashes the decoder before the real error is shown.
2. The global git config contains `<REDACTED:email>:.insteadOf=https://github.com/`, so pip's `git+https` clone is rewritten to SSH. HTTPS 443 is blocked by the network and SSH 22 is reset, so neither transport works.
3. 安装器 tracks installs only in `~/.<wrapper>/installed.json`; a manual `pip install` leaves `安装器 info <name>` reporting "not installed".

## Fix

1. Set `PYTHONUTF8=1` so pip output decodes cleanly.
2. Fetch the harness source through `gh` (api.github.com is reachable): recursively via `gh api repos/HKUDS/CLI-Anything/contents/<name>/agent-harness?ref=main`, or per file with `-H "Accept: application/vnd.github.raw"`.
3. `python -m pip install <local agent-harness dir>`.
4. Add a `.cmd` shim for the generated `cli-anything-<name>.exe` to a PATH directory (the Python `Scripts` dir is not on PATH).
5. Optionally register it in `installed.json` as `{version, entry_point, source:"harness", strategy:"pip"}`.

## Verification

The CLI runs, the bundled suites pass (5 unit + 5 E2E), a demo project renders SVG/PNG via mermaid.ink, `export share` returns a mermaid.live URL, and `安装器 launch mermaid ...` forwards through the shim.

cli-anything-mermaid runs; 10 bundled tests pass; SVG/PNG render and share URL work; 安装器 launch forwards correctly.
