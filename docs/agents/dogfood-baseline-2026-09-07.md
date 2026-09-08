# Dogfood 基线：misaka-intake-bot 决策质量（2026-09-07）

> 目的：下发外部试点/赏金前，先证明 action 的决策质量达标（G4）。
> 方法：22 个真实形态 CI/运行失败样本（取材本仓 lesson/intake/CI 场景 +
> 噪音对照），`suggest-only`（不真提交），阈值 sim=0.45。

## 结果总览

| 指标 | 值 |
|---|---|
| 样本数 | 22 |
| hit（建议） | 9 |
| intake（新颖候选） | 11 |
| ignore（噪音） | 2 |
| 误配（hit 到不相关课程） | **0** |

## 逐样本

| # | 错误签名（脱敏截断） | decision | 命中课程 / 原因 |
|---|---|---|---|
| 1 | git credential helper 401 … github helper path mismatch | hit | git-credential-helper-gh-path-mismatch |
| 2 | git: 'credential-github' is not a git command | hit | lesson-06-git-push-credential-helper-403 |
| 3 | pip install ReadTimeoutError … corporate proxy pypi | hit | corporate-proxy-curl-timeout |
| 4 | ModuleNotFoundError: No module named 'requests' | intake | novel（无同栈课） |
| 5 | curl: (35) SSL connect error … wrong version number proxy | hit | corporate-proxy-curl-timeout |
| 6 | EACCES: permission denied, open '.npmrc' | hit | permission-denied-fix |
| 7 | npm ERR! code ELIFECYCLE … node-gyp rebuild failed | intake | novel |
| 8 | fatal: unable to access … 403 | intake | novel |
| 9 | TypeError: Cannot read properties of undefined (reading 'map') | intake | novel |
| 10 | ReferenceError: window is not defined (server.js) | intake | novel |
| 11 | Error from server: namespaces not found kubernetes | intake | novel |
| 12 | error[E0308] mismatched types rust cargo | intake | novel |
| 13 | FAILURE: Build failed … gradle :app:assemble | intake | novel |
| 14 | Terraform init failed backend state lock tfstate | hit | agent-state-database-lock-cleanup |
| 15 | MongoServerError: Authentication failed credentials | intake | novel |
| 16 | connection refused econnrefused 127.0.0.1:5432 postgres | hit | postgresql-connection-pool-exhaustion |
| 17 | The token is not valid: ghp_… checkout failed | hit | github-actions-composite-pitfalls |
| 18 | Docker build failed exit 137 oomkilled | intake | novel |
| 19 | SyntaxError: Unexpected token '}' in JSON | hit | json-parse-failure-handling |
| 20 | ENOSPC: no space left on device | intake | novel |
| 21 | https://example.com/callback | ignore | 纯 URL 噪音 |
| 22 | it broke | ignore | 签名过短（<10 字符） |

## 结论与达标判断

- **hit 全部对症**（9/9，含跨栈不误配：git/rust/gradle 各自归位）——v1.0 stack-aware
  命中门在本批样本上无 FP。
- **intake 均为真实新颖失败**（11/11 无现成课程覆盖：Mongo auth、docker OOM、gradle、
  E0308、ENOSPC…）——正是外部复用能扩充的语料面。
- **ignore 正确拦噪音**（URL/过短）。
- 对外部 pilot 的启示：命中率 ≈41%（9/22）已能给 CI 失败即时建议；未命中的一半
  会转化为 intake 候选 → 飞轮素材。

> 说明：样本为维护者构造（覆盖真实课程/真实长尾/噪音三态），非线上随机采样；
> 真实外部 pilot 的命中率取决于其错误分布与本仓课程域的重合度。
