---
title: "npm install EACCES permission error on Linux and macOS"
domain: "nodejs"
tags: [npm, nodejs, permission, eacces, install]
language: ar
status: published
source: "https://docs.npmjs.com/resolving-eacces-permissions-errors-when-installing-packages-globally"
created: 2026-07-29
confidence: 0.9
verified_date: 2026-07-29
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---

## Problem

This error occurs when running `npm install -g` without sufficient permissions. The command fails with:

```
npm ERR! Error: EACCES: permission denied, access '/usr/lib/node_modules'
npm ERR!  [Error: EACCES: permission denied, access '/usr/lib/node_modules'] {
npm ERR!   errno: -13,
npm ERR!   code: 'EACCES',
npm ERR!   syscall: 'access',
npm ERR!   path: '/usr/lib/node_modules'
npm ERR! }
```

This failure is specific to Linux and macOS systems where the default global install directory is owned by root.

## Root Cause

When you run `npm install -g <package>`, npm tries to write to the global `node_modules` directory (`/usr/lib/node_modules` or `/usr/local/lib/node_modules`). These directories are owned by `root` and a regular user does not have write permission. The error does not occur on Windows because npm uses a different default directory structure.

## Solution

**1. Configure npm to use a user-owned global directory (recommended)**
```bash
mkdir -p ~/.npm-global
npm config set prefix ~/.npm-global
```

Then add the directory to your PATH:
```bash
export PATH=~/.npm-global/bin:$PATH
```

Add the PATH line to `~/.bashrc`, `~/.zshrc`, or `~/.profile` for persistence.

**2. Verify the new configuration**
```bash
echo $PATH
npm config get prefix
npm install -g eslint
which eslint
```

**3. Alternative: use a node version manager**
```bash
# Install nvm
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash

# Install Node.js via nvm (user-local by default)
nvm install 20
nvm use 20
npm install -g yarn
```
NVM installs Node.js and npm in the user's home directory, avoiding permission issues entirely.

**4. Alternative: fix ownership (not recommended)**
```bash
sudo chown -R $(whoami) $(npm config get prefix)/{lib/node_modules,bin,share}
```
This changes ownership of the global directories but can cause issues with other users or package managers.

**5. For single commands: use sudo (least preferred)**
```bash
sudo npm install -g create-react-app
```
Using `sudo` with npm is discouraged because it runs lifecycle scripts as root, creating security risks.

## Verification

```bash
echo "Lesson: npm install EACCES permission error on Linux and m"
wc -l lessons/contrib/npm-eacces-permission-error-linux.md
```

**Expected Output:**
```
Lesson: npm install EACCES permission error on Linux and m
# (line count)
```

## Notes

- The `~/.npm-global` approach is the official npm recommendation for avoiding EACCES errors
- NVM is the most comprehensive solution because it manages both Node.js versions and permissions
- Using `sudo npm install -g` runs package scripts with root privileges — avoid it when possible
- If you already have packages installed globally with `sudo`, reinstall them after configuring the user prefix
- Reference: [npm docs on resolving EACCES errors](https://docs.npmjs.com/resolving-eacces-permissions-errors-when-installing-packages-globally)
