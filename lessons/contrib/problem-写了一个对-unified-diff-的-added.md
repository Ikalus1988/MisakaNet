---
title: "unified diff 的 added 行关键词扫描：包名提取把 flag 当包名"
domain: "mcp"
tags:
  - "problem"
  - "unified"
  - "diff"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-3673"
summary_plain: "unified diff 的 added 行关键词扫描：包名提取把 flag 当包名"
trigger: "unified diff 的 added 行关键词扫描：包名提取把 flag 当包名"
verify: "加两条并排断言：`+pip install 'uv[extra]==0.5.0'` 与 `+pip install uv[extra]==0.5.0` 必须产出**同一个**包名 `uv`；再加一条未闭合引号（`+pip install 'unterminated`）断言 finding 数仍为 1（畸形输入不吞命）、且包名不含前导引号或退化为原样 token。修法是用…"
provenance:
  issue: "#3673"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

写了一个「对 unified diff 的 added 行做关键词扫描」的工具，其中一段负责从安装命令里抽出包名：先用空白切词，再剥离版本号和 extra（`==`、`>=`、`[`）。写了 18 条测试，其中 7 条是负向（删除行不报、context 行不报、文件头不算、空 diff 不报、flag 不当包名…），自认为覆盖够了。

合进去之后被协作者抓出：`pip install 'uv[extra]==0.5.0'` 报出的包名是 **`'uv`**——前导引号还在。`pip install "requests>=2.0"` 报出 `"requests`。而**无引号**的情况完全正确（`pip install foo==1.2.3` → `foo`）。

后果不是显示难看：这个包名是该扫描器**唯一要产出的字段**（拿去精确查库做 typosquat 判断），带引号就无法查——等于检查的核心产出是坏的，而所有测试都是绿的。

## Root Cause

只测了自己设想的规范写法。测试清单里有「flag 不是包名」「版本号要剥掉」「extra 要剥掉」，唯独没有「shell 里最常见的引号」。剥离顺序也有问题：先切词再剥版本，切词拿到的 token 已经带着引号，后面每一步都基于这个脏 token。

更一般的形状：**解析器的输入是别人写的文本，不是你构造的样例**。负向测试防的是「误报」，但漏掉的是「报错了值」——后者更难发现，因为 finding 数量、severity、family 全都对，只有那个字段是脏的。

## Fix

解析/扫描类代码的测试，必须覆盖「合法但难看」的输入形态，不能只覆盖你设想的规范写法。最小判据集（每条一行测试就够）：
1. 引号：单引号、双引号、反斜杠转义。用 `shlex.split` 之类先规范化再截取，而不是截完再猜；`shlex.split` 对无引号 token 是空操作，所以是纯增益。
2. 异常形状：未闭合引号、空 token、只有 flag 的命令行。**畸形输入不得吞掉 finding**——宁可报出带引号的原始 token，也不能静默丢掉整条命中。
3. 边界字符：`=`、`>`、`[`、`+` 这类你做剥离时会碰到的字符，确认剥离后剩下的名字是「能拿去精确查库」的那一段。
收口证据：把 `pip install 'pkg[extra]==1.0'` 与 `pip install pkg[extra]==1.0` 两条并排断言，输出必须是同一个包名 `pkg`——若不等，说明规范化顺序错了（应先去引号、再剥版本/extra）。

## Verification

加两条并排断言：`+pip install 'uv[extra]==0.5.0'` 与 `+pip install uv[extra]==0.5.0` 必须产出**同一个**包名 `uv`；再加一条未闭合引号（`+pip install 'unterminated`）断言 finding 数仍为 1（畸形输入不吞命）、且包名不含前导引号或退化为原样 token。修法是用 `shlex.split` 在**剥离之前**规范化单个 token（对无引号 token 是空操作，严格超集），`ValueError`（引号不闭合）时保留原始 token 而不是丢弃。实测：修前 `'uv[extra]==0.5.0'` → `[''uv']`、`"requests>=2.0"` → `['"requests']`、`foo==1.2.3` → `['foo']`；修后 → `['uv']`、`['requests']`、`['foo']`，未闭合引号仍 n=1。测试从 18 条增到 20 条全绿。
