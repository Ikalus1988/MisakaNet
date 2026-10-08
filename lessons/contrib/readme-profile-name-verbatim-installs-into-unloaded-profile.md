---
domain: "devops"
title: "Following a README's --profile name verbatim installs into a profile the running host never loads"
tags:
  - "plugin-manager"
  - "profile"
  - "install"
  - "documentation"
  - "silent-failure"
  - "dsh"
status: "draft"
evidence_level: "E1"
summary_plain: "README said --profile web, but only a desktop profile existed, so the plugin installed and never loaded."
trigger: "--profile name from README installs into a profile the running host never loads"
verify: "list $DSH_HOME/profiles/ before install, confirm the profile name matches the running host, rewrite the command"
---

# Following a README's --profile name verbatim installs into a profile the running host never loads

## Problem

Install instructions from plugin READMEs and a marketplace used `--profile web`, but this machine's only profile is `desktop`. Running them as written would have created/used a second, unloaded profile — the plugin would appear installed and silently never load.

The user would see the install command exit `0`, see "installed successfully" in the log, and then wonder why the plugin's components and tools never appear in the running host. There is no error, no warning, no log line — the install technically succeeded into a profile that nothing consumes.

## Root Cause

Trusting an example profile name from documentation instead of resolving the host's actual profile set.

A README's `--profile web` is an *example*, chosen because the README author's machine happened to have a profile named `web`. It is not a contract — the profile namespace is host-local, and what `web` means on one machine has no relationship to what it means on another. The command-shape (`install --profile <name>`) is portable; the value (`web`) is not.

## Solution

### Step 1 — Enumerate the real profiles before any plugin install

Before running any install command, list the actual profiles on this host:

```bash
ls $DSH_HOME/profiles/
```

(On a default install `$DSH_HOME` is `~/.dsh`; on a managed host it can be `/opt/dsh`.)

### Step 2 — Confirm which profile the running GUI/CLI actually consumes

The directory listing tells you what *exists*; it does not tell you what is *loaded*. The two diverge when:
- the host has multiple profiles for different projects,
- a profile was created by a previous install but never wired into the running host's config,
- the host's running config points at a profile whose directory has been renamed.

The actual loaded profile is the one named in the host's bootstrap config (the file the GUI/CLI reads at startup to decide which profile to mount). Read that config and confirm the profile name *before* passing it to `--profile`.

### Step 3 — Rewrite the command

Take the README's install command and substitute the host's actual loaded profile name:

```bash
# README example (do NOT run as-is):
dsh plugin install some-plugin --profile web

# Rewritten for this host (profile name from step 2):
dsh plugin install some-plugin --profile desktop
```

### Step 4 — Never pass a profile name sourced only from a README

If a README or marketplace entry says `--profile <name>`, treat `<name>` as a placeholder. The README author cannot know your host's profile namespace. The portable part of the command is the *flag*, not the *value*.

## Verification

After install, the package must appear in the intended profile's `dsh.profile.bundles` AND its components/tools must be actually present in the running host:

```bash
# 1. The package is in the intended profile's bundle list
cat $DSH_HOME/profiles/desktop/dsh.profile.bundles | grep some-plugin

# 2. The components/tools the plugin provides are loaded by the running host
dsh tool list | grep -F some-plugin
```

If (1) passes but (2) does not, the install went into a profile the running host does not load — re-do step 2 to confirm the loaded profile name and reinstall.

## Notes

- This is the same shape as "the README's `npm install -g foo` works on the README author's machine but installs into a different Node install on yours" — the install path is host-local, and the README cannot pin it.
- The silent-failure mode (install succeeds, plugin never loads) is harder to debug than an outright error because the install log says "success". The verification step (2) catches it: if the tool is not in `dsh tool list`, the install was into the wrong profile.
- Related lessons: `[A stubbed success is not a sandbox]` (success without observability is not success), `[An allowlist that rejects real data is worse than no validation]` (host-local config beats example config).
