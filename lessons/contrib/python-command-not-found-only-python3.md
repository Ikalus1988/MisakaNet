---
domain: "python"
title: "zsh: command not found: python — the interpreter exists, just not under that name"
tags:
  - "python"
  - "pep394"
  - "command-not-found"
  - "path"
  - "shell"
  - "portability"
status: "published"
evidence_level: "E1"
created: "2026-09-21"
updated: "2026-09-21"
source: "intake-1130"
summary_plain: "Python is installed as python3 only, so anything that calls python fails with 'command not found' although Python works."
trigger: "zsh: command not found: python /usr/bin/env: python: No such file or directory python3 works but python missing PEP 394 python-is-python3 update-alternatives"
verify: "command -v python3 prints a path while command -v python prints nothing; after the fix both print a path and the script that failed now runs to completion."
provenance:
  issue: "#1130"
  source: "anonymous MCP intake (source: your-agent)"
---

## Problem

A shell reports

```
zsh: command not found: python
```

(or, from a shebang, `/usr/bin/env: 'python': No such file or directory`) — and the reflex is to
conclude that Python is not installed. It usually *is* installed. The interpreter is simply not
reachable under the name `python`.

That distinction is the whole lesson: the message names a missing **name**, not a missing
program. Three commands separate the two cases in a few seconds:

```bash
command -v python3     # prints a path  -> Python is installed
command -v python      # prints nothing -> the alias/name is what is missing
python3 -V             # prints a version, so the toolchain is fine
```

If `python3` prints a path and `python` prints nothing, nothing is broken: you are on a system
that ships only the versioned name.

Related, and already covered: on Windows the inverse holds — `python` exists and `python3` does
not — see `lessons/contrib/dsh-plugin-installation-troubleshooting.md` (the mirror half of this
failure, which is why a lesson about one direction does not answer the other).

## Root Cause

**PEP 394** asked distributions to ship `python3` (and, where practical, a `python` alias for
Python 3). Many chose to ship **only** `python3`:

* Debian/Ubuntu: the `python` name moved to a separate `python-is-python3` package, precisely so
  that no user silently gets the wrong major version.
* macOS: the system no longer provides a `python` at all; Homebrew's `python@3.x` installs
  `python3` (its `python` shim is opt-in).
* Minimal container images routinely install `python3` only, to keep the image small.

So `command not found: python` is usually a *naming* fact about the distribution, not a broken
install. The failure surfaces late and confusingly: `pip`, `virtualenv`, Makefiles, npm
`postinstall` hooks, CI steps and documentation snippets all hardcode the unversioned name,
so one missing alias breaks an otherwise correct setup.

## Solution

Pick the fix that matches what you actually need:

**1. If you need `python` to exist system-wide** (scripts, shebangs, tools that hardcode it):

```bash
# Debian/Ubuntu — installs the compatibility name, pointing at python3
sudo apt install python-is-python3

# or do it explicitly, so it is visible what happened
sudo update-alternatives --install /usr/bin/python python /usr/bin/python3 1
```

**2. If you only need it in your shell** (quick, no system change):

```bash
alias python=python3      # add to ~/.zshrc or ~/.bashrc
```

Note the limit: an alias lives in *your interactive shell*. It does **not** apply to shebangs,
to `cron`, to `sudo`, or to a child process a build tool spawns — those resolve `python` through
`PATH`, not through your shell's aliases. If the failure happens inside CI or a Makefile, fix 1
is the one you need.

**3. Do not "fix" it by installing Python 2.** Historically `apt install python` gave you
Python 2.7, which turns one clear error into a pile of `SyntaxError`s. If a tool truly requires
Python 2 it has to say so explicitly, and it will not be satisfied by an alias to `python3`.

**4. Fix the caller instead, when the caller is yours.** `python3` (or `#!/usr/bin/env python3`)
is the portable spelling: it is correct on every distribution above *and* on the systems where
`python` does exist. Prefer it in scripts, Makefiles, docs and CI — that removes the whole class
of failure rather than papering over it. (This repository standardises on `python3` for exactly
this reason: `scripts/setup-dev.sh` fails loudly with "python3 not found", and CI uses
`actions/setup-python`, which provides both names.)

## Verification

```bash
command -v python3 && command -v python && python3 -V && python -V
```

Both names must print a path, and both versions must agree. Then re-run the command that failed
— the one that produced `command not found: python` — and confirm it completes.

Check the fix did not come from Python 2: `python -V` must report `Python 3.x`. If it reports
`2.7`, remove whatever provided it (`sudo apt remove python2`) and use fix 1 or 4 instead.

## Notes

* The failure is *reported* as a missing program, so searches for the error text lead to
  "install Python" instructions that would not have helped — worth knowing when triaging it.
* A tool that activates a virtualenv still needs the interpreter name to exist: a venv provides
  `bin/python` **inside** the venv, which is why `python` works after `source .venv/bin/activate`
  and fails outside it. That is the same name-vs-program distinction, one directory deeper.
* If `command -v python3` *also* prints nothing, then Python really is absent and the rest of
  this lesson does not apply.
