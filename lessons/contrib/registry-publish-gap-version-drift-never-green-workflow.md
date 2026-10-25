---
domain: "ci"
title: "One registry silently five versions stale: no publish workflow existed and the release gate had never been green"
tags:
  - "ci"
  - "release"
  - "npm"
  - "pypi"
  - "version-drift"
  - "oidc"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "三个发布渠道里有一个停更了，因为仓库里根本没有对应的发布流程，而 CI 徽章全是绿的，看不出用户装到的是旧版本。"
trigger: "npm view version behind tag missing publish workflow registry version drift never green"
verify: "npm view <pkg> version、PyPI JSON 的 version、git describe --tags --abbrev=0 三者一致；且 gh run list 里该 publish workflow 至少有一次真正成功的运行"
source: "intake-2808"
provenance:
  issue: "#2808"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# One registry silently five versions stale: no publish workflow existed and the release gate had never been green

## Problem

一个发布到多个 registry（PyPI + npm + 容器 registry）的项目，其中一个渠道悄悄停更了。npm 落后 **五个 minor 版本**，从那个渠道安装的用户拿到的是**一年前**的构建，其中包含四个 release 之前就已修掉的 bug。

仓库里任何现有信号都发现不了这件事：diff 里的版本号 bump 都在，CI 徽章全绿，changelog 也照常更新——每一件可见的事都是真的。

## Root Cause

**那个渠道根本没有 publish workflow。** 另外两个渠道各有 `publish-*.yml`，在打 tag 时触发；这一个从来只有手工发布，而手工步骤在某次之后悄悄停了。

registry 之间的版本漂移在仓库内部是不可见的：diff 显示版本号在落地，CI 显示绿色，两者都为真。缺口只在有人问"用户真正安装的那个东西更新了吗"的时候才出现。

同一失败还有第二、更隐蔽的形态：**一个看起来是发布门禁的 workflow 从来没有通过过一次**——每次运行都是红的，或者"绿"只是因为跳过了真正重要的那部分。正因为它在每一次运行里都是红的，"发布那一次也是红的"就看起来完全正常，没人会去追。

## Solution

1. **每一条用户真正会走的安装路径，都要有自己的 publish workflow**，由 tag 驱动，并且和测试/smoke 用同一条命令做门禁。不要允许任何一个 registry 停留在"只靠手工"的状态——手工步骤一定会停，而且停的时候没有任何信号。
2. **发布后去查 registry，而不是查 CI 徽章**。`npm view <pkg> version` 和 PyPI 的 JSON endpoint 都能直接告诉你线上版本，把它和 tag 对比。
3. **信任一个门禁之前，先看它的历史**：这个检查通过过吗？一个从来没绿过的 workflow 不是任何东西的证据；一个永远红的 workflow 会让"发布时红"看起来正常。
4. **优先用短时 OIDC 发布**（npm trusted publishing）代替长期 registry token：没有要存、要轮换的密钥，provenance attestation 还是免费的。如果必须用 token，它属于 CI secret store，永远不进仓库、不进 shell history。

```bash
# 线上实际版本
npm view <pkg> version
curl -sS "https://pypi.org/pypi/<pkg>/json" | python3 -c "import json,sys; print(json.load(sys.stdin)['info']['version'])"

# 应该是多少
git describe --tags --abbrev=0

# 这个门禁到底成功过没有
gh run list --workflow=publish-npm.yml --limit 20
```

## Verification

- **修复前**：把 `npm view` / PyPI JSON 报出的版本与 git tag 对比，发现其中一个渠道差五个版本；`gh run list --workflow=<publish.yml>` 显示有两个 workflow **从未成功过一次**。
- **修复后**：补上缺失的 tag 驱动的 publish workflow（OIDC，不存 token），下一个 tag 发布成功，registry 返回新版本并带 SLSA provenance attestation。判据是**取回发布出来的 tarball 检查内容**，而不是读 CI 的绿色结论。
- **通过的判据**：三个渠道的线上版本都等于 tag，且该 publish workflow 的历史里至少有一次真正发布了产物的成功运行。
