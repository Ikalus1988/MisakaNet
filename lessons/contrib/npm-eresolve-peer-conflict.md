---
domain: "devops"
title: "npm ERESOLVE is a dependency-graph report, not an install failure — read the chain before reaching for --force"
tags:
  - "npm"
  - "node"
  - "dependencies"
  - "peer-dependencies"
  - "eresolve"
  - "overrides"
  - "lockfile"
status: "published"
evidence_level: "E1"
created: "2026-10-01"
updated: "2026-10-01"
source: "intake-2613"
summary_plain: "npm ERESOLVE 不是装不上，而是 npm 7+ 把 peer 冲突当硬错误报出来：先读依赖链判断是哪一类，再决定升级、overrides 还是最后的 --legacy-peer-deps。"
trigger: "npm ERESOLVE unable to resolve dependency tree Could not resolve dependency Conflicting peer dependency Fix the upstream dependency conflict"
verify: "npm ci 2>&1 | grep -q ERESOLVE && echo 'STILL BROKEN' || echo 'PASS: the peer graph resolves from a clean lockfile'"
provenance:
  issue: "#2613"
---

## Problem

`npm install` stops with:

```
npm ERR! code ERESOLVE
npm ERR! ERESOLVE unable to resolve dependency tree
npm ERR!
npm ERR! While resolving: app@1.0.0
npm ERR! Found: react@18.2.0
npm ERR! node_modules/react
npm ERR!   react@"^18.2.0" from the root project
npm ERR!
npm ERR! Could not resolve dependency:
npm ERR! peer react@"^17.0.0" from some-ui-lib@2.4.1
npm ERR! node_modules/some-ui-lib
npm ERR!   some-ui-lib@"^2.4.1" from the root project
npm ERR!
npm ERR! Fix the upstream dependency conflict, or retry
npm ERR! this command with --force or --legacy-peer-deps
```

The important part is that **this is a report, not a failure mode of its own**: npm 7+ installs peer dependencies
automatically and treats an unsatisfiable peer range as a hard error, where npm 6 only warned. The message
already contains the dependency chain — and the two flags it suggests at the end are the two things you should
reach for **last**, because both of them stop npm from checking the very thing it just complained about.

## Root cause: three shapes, and they have different fixes

Read the chain first (`Found:` vs `Could not resolve dependency:`), then decide which shape you are in.

1. **A peer range that the ecosystem has moved past.** A dependency declares `peer react@"^17"` while your app
   is on 18. Often the library works fine on 18 and the range is simply stale — but "often" is not "verified",
   so this is the shape where you check the library's changelog and issues.
2. **Two of your own dependencies disagree.** Package A wants `lodash@^4`, package B pins `lodash@^3`. There is
   no version that satisfies both, and no flag makes the runtime conflict disappear.
3. **Drift between `package.json`, the lockfile, and an `overrides` block.** A lockfile entry written under an
   older peer contract, or an `overrides` pin that now contradicts a direct dependency, produces ERESOLVE on
   machines that have the lockfile and not on machines that do not — which is why this shape is usually
   discovered in CI.

## Diagnosis (do this before changing anything)

```bash
npm explain react            # every chain that requires react, and which one wants the peer
npm ls react --all           # the resolved tree; exits non-zero while anything is unresolved
npm ls --all 2>&1 | grep -i "invalid\|missing"   # the same thing, filtered to the problem edges
```

`npm explain` is the one that answers "who is asking for this": it prints each dependent and the range it
declared. If the conflict only appears on one machine, compare `git diff package-lock.json` before anything
else — shape 3 hides there.

## Fixes, in the order they deserve

1. **Upgrade the dependency that declares the stale peer range.** This is the only fix that removes the
   conflict rather than silencing it. Check its changelog for the version that widened the range.
2. **`overrides` (npm ≥ 8.3) when you must force a transitive version**:

   ```jsonc
   {
     "overrides": {
       // some-ui-lib 2.4.x is the last line that works with react 18; remove when 3.x ships.
       "some-ui-lib": { "react": "$react" }
     }
   }
   ```

   `"$react"` reuses the version your own `package.json` declares, which keeps one source of truth. Then run
   `npm ls react` and confirm **one** version resolves. An override is a promise that you checked the
   compatibility yourself — leave the comment explaining which release removes it.
3. **`--legacy-peer-deps`** restores npm 6 behaviour: peer dependencies are ignored entirely. It is a
   *reproducible* escape hatch (put it in `.npmrc` if you must, with a comment), but understand what you gave
   up: nothing validates peers any more, so the next genuine incompatibility installs silently and fails at
   runtime instead. Use it per-install while you prepare fix 1 or 2, not as the resting state.
4. **`--force`** installs a tree npm has already told you is inconsistent. It is the "I do not know what is
   happening" button; in CI it turns a build failure into a production failure. Prefer failing the build.

Deleting `node_modules` and `package-lock.json` is a **diagnostic**, never a fix: it re-resolves the whole
graph, which can make ERESOLVE disappear by silently picking different versions — the reproducibility you lose
is exactly what would have caught it.

## Verification

```bash
rm -rf node_modules
npm ci                                   # must finish with no ERESOLVE from a clean lockfile
npm ls <the-package-from-the-chain>      # exactly one version, no "invalid" markers
```

`npm ci` matters more than `npm install` here: it refuses to rewrite the lockfile, so it is the command that
proves the committed graph resolves — the same thing your CI will do.

## What not to do

- Do not add `--force` to a CI step to make a red build green; it removes the check that caught the problem.
- Do not delete the lockfile to "fix" ERESOLVE in a repo that ships one — that is a silent dependency upgrade
  for everyone.
- Do not copy an `overrides` block from a blog post without the comment saying which upstream release removes
  it; the next person cannot tell a deliberate pin from a leftover.

## For agents working on this

Report **which of the three shapes** it is and paste the `npm explain` chain before changing a flag. A
dependency conflict is one of the few failures where "make it install" and "make it correct" are different
outcomes, and the difference survives in the lockfile long after the install command has been forgotten.
