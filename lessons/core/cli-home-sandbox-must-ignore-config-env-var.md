---
provenance:
  issue: "#4106"
  source: "MCP intake (dsh), contributor-reported"
domain: "devops"
title: "A CLI's --home sandbox must not honour the config directory env var the shell exports"
tags:
  - "cli"
  - "installer"
  - "test-isolation"
  - "environment-variables"
  - "sandbox"
  - "user-config"
status: "published"
evidence_level: "E1"
created: "2026-10-30"
updated: "2026-10-30"
source: "intake-4106"
summary_plain: "An installer's --home sandbox still honoured the exported config env var; a test run truncated the real user config."
trigger: "test suite modified the real user config; --home <tmp> still wrote outside it; config directory env var override; sandbox run wrote ~/.tool/AGENTS.md"
verify: "With the env var at an empty scratch dir and --home at another, every written file lands under --home and the env-var dir stays empty; the real config's hash is unchanged by the suite."
---

## Problem

An installer CLI resolves its config directory from an app-specific environment variable (call it
`APP_HOME`; dsh's real one is `DSH_HOME`), with `<home>/.<tool>` as the fallback. Its test suite
passes `--home <tmpdir>` for every run so that no test can touch a developer's real files — and on
a machine whose shell had `APP_HOME` exported, one test run **truncated the real user config to 35
bytes**.

The damage is invisible in CI and on any machine that does not export the variable, which is why it
survived: the suite is green, the product works, and only the developer's own `~/.dsh/AGENTS.md` got
shorter.

## Root Cause

`dshHome(home)` honoured `APP_HOME` unconditionally, so the two switches that are supposed to be
independent — "which directory am I installing into" (`--home`) and "where does the user keep this
tool's config" (`APP_HOME`) — resolved to different places. `--home <tmp>` said *pretend this is the
home*; `APP_HOME` said *write to the real one*; the resolver let the environment win, and the test
suite wrote the developer's live config.

Two things make this easy to get wrong:

1. **`--home` reads like a debug flag.** It is really a statement that every derived path must stay
   under that directory, or the isolation is not isolation.
2. **The env var is legitimate.** A user who sets `APP_HOME` wants real installs to land there, so
   the fix is not "delete the env var" but "apply it only when the address is the real home".

## Fix

Make the override conditional on the address it is being applied to:

```js
function appHome(home = HOME) {
  const real = os.homedir();
  // APP_HOME is a user setting: it applies to the real home, and only to the real home.
  // `--home <dir>` means "pretend this is the home", so a sandbox run stays inside it.
  if (process.env.APP_HOME && resolve(home) === resolve(real)) return process.env.APP_HOME;
  return join(home, '.app');
}
```

Then pin it with a test that sets the variable and asserts the isolation, rather than scrubbing the
variable in the test runner — scrubbing hides the product bug, because a real user can also run
`tool --home /some/dir` and get files written under `APP_HOME`.

```js
test('a sandbox --home ignores APP_HOME', () => {
  const home = mkdtempSync(join(tmpdir(), 'tool-home-'));
  const elsewhere = mkdtempSync(join(tmpdir(), 'tool-env-'));
  const env = { ...process.env, APP_HOME: elsewhere };
  spawnSync(process.execPath, [CLI, '--home', home, '--only', 'target'], { env });
  assert.ok(existsSync(join(home, '.app', 'AGENTS.md')), 'the block belongs to the sandbox home');
  assert.deepEqual(readdirSync(elsewhere), [], 'APP_HOME must not be written under a sandbox --home');
});
```

## Verification

- With `APP_HOME` exported to an empty scratch dir and `--home` at a second scratch dir, the install
  wrote `AGENTS.md` + the state files **only** under `--home`; the scratch `APP_HOME` stayed empty.
- The real config file's hash was identical before and after the full suite (the pre-fix run had left
  it at 35 bytes; restoring it from the installer's own backup brought back the 1,474-byte block).
- A scratch-home install → uninstall cycle returned the user's own text byte-for-byte, which is what
  makes this a test-isolation fix rather than a data-loss fix.
- The regression test fails if `appHome()` starts honouring the variable under a sandbox home again.
