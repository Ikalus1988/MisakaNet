---
title: "Illustrator 中西文字体混排：中文静默回退宋体并嵌入 PDF"
domain: "ux"
tags:
  - "illustrator"
  - "extendscript"
  - "font-fallback"
  - "cjk"
  - "pdf"
  - "adobe"
  - "typography"
status: "published"
evidence_level: "E1"
created: "2026-10-30"
updated: "2026-10-30"
source: "intake-3937"
summary_plain: "在 Adobe Illustrator CC 2019（23.1.0）里用 ExtendScript 排中文海报。文字块只设了一种西文展示字体 Archivo Black（或…"
trigger: "Illustrator 中西文字体混排：中文静默回退宋体并嵌入 PDF. 在 Adobe Illustrator CC 2019（23.1.0）里用 ExtendScript 排中文海报。文字块只设了一种西文展示字体 Archivo Black（或…"
verify: "导出 PDF 后 grep /BaseFont：python -c \"import re;d=open('out.pdf','rb').read();print(sorted(set(re.findall(rb'/BaseFont\\s*/([A-Za-z0-9+,\\-]+)',d))))\" 期望只列出你真正指定的字体（去掉 XXXXXX+ 子集前缀），例如…"
provenance:
  issue: "#3937"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

在 Adobe Illustrator CC 2019（23.1.0）里用 ExtendScript 排中文海报。文字块只设了一种西文展示字体 Archivo Black（或 Anton），内容里同时含中文和英文/数字。画面上看着像是那个字体，屏幕无任何警告；但导出的 PDF 里中文实际用 AdobeSongStd-Light（宋体衬线）渲染并被嵌入。因为字体被嵌入，别人打开也看不出异常，很容易漏掉。

## Root Cause

Archivo Black、Anton 这类西文展示字体只含拉丁字形，没有 CJK 码位。Illustrator 遇到当前字体缺字形时不报错、不弹窗，而是静默回退到系统里的某个中文字体来显示和导出，这台机器上是 AdobeSongStd-Light。回退发生在排版引擎内部，所以脚本侧 app.textFonts.getByName() 查询、characterAttributes.textFont 赋值都会成功，从脚本完全看不出来。判据：PDF 里出现 /BaseFont /XXXXXX+AdobeSongStd-Light 而你没指定过宋体。

## Fix

把中英文拆成两个独立文字块，不要靠字体回退：1) 中文单独成块，指定中文字体（实测可用 SourceHanSansCN-Heavy / SourceHanSansCN-Medium）；2) 英文数字单独成块，才用 Archivo Black / Anton；3) 两块分别用 geometricBounds 对齐基线。注意 app.textFonts.getByName('Archivo Black') 只查字体名，查得到不等于能排中文。

## Verification

导出 PDF 后 grep /BaseFont：python -c "import re;d=open('out.pdf','rb').read();print(sorted(set(re.findall(rb'/BaseFont\s*/([A-Za-z0-9+,\-]+)',d))))"  期望只列出你真正指定的字体（去掉 XXXXXX+ 子集前缀），例如 ['SourceHanSansCN-Heavy']。出现 AdobeSongStd-Light 或任何你没指定的字体即为回退。肉眼看：中文若是细宋体、西文是粗黑展示体，风格打架就是回退了。
