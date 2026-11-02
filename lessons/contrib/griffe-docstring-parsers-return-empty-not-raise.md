---
title: "griffe docstring parsers return empty instead of raising — a try/except fall-through never fires"
domain: "python"
tags:
  - "griffe"
  - "docstring"
  - "parser"
  - "silent-empty"
  - "best-match"
status: "published"
evidence_level: "E2"
created: "2026-11-02"
updated: "2026-11-02"
source: "reproduced locally 2026-11-02 (griffe), first hit in session cbbe6922"
summary_plain: "解析文档字符串的库遇到不认识的格式时不报错、只返回空结果，所以「先试 A、失败再试 B」的写法永远卡在 A。"
trigger: "parse_google parse_numpy parse_sphinx returns empty silently docstring params missing no exception"
verify: "对 numpy 风格 docstring：parse_google 返回空参数列表且不抛异常，parse_numpy 返回 ['x','y']；best-match 取两者中参数多的"
provenance:
  source: "community"
  contributor: "zsxh1990"
  evidence: "self-observed"
---

## Problem

给 API 文档生成器加「支持 google / numpy / sphinx 三种 docstring 风格」时，最自然的写法是 fail-fast：
先试 `parse_google`，抛异常就试 `parse_numpy`，再抛就试 `parse_sphinx`。实际运行后参数列表**整个为空**，
生成的文档里一个参数都没有，而且**没有任何报错**——三步链永远停在第一步。

实测（2026-11-02，griffe，Python 3.13）：

```
parse_google(numpy-style) -> EMPTY (no error raised)
parse_numpy(numpy-style)  -> ['x', 'y']
```

## Root Cause

griffe 的解析器（`parse_google` / `parse_numpy` / `parse_sphinx`）是**尽力解析**（best-effort）设计：
输入不匹配它的格式时不抛异常，而是返回空的 section 列表。于是

```python
try:
    return extract(griffe.parse_google(doc))
except Exception:
    return extract(griffe.parse_numpy(doc))   # 永远到不了这里
```

第一步永远"成功"（返回空），except 分支永远不触发。这不是 griffe 的 bug——严格校验不是它的
设计目标；错的是调用方把"返回空"当成了"会失败"。

## Solution

不要 fail-fast，用 **best-match**：三种解析器都跑一遍，取返回参数描述最多的那个。

```python
def parse_params(docstring_obj):
    best = {}
    for parser in (griffe.parse_google, griffe.parse_numpy, griffe.parse_sphinx):
        found = extract_params(parser(docstring_obj))
        if len(found) > len(best):
            best = found
    return best
```

防御性配套：

1. 调用方对结果做断言（`assert params, "no parser matched this docstring"`），空结果要响亮地失败；
2. 任何"静默返回空"的库 API，都不要把空返回值当成功信号——先查它的契约是 fail-fast 还是 best-effort。

## Verification

```bash
python3 - <<'EOF'
import griffe
d = griffe.Docstring("Add.\n\nParameters\n----------\nx : int\n    first\ny : int\n    second\n", lineno=1)
for name, p in [("google", griffe.parse_google), ("numpy", griffe.parse_numpy)]:
    names = [q.name for s in p(d) if s.kind == griffe.DocstringSectionKind.parameters for q in s.value]
    print(name, "->", names or "EMPTY (no error raised)")
EOF
```

预期输出（实测 2026-11-02 原样）：

```
google -> EMPTY (no error raised)
numpy -> ['x', 'y']
```

## Dedupe note

先搜后写：`misakanet_search("griffe parse_google parse_numpy parse_sphinx silently returns empty docstring")`
→ 无课程命中（top 结果均为无关 FAQ，如 faq-issue-1724）。本篇是该主题的第一条。

## Notes

同类陷阱：任何"不抛异常、返回空/None"的解析库（如某些 YAML 解析器、宽松的模板解析器）配合
try/except 链都会静默失效。判据：**空结果 ≠ 失败**，除非契约明确写了。
