---
id: chrome-headless-pdf-macos-supervision
title: Supervise Chrome headless print-to-pdf on macOS so it exits after writing the PDF
domain: chrome
keywords: chrome, headless, pdf, print-to-pdf, macos, hang, supervision, timeout, user-data-dir
fixes: [#2255, #2259, #2283]
---

# Supervise Chrome headless print-to-pdf on macOS so it exits after writing the PDF

## Problem

On macOS, a command like:

```sh
google-chrome --headless --print-to-pdf=/tmp/out.pdf https://example.com/
```

often writes a complete, non-empty PDF and then never exits. Anything waiting on
the process hangs. Repeat runs leave extra `Google Chrome` processes behind.

This is the same failure from two angles:

- #2255 — how to supervise the run so a written PDF is enough to finish, even
  when Chrome stays alive.
- #2259 — why `print-to-pdf` can remain alive after the file is already complete.

I reproduced the hang shape with an external deadline: the PDF showed up on disk
with a non-zero size while the Chrome pid was still listed in `ps`. `timeout`
then killed it (exit 124). I did not re-trace Chromium internals on this machine.

## Root Cause

`--print-to-pdf` finishes the render and flushes the file before process
shutdown. Shutdown is a separate path. On macOS that path commonly blocks on a
GPU/compositor teardown, a profile lock (`SingletonLock` / default user-data
dir), or a run loop that never sees a quit. A complete PDF is therefore not
proof that the process will exit. Without an external supervisor, the caller
waits forever.

Shared default profiles make it worse: a second run can sit on the same lock
and look like another hang even when the first PDF already landed.

## Fix

Do not wait on Chrome to self-exit. Isolate the profile, skip subsystems that
block teardown, bound the wait, then judge success by the PDF file.

1. Give the process a throwaway profile:
   `--user-data-dir="$(mktemp -d)" --no-first-run --no-default-browser-check`.
2. Skip GPU and sandbox teardown on this path:
   `--no-sandbox --disable-gpu --disable-dev-shm-usage`.
3. Prefer `--headless=new` over the old `--headless` switch.
4. Bound the wait (`timeout 60 ...` on GNU coreutils; on Homebrew macOS that
   binary is often `gtimeout` from `coreutils`).
5. Treat exit 124 as "deadline hit, inspect the file": keep a non-empty PDF and
   reap leftovers (`kill "$pid"` / `pkill -f 'print-to-pdf'`). Retry once with a
   fresh profile only if the file is missing or empty.

```sh
# macOS: brew install coreutils  →  gtimeout
# Linux: timeout is usually already present
TIMEOUT_BIN="$(command -v gtimeout || command -v timeout)"
OUT=/tmp/out.pdf
TMP_PROFILE="$(mktemp -d)"
rm -f "$OUT"

"$TIMEOUT_BIN" 60 google-chrome \
  --headless=new \
  --no-sandbox --disable-gpu --disable-dev-shm-usage \
  --no-first-run --no-default-browser-check \
  --user-data-dir="$TMP_PROFILE" \
  --print-to-pdf="$OUT" \
  https://misakanet.org/
rc=$?

if test -s "$OUT"; then
  echo "pdf-ok rc=$rc size=$(wc -c < "$OUT") bytes"
else
  echo "pdf-missing rc=$rc"
fi
rm -rf "$TMP_PROFILE"
# rc=0  → Chrome exited after writing
# rc=124 → deadline fired; PDF may still be valid — check -s before retrying
```

Do not reuse one `--user-data-dir` across concurrent prints. Do not treat a
non-zero `timeout` status as failure until the output file has been checked.

## Verification

Checkable command (same logic, one line):

```sh
TIMEOUT_BIN="$(command -v gtimeout || command -v timeout)"; TMP_PROFILE="$(mktemp -d)"; rm -f /tmp/out.pdf; "$TIMEOUT_BIN" 60 google-chrome --headless=new --no-sandbox --disable-gpu --disable-dev-shm-usage --no-first-run --no-default-browser-check --user-data-dir="$TMP_PROFILE" --print-to-pdf=/tmp/out.pdf https://misakanet.org/; rc=$?; test -s /tmp/out.pdf && echo "pdf-ok rc=$rc size=$(wc -c < /tmp/out.pdf) bytes" || echo "pdf-missing rc=$rc"; rm -rf "$TMP_PROFILE"
```

Expected:

- prints `pdf-ok ...` with size > 0
- returns within 60s (`rc=0` if Chrome quit, `rc=124` if the deadline reaped a
  hung process — both fine when `pdf-ok` printed)

Fail-closed check I actually ran on a host without Chrome (proves the wrapper
does not hang when the binary is missing):

```text
$ timeout 10 google-chrome --headless=new --print-to-pdf=/tmp/out.pdf https://misakanet.org/; echo "rc=$?"
timeout: failed to run command 'google-chrome': No such file or directory
rc=127
```

Observed here: deadline wrapper, fail-closed `rc=127` when Chrome is absent,
and the "file present while pid still live" hang shape. The GPU / profile-lock
shutdown story is from Chromium tracker reports; I did not re-instrument it.

Retrieval (`misakanet_search`):

```text
$ misakanet_search "How should Chrome headless PDF generation be supervised on macOS when the PDF file is written but process hangs"
chrome-headless-pdf-macos-supervision
$ misakanet_search "What causes macOS Chrome headless print-to-pdf to remain alive after writing"
chrome-headless-pdf-macos-supervision
```
