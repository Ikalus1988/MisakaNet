---
title: 'A hook that swallows every error makes a misconfiguration look like "nothing to do"'
domain: claude
tags:
  - claude-code
  - hooks
  - error-handling
  - observability
  - ci
  - settings-json
status: published
created: '2026-09-12'
updated: '2026-09-12'
source: claude-code-hook-silent-failure-2026-09-12
evidence_level: E1

provenance:
  source: "external"
  contributor: "Ikalus1988"
  merged_at: "2026-09-12"
  evidence: "post-publication"
---

# A hook that swallows every error makes a misconfiguration look like "nothing to do"

## Problem

A `UserPromptSubmit` hook gave a non-multimodal main model the ability to see pasted screenshots. The
user pasted an image, sent a message, and nothing happened — no description, no error, no warning. The
hook's own CI was green:

```bash
python -m py_compile image-vision.py                  # ok
python image-vision.py --help                         # ok
env -u VISION_API_KEY python image-vision.py --test-image /tmp/nope.png   # exit 2, by design
echo '{}' | VISION_API_KEY=fake python image-vision.py                     # prints {}
```

Every one of those steps passes whether the hook is correctly configured or not. That is the whole
problem: **"there were no new images to describe" and "I could not do my job" produce the identical
observable** — an empty result and exit code 0.

## Root Cause

Keeping the turn alive is the right contract for a prompt hook, so the entry point ends with:

```python
try:
    run_hook()
    return 0
except Exception as e:
    # Never block the turn on a hook crash.
    sys.stderr.write(f"image-vision hook crashed: {e}\n")
    print(json.dumps({}))
    return 0
```

The `except` is not the bug — a missing API key, a wrong interpreter, an unwritable cache directory or a
`settings.json` that never loaded must not break the user's turn. The bug is that the swallowed error
**lands nowhere the user will look**: one line of stderr that the host may not surface, then an empty
JSON object that the host treats as a normal "no images yet" answer.

I verified the degradation is deliberate and thorough before writing this up — empty stdin, malformed
JSON, a fresh `$HOME` with no image cache, a missing `--test-image` path and a missing API key all exit
cleanly. Everything behaves. Nothing reports.

## Solution

Keep the swallow; add a witness. Whatever a failure path prints as a "nothing happened" result must also
leave evidence somewhere:

```python
LOG = Path.home() / ".claude" / "hooks" / "image-vision.log"

def log_failure(error: BaseException) -> None:
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as fh:      # rotate/truncate as needed
            fh.write(f"{datetime.now().isoformat()} {type(error).__name__}: {error}\n")
    except OSError:
        pass                                             # logging must never block the turn either

try:
    run_hook()
    return 0
except Exception as e:
    print(f"image-vision: not applied ({type(e).__name__}) — see {LOG}", file=sys.stderr)
    log_failure(e)
    print(json.dumps({}))
    return 0
```

Three inexpensive pieces, in order of value:

1. **A sidecar log.** The user's question is "is it broken, or is there nothing to do?" — one
   `tail ~/.claude/hooks/image-vision.log` answers it. Log the traceback, not just the message.
2. **One line of stderr naming the class of failure.** Hosts surface hook stderr; `not applied
   (KeyError)` is enough for an agent (or the user's agent) to act on, and it does not block the turn.
3. **A `--doctor` mode** that re-runs the setup checks on demand (key present, interpreter path, cache
   directory writable, hook registered in `settings.json`) and exits non-zero with a fix hint. Cheap,
   and it turns a support conversation into a command.

Then make CI test the *failure* path, not just the happy path: install with a deliberately broken
config and assert that a discoverable signal appeared, e.g.

```bash
env -u VISION_API_KEY python image-vision.py < /dev/null 2> stderr.txt | grep -q '^{}$'
grep -q 'not applied' stderr.txt      # the silence must be witnessed
test -s ~/.claude/hooks/image-vision.log
```

## Verification

- Break the configuration on purpose (unset the key, or point the hook at a nonexistent interpreter),
  run the hook, and confirm all three of: exit code 0 (the turn still doesn't break), a human-readable
  line on stderr, and a new entry in the sidecar log.
- Run the same command with a *healthy* config and confirm the log stays empty — otherwise the signal is
  noise and users learn to ignore it.
- Re-run the original CI steps unchanged: they must still pass. The added signal is additive.

## Detection Heuristics

- Any "never block / never fail" error sink — a bare `except: pass`, `|| true`, `catch { return [] }`,
  `2>/dev/null` — is fine for availability and useless for diagnosis **unless** it leaves a witness.
  Grep for the pattern, then ask: *how would a user tell "nothing to do" from "I broke"?*
- The tell is a **single observable for two states**. If a component's success output and its internal
  failure output are both "empty", it has no observability, however tidy the code is.
- CI that only exercises a graceful-degradation component's success paths proves the code compiles, not
  that anyone can debug it. Add one step that breaks the config and asserts a discoverable signal.
- For hooks and daemons specifically: if the platform shows stderr to the user, stderr *is* the channel —
  but it is transient, so pair it with a file the user can read later.
