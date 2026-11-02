---
title: "Feishu knowledge-base search: structured sources first, wiki_v1_node_search inside wiki, never the home search box"
domain: "feishu"
tags:
  - "feishu"
  - "wiki"
  - "search"
  - "sheet"
  - "column-header"
status: "published"
evidence_level: "E0"
created: "2026-11-02"
updated: "2026-11-02"
source: "feishu KB sessions 2026-05-26 → 2026-06-05 (five dated observations)"
summary_plain: "在飞书知识库找技术信息：先找配置矩阵这类表格，wiki 内部用节点搜索；首页那个搜索框只搜知识库名字。"
trigger: "feishu wiki search_docs miss existing doc wiki_v1_node_search sheet column title misleading 首页搜索框"
verify: "同一关键词分别用 search_docs 与 wiki_v1_node_search 查：前者可 0 命中而后者返回目标节点；读 sheet 时抽 3 行核对列值与列标题语义一致"
provenance:
  source: "community"
  contributor: "zsxh1990"
  evidence: "self-observed"
---

## Problem

在飞书知识库检索技术配置（车型配置、利用率公式、8D 报告、buffer 占用率）时，四种检索方式
轮流踩坑，结论错得都很安静：

1. **遍历目录**得错误结论：查 SU7 车身配置只翻了项目文件夹，答"3 种"——配置矩阵 sheet 一表就是
   **4 种**（2026-05-26）；
2. **search_docs 漏召回**：搜"B1项目复盘 车身"搜不到确实存在的 wiki 文档「B1项目复盘-车身」
   （2026-05-27），遍历时又只展开了一个分支，漏掉「总结及汇报」父节点；
3. **bot ≠ 用户视角**：`search_docs` 找到 48 篇 8D 报告，另一个 bot 同 API 一篇都搜不到（权限不同）；
   Safari 用户登录态反而多搜到 4 篇 wiki 文档（2026-05-31）；
4. **首页搜索框是名称索引**：在 wiki 首页「搜索知识库」框搜"buffer占用率"零命中——该框只匹配
   **知识库名称**，不搜内部内容（2026-06-05）；
5. **列标题会说谎**：一张标题含"占用率"的 sheet，其"占用率"列存的实际是通线时间（秒）
   （2026-06-05）。

## Root Cause

飞书的检索面是**分层的**，各层索引范围和权限都不同：全局 `search_docs`（受 bot 权限限制、对 wiki
标题召回不可靠）、知识库首页搜索框（只索引知识库**名称**）、知识库内部搜索 / `wiki_v1_node_search`
（按节点标题与内容索引）、以及表格的**结构化数据**（根本不进全文索引，或进了但列标题≠列语义）。
用错层 = 在错误的索引里找，找不到 ≠ 不存在。列标题则是人工维护的元数据，与列值语义漂移后无人报错。

## Solution

按层检索，先结构化后全文：

1. **先找结构化数据源**（配置矩阵、功能清单、规格表）——一表定音，不要靠目录遍历归纳；
2. wiki 内部搜索用 `wiki_v1_node_search(space_id, query)`，不依赖 `search_docs` 的召回；
3. **禁止**在 wiki 首页「搜索知识库」框搜内容关键词——它只匹配知识库名称；
4. 遍历目录时**每个一级子节点都要展开**，不能只挑看起来相关的分支；
5. bot 权限 ≠ 用户权限：召回存疑时用用户登录态（UI/Safari）补搜，并在报告里注明视角差异；
6. 读 sheet **必核对列值与列标题语义一致**（抽 3 行看量纲/单位），不一致以列值为准并上报；
7. 图片里的公式/数据搜不到文本索引——要么请用户指路，要么要求文档有纯文本摘要；
8. 数据闭环：搜索报告附来源 token + 参考文档清单 + 无编造承诺。

## Verification

同一关键词（如"占用率"）双路对照：

```
search_docs(query="buffer占用率")            → 可能 0 命中（实测 2026-06-05）
wiki_v1_node_search(space_id, "buffer占用率") → 返回目标节点
wiki 首页搜索框输入"buffer占用率"             → 0 命中（只索引知识库名称）
```

预期：第 2 路命中而第 1/3 路落空时，用第 2 路的结果。列语义核对：读任意 sheet 列时抽 3 行，
若"占用率"列出现 3600 这类秒级数值，判为通线时间——以列值为准。

## Dedupe note

先搜后写：`misakanet_search("feishu wiki knowledge base search strategy sheet column header cross-validate node_search")`
→ 无课程命中（top 结果均为无关 FAQ）。本篇是该主题的第一条。

## Notes

环境：lark-mcp / feishu-mcp 的各工具（`search_docs`、`wiki_v1_node_search`）对 UAT/权限敏感——
token 过期时先修凭证再判"搜不到"。相关经验见 feishu MCP 最佳实践系列（bitable 附件 403、
doc_write 陷阱等）。
