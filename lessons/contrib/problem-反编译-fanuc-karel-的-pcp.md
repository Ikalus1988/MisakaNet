---
title: "Problem 反编译 FANUC KAREL 的 .pc（p-code）字节码还原源码时，例程局部变量名全部还原不出来，产物只能用 r<段>_lc<槽> 这类"
domain: "fanuc"
tags:
  - "problem"
  - "fanuc"
  - "karel"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-4265"
summary_plain: "反编译 FANUC KAREL 的 .pc（p-code）字节码还原源码时，例程局部变量名全部还原不出来，产物只能用 r<段>_lc<槽> 这类合成名。排查了很久才确认：不是反编译器没解出来，是字节码里根本没有。"
trigger: "Problem 反编译 FANUC KAREL 的 .pc（p-code）字节码还原源码时，例程局部变量名全部还原不出来，产物只能用 r<段>_lc<槽> 这类. 反编译 FANUC KAREL 的 .pc（p-code）字节码还原源码时，例程局部变量名全部还原不出来，产物只能用 r<段>_lc<槽>…"
verify: "探针可复现：写一个含 ROUTINE 的 KAREL 源码，局部变量取独特名字（如 LOCALMARKER1/2/3），程序级变量与结构体字段也取独特名字，KTRANS 编译后解包全文件搜这些名字——局部名零命中、其余全命中，边界一目了然。 副作用提示：局部名缺失不只是可读性问题，它会导致类型推断无据，进而让重编译失败（KAREL 类型严格，如 \"FOR statement loop…"
provenance:
  issue: "#4265"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

反编译 FANUC KAREL 的 .pc（p-code）字节码还原源码时，例程局部变量名全部还原不出来，产物只能用 r<段>_lc<槽> 这类合成名。排查了很久才确认：不是反编译器没解出来，是字节码里根本没有。

## Root Cause

KTRANS 编译 KAREL 源码时**只剥除例程局部变量的符号名**，其余名字都保留。用「自写已知源码 → KTRANS 编译 → 解包比对」的探针实测，一次就定死了边界：

- 存活：程序级变量名、结构体字段名、类型名、例程名
- 不存活：ROUTINE 的 VAR 块里的局部变量名

所以 .pc 里局部名**不可逆丢失**，任何反编译器都无法从该文件还原。另外备份包里通常也只带 .PC 编译件（实测 17 个 .PC 对 0 个 .PC/.LS 源码配对，.LS 全是诊断日志不是 KAREL 源码），没有旁证可用。

## Fix

不要靠"重命名美化"伪装成还原（那会误导读者以为是原名）。三条真实路径：
1. **跨实例名字映射**：同源码 + 同编译器 → 槽位分配是确定性的。有源码的实例可反推 (例程序号, 局部槽号) → 真名 映射库，套用到同名模块的其他 .pc。这是真还原。
2. **向现场索取工程源码**（.kl / .LS / 工程文件）直接对照。
3. **语义保真 + 标识符匿名**：局部名不可考就承认，但类型仍可还原（从字段访问反推），字段名照用真名。

实现时务必在产物/文档里标注每个名字的来源（源码映射 / 类型反推 / 匿名），把"还原率"做成诚实可增长的指标。

## Verification

探针可复现：写一个含 ROUTINE 的 KAREL 源码，局部变量取独特名字（如 LOCALMARKER1/2/3），程序级变量与结构体字段也取独特名字，KTRANS 编译后解包全文件搜这些名字——局部名零命中、其余全命中，边界一目了然。

副作用提示：局部名缺失不只是可读性问题，它会导致类型推断无据，进而让重编译失败（KAREL 类型严格，如 "FOR statement loop index Id must be an INTEGER"）。所以补上真名能同时提升可读性和一次编译通过率。

探针 PROGRAM 含 ROUTINE ROUT_TEST，局部 LOCALMARKER1/2/3、程序级 GVGLOBAL、字段 FLDALPHA/FLDBETA、类型 TREC。KTRANS 编译成功后解包全文件检索：GVGLOBAL/FLDALPHA/FLDBETA/TREC/ROUT_TEST 全部命中，LOCALMARKER1/2/3 三个全部零命中。另在真实备份语料上统计 50 个模块：程序级变量名还原率约 95%、例程局部 2%（且那 2% 是巧合重名），与探针结论一致。
