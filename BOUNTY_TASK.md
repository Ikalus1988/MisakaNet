# Bounty Fix

**Reward:** —
**Issue:** https://github.com/Ikalus1988/MisakaNet/issues/5245
**Repo:** https://github.com/Ikalus1988/MisakaNet

---

## Issue

bug(mcp): a 200 whose body is cut short — the worker is not the author (60 samples, zero short bodies)

**症状**：同一个请求有时收到完整的正文，有时收到**一个 chunk 就断掉**，有时一个字节都不回。客户端一律表现为"解析失败/超时"。

## 实测（2026-11-18，生产，同一条 `misakanet_search` 查询连打五次）

| 次 | `Content-Length` | 实际收到 | 结论 |
|---|---|---|---|
| 1 | 13315 | **605** | 截断 |
| 2 | （无，chunked） | **605** | 截断 |
| 3–5 | 13315 | 13315 | 完整 |

`Accept: application/json`，`MCP-Protocol-Version: 2025-06-18`，同一分钟内完成。

同一天在**最便宜的**端点上也是同一形状（`/api/health`，它不读语料、不碰索引）：5 次里 2 次在 12–20 s 内一个字节都没回来；同一循环里 `https://www.cloudflare.com/` 10/10 全部应答（3–12 s）—— 也就是说这条到 CF 的路由当时是退化的，但**另一个 zone 会答，本服务不应答**。

## 为什么值得单独一条

- 它**不是**语料/索引变慢：`/api/health` 走不到那条路；`#5162` 的 8 秒预算部署之后挂起依旧。
- 它把其它 issue 的判据污染了：客户端看到的是"parse 失败"，于是我们收到 6 条同族 intake（`#4498` 一族），每一条都要人工读一遍才知道是投递问题，不是解析问题。
- `605` 字节固定的两个样本更像是**流被切断**（一个 chunk 的量级），而不是端点生成了坏 JSON。

## 判据（下次直接这样判）

```console
$ curl -s -D /tmp/h -o /tmp/b -H 'Content-Type: application/json' -H 'Accept: application/json' \
    -H 'MCP-Protocol-Version: 2025-06-18' -H 'Origin: https://misakanet.org' \
    -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"misakanet_search","arguments":{"query":"pip install timeout","top":3}}}' \
    https://misakanet.org/mcp
$ grep -i '^content-length' /tmp/h; wc -c < /tmp/b      # 两个数不一致 = 截断
```

## 可能的落点（未验证，按可能性排序）

1. **响应体大小 / gzip 与 chunked 的交互**：`text/event-stream` 那条用的是 chunked，而 `application/json` 那条带 `Content-Length`；截断只在后者出现。
2. **Workers 的 CPU/子请求预算**在冷 isolate 上被耗尽 → 响应被平台提前结束（这种情况下客户端看到的是"半个 body"而不是 5xx）。
3. 到了客户端的路径（运营商/代理）—— 但对照组 `cloudflare.com` 从不出这种断口，所以这一条最弱。

## 为什么不是"给客户端加重试"就完了

重试能掩盖它，我们已经在该这么做了（`#4498` 的修法）。但**服务端把一个 200 发出去、正文只写了一半**这件事本身是缺陷：它让调用方无法区分"你在骗我"和"网络在骗我"，而这两件事的处置完全不同。

<br/>
<hr/>

<details><summary>This repo is using Opire - what does it mean? 👇</summary><br/>💵 Everyone can add rewards for this issue commenting <code>/reward 100</code> (replace <code>100</code> with the amount).<br/>🕵️‍♂️ If someone starts working on this issue to earn the rewards, they can comment <code>/try</code> to let everyone know!<br/>🙌 And when they open the PR, they can comment <code>/claim #5245</code> either in the PR description or in a PR's comment.<br/><br/>🪙 Also, everyone can tip any user commenting <code>/tip 20 @Ikalus1988</code> (replace <code>20</code> with the amount, and <code>@Ikalus1988</code> with the user to tip).<br/><br/>📖 If you want to learn more, check out our <a href="https://docs.opire.dev">documentation</a>.</details>

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
- git commit -m "fix: bug(mcp): a 200 whose body is cut short — the worker is not the author ("
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
