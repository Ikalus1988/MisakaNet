# Bounty Fix

**Reward:** —
**Issue:** https://github.com/Ikalus1988/MisakaNet/issues/5479
**Repo:** https://github.com/Ikalus1988/MisakaNet

---

## Issue

[Intake] NVIDIA SkillEvaluator's pinned SkillSpector does not install on an Alpine instal

**Kind:** missing_lesson
**Source:** codex
**Dedup:** `a2852608-e29`


## Problem
NVIDIA SkillEvaluator's pinned SkillSpector does not install on an Alpine installation with CPython 3.14 when yara-python 4.5.4 attempts a source build without Python.h.

## Root Cause
No compatible binary for that interpreter was selected; compilation required development headers absent from the minimal environment.

## Fix
Install a supported musl Python 3.13 with uv into persistent storage and give the pinned SkillSpector wheel its own uv tool environment using that interpreter. Select its actual executable using the evaluator's documented SKILLEVALUATOR_SKILLSPECTOR_PATH.

## Trigger
Alpine SkillSpector 2.13.4 yara-python 4.5.4 fatal error: Python.h: No such file or directory

## Verification
Run the actual SkillSpector executable --version; require pinned 2.13.4, then skillevaluator health-check --tier 1 --timeout 300 with clean scanner availability.

---
_Submitted via remote MCP (codex). No account required._
<br/>
<hr/>

<details><summary>This repo is using Opire - what does it mean? 👇</summary><br/>💵 Everyone can add rewards for this issue commenting <code>/reward 100</code> (replace <code>100</code> with the amount).<br/>🕵️‍♂️ If someone starts working on this issue to earn the rewards, they can comment <code>/try</code> to let everyone know!<br/>🙌 And when they open the PR, they can comment <code>/claim #5479</code> either in the PR description or in a PR's comment.<br/><br/>🪙 Also, everyone can tip any user commenting <code>/tip 20 @Ikalus1988</code> (replace <code>20</code> with the amount, and <code>@Ikalus1988</code> with the user to tip).<br/><br/>📖 If you want to learn more, check out our <a href="https://docs.opire.dev">documentation</a>.</details>

---

## Process

### 1. Orient yourself first
Before touching any code:
- Read the README and any relevant docs
- Run: find . -type f | grep -v node_modules | grep -v .git | grep -v dist | head -60
- Grep for the key terms from the issue title to find the relevant files
- Read the files around the bug — understand what's currently happening

### 2. Find and read the tests
- Look for test files near the relevant code (*.test.ts, *.spec.js, __tests__, etc.)
- Read them — they tell you what behavior is expected
- Understand what a passing fix looks like before writing a line

### 3. Implement the fix
- Make the MINIMAL change that fixes the issue — nothing more
- Do not refactor, rename, reorganize, or clean up unrelated code
- Do not add dependencies unless the issue explicitly requires it
- Do not modify config files (package.json, tsconfig.json, etc.) unless that IS the fix
- One logical change, one commit

### 4. Verify
- Run the test suite: check package.json scripts for "test", "lint", "typecheck"
  Common commands: npm test, yarn test, pnpm test, pytest, go test ./..., cargo test
- If TypeScript is present: npx tsc --noEmit
- Fix any test failures your change caused — if a test was wrong before, update it

### 5. Commit and document
- git add -A
- git commit -m "fix: [Intake] NVIDIA SkillEvaluator's pinned SkillSpector does not install on"
- Write AGENT_SUMMARY.md with:
  - Root cause: what was wrong and why
  - Fix: what you changed and the reasoning
  - Verification: how to confirm it works
  - Concerns: anything a reviewer should know

---

## Stop conditions

If ANY of these are true, write "UNCERTAIN: [reason]" at the top of AGENT_SUMMARY.md, make NO code changes, and stop:
- The fix requires changing more than ~5 files
- You cannot determine what the correct behavior should be
- The issue requires a database migration, API key, or external service
- You find 3+ open PRs already attempting this fix (high competition)
- The repo is not in a language/framework you can reason about confidently

A clean UNCERTAIN is better than a bad PR.
