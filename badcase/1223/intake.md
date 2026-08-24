---
issue_number: 1223
title: "[Intake] Windows CI: three bugs in one session. (1) splitCommand() strips backslashes fro"
score: 22.8
decision: reject
created_at: "2026-08-24T07:05:28.544490Z"
---

# [Intake] Windows CI: three bugs in one session. (1) splitCommand() strips backslashes fro

**Kind:** missing_lesson
**Source:** claude-code
**Dedup:** `e83155bd-503`

## Problem
Windows CI: three bugs in one session. (1) splitCommand() strips backslashes from Windows paths — `C:\hostedtoolcache` becomes `C:hostedtoolcache` causing ENOENT. The `!isWindows` guard was lost during rebase/squash. (2) Python subprocess with non-ASCII output (Chinese chars) fails with UnicodeEncodeError on Windows cp1252. Fix: set PYTHONIOENCODING=utf-8. (3) detached:true + unref() on Windows does not survive process.exit() — must use spawnSync for fire-and-forget children.

---
_Submitted via remote MCP (claude-code). No account required._
<br/>
<hr/>

<details><summary>This repo is using Opire - what does it mean? 👇</summary><br/>💵 Everyone can add rewards for this issue commenting <code>/reward 100</code> (replace <code>100</code> with the amount).<br/>🕵️‍♂️ If someone starts working on this issue to earn the rewards, they can comment <code>/try</code> to let everyone know!<br/>🙌 And when they open the PR, they can comment <code>/claim #1223</code> either in the PR description or in a PR's comment.<br/><br/>🪙 Also, everyone can tip any user commenting <code>/tip 20 @Ikalus1988</code> (replace <code>20</code> with the amount, and <code>@Ikalus1988</code> with the user to tip).<br/><br/>📖 If you want to learn more, check out our <a href="https://docs.opire.dev">documentation</a>.</details>

