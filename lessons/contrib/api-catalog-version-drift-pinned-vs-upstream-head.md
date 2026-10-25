---
domain: "nodejs"
title: "Verify a version-dependent API catalog against the pinned package, not upstream HEAD"
tags:
  - "nodejs"
  - "npm"
  - "dependency-version"
  - "verification"
  - "api-catalog"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "所谓“权威 API 清单”会随版本变：按用户实际安装的那个版本核对，否则会拿一个还没人装得上的未来当真理。"
trigger: "maintainer said slot key did not exist verifying against upstream master instead of pinned package"
verify: "同一 key 在 node_modules 里的 pinned 包与上游 master 上结论相反时必须报告漂移；改为运行时探测后发布门禁落在宿主接受的 key 上且 FAIL=0"
source: "intake-2772"
provenance:
  issue: "#2772"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# Verify a version-dependent API catalog against the pinned package, not upstream HEAD

## Problem

"权威" API 清单有两个来源，它们互相矛盾，而选错来源会**把结论反过来**：

| 来源 | 条目数 | key `A` | key `B` |
|---|---|---|---|
| 锁定的 npm 包（用户实际安装的东西） | 42 | 存在 | **不存在** |
| SDK 仓库的 upstream `master` | 92 | **不存在** | 存在 |

一位维护者报告"key `A` 不存在，用 `B`"——这句话对锁定包是真的。开发者却去拉了 upstream `master`，在里面找到了 `A`、没找到 `B`，于是回复维护者说人家错了。两个人都在核对同一个"单一事实来源"，却得到了相反的答案。

之后开发者又用 upstream 的集合搭了一套验证 harness，并据此确认代码是"对的"——这是第四个错误判断，因为安装锁定包的用户根本没有那个位置。

## Root Cause

"权威清单"不是单一的物件，它是**依赖版本**的：

- **锁定的包**是用户宿主里实际存在的东西；
- **upstream HEAD** 是 SDK 仓库今天包含的东西。

对着 upstream HEAD 验证，证明的是代码匹配一个**还没有任何用户拥有**的未来；对着锁定包验证，证明的是代码匹配实际会运行的东西。当两者漂移时，一个判断可以对其一为真、对其二为假——而用户永远只拿到锁定包。

两个人都没错，是"清单"这个词省掉了版本，才让双方各自都既对又错。

## Solution

**说清楚你是对着哪个版本验证的，并优先用用户安装的那个版本。**

```bash
# 用户实际拥有的
node -e "const p=require('./node_modules/<sdk>/package.json'); console.log(p.version)"
grep -oE "\"[a-z][a-z0-9._]+\"" node_modules/<sdk>/lib/*.js | sort -u | wc -l

# 上游拥有的（用于判断漂移，不是用于判断真相）
gh api repos/<org>/<repo>/contents/<path-to-catalog> --jq .content | base64 -d | grep -cE "^  key: '"
```

**报告漂移，而不是把两个列表合并。** 合并出来的清单会让代码对着一个没有任何宿主拥有的目录去验证——那正是"第四个错误判断"的形态。

**更好的做法：干脆不要硬编码 key。** 当集合本身依赖版本时，在运行时探测，只注册宿主接受的东西：

```js
const accepted = Object.keys(host?.slots ?? {})
for (const key of CANDIDATE_KEYS) {
  if (accepted.includes(key)) register(key)
}
```

## Verification

- **漂移的判据**：锁定的包有 key `B`、没有 key `A`；上游 `master` 有 `A`、没有 `B`。同一个探测产生相反结果，这就是漂移——报告它，不要取平均，也不要合并成"超集"。
- **修复后**：改为运行时探测而不是硬编码 key，发布门禁落在 `B` 上并通过，`FAIL=0`。
- **通过判据**：代码注册的每一个 key 都在锁定安装里存在；两个清单不一致时，结论必须点名两个版本，而不是只说"清单里有/没有"。
