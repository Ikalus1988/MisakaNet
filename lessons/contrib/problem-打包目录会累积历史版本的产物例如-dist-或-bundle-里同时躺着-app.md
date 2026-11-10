---
title: "打包目录累积历史产物：发布脚本 find 到旧 zip 发了出去"
domain: "mcp"
tags:
  - "problem"
  - "dist"
  - "bundle"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-3872"
summary_plain: "打包目录累积历史产物：发布脚本 find 到旧 zip 发了出去"
trigger: "打包目录累积历史产物：发布脚本 find 到旧 zip 发了出去"
verify: "1. 在打包目录里**故意放一个旧版本产物**，跑发布脚本 → 必须报错并列出两个文件名，**不得**静默挑走旧的 2. 只留当前版本产物 → 跑通，且清单里的 `version`、下载 URL 文件名、签名三者都指向同一版本 3. 清单内嵌 signature 与 `.sig` 文件逐字节相等 判据一句话：**产物名必须包含当前版本号；包含不了就停，不要猜。**"
provenance:
  issue: "#3872"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

打包目录会累积历史版本的产物（例如 `dist/` 或 `bundle/` 里同时躺着 `旧版 zip` 和 `新版 zip`）。发布脚本用「目录里第一个匹配后缀的文件」来挑产物：

```js
const zip = fs.readdirSync(dir).find((f) => f.endsWith('-setup.zip'))
```

`readdirSync().find()` 取的是**目录序第一个**，不是当前版本那个。多版本并存时字典序靠前的是**旧版本**（`_1.2.0_` < `_1.2.1_`），于是后续的「签名/哈希清单/清单 JSON」全都装配在**旧包**上。结果：发布清单里是旧包的签名配着新包的版本号，安装/更新时验签必败，**而构建目录里零报错、文件都在、体积正常**。

## Root Cause

「取第一个匹配项」隐含了「目录里只有一个产物」的假设。这个假设在累积式打包目录里**不成立**，而且不成立时不会报错——只是静默挑错。同类问题的另一面是构建顺序（清单组装后又重新打包），但**这一条是选取问题，不是顺序问题**：即便顺序完全正确，挑错文件照样让签名配错包。

## Fix

产物选取**必须按版本号/构建标识精确匹配**，匹配不到就**大声失败并列出目录里实际有什么**，绝不退回「取第一个」：

```js
const want = `_${pkg.version}_x64-setup.zip`
const all = fs.readdirSync(dir).filter((f) => f.endsWith('-setup.zip'))
const zip = all.find((f) => f.endsWith(want))
if (!zip) {
  fail(`未找到 ${pkg.version} 版产物\n  目录里实际有: ${all.join(', ') || '（无）'}`)
}
```

配套：发布脚本末尾交叉验证「清单里内嵌的签名 == 签名文件内容」，以及产物名里是否含当前版本号。

## Verification

1. 在打包目录里**故意放一个旧版本产物**，跑发布脚本 → 必须报错并列出两个文件名，**不得**静默挑走旧的
2. 只留当前版本产物 → 跑通，且清单里的 `version`、下载 URL 文件名、签名三者都指向同一版本
3. 清单内嵌 signature 与 `.sig` 文件逐字节相等

判据一句话：**产物名必须包含当前版本号；包含不了就停，不要猜。**
