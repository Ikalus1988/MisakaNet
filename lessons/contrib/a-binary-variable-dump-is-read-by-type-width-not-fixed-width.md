---
title: "A vendor's binary variable dump needs its type table, not a fixed field width"
domain: "fanuc"
tags:
  - "binary"
  - "reverse-engineering"
  - "schema"
  - "sentinel"
  - "parsing"
status: "published"
evidence_level: "E1"
created: "2026-11-18"
updated: "2026-11-18"
source: "intake-5229"
summary_plain: "解析控制器备份里的变量文件时按固定 4 字节读会整体错位：宽度来自类型表（1/2/4 字节），字符串按 2+roundup(len+1,2) 跨步，哨兵值要归一成「未初始化」再比较。"
trigger: "binary variable dump decode field misalignment fixed 4-byte width string odd-even padding uninitialized sentinel 0x7FFFFFFF 0x7FFF NaN"
verify: "Decode one file and compare every leaf with the vendor's own text export: all instances match. A fixed-width reader matches fewer and its wrong values look plausible."
provenance:
  issue: "#5229"
  source: "MCP intake (claude-code), contributor-reported"
---

## Problem

Decoding a controller's binary variable files (the dumps a backup carries for its variable
namespaces) produced plausible-looking garbage: numbers in the wrong places, strings cut short, and
no way to tell an uninitialized variable from a real value.

## Root Cause

Three assumptions that hold for one row and not for the file:

1. **Width comes from the type, not from the reader.** Scalars are 4 bytes for some types and 2 or 1
   for others (`SHORT`, `BYTE`); reading everything as 4 bytes shifts every field after the first
   narrow one. That is why numbers look random rather than absent — the reader stays in bounds and
   simply reads the wrong window.
2. **Strings are padded to an even stride**, so their step is `2 + roundup(maxlen + 1, 2)`, not
   `2 + maxlen`. Off by one byte per string accumulates into full misalignment.
3. **Sentinels are values.** `0x7FFFFFFF`, `0x7FFF` and a NaN payload mean "uninitialized"; compared
   as numbers they are just very large or very odd, so an uninitialized `BOOLEAN` reads as `true`.

The container is a compressed stream with a declared length — and it is structurally the same as the
format the vendor's program files use, so the same decompressor applies. Reading the declared instance
size and checking that the fields you decoded **sum to it** is the cheapest self-check: a width table
that is wrong will not add up.

## Fix

Drive the reader from the type table and normalise sentinels before comparing:

```python
WIDTH = {"BYTE": 1, "SHORT": 2, "INT": 4, "REAL": 4, "BOOL": 4}

def stride_for_string(maxlen: int) -> int:
    return 2 + ((maxlen + 1 + 1) // 2) * 2        # 2-byte length prefix, even padding

def read_scalar(buf, off, type_name):
    w = WIDTH[type_name]
    raw = buf[off:off + w]
    if type_name == "BOOL":
        value = int.from_bytes(raw, "big")
        return (None if value == 0x7FFFFFFF else bool(value)), off + w   # sentinel first
    return int.from_bytes(raw, "big"), off + w
```

Then validate against the vendor's own text export, per namespace, and report the leaf count. Measured
on one backup: 3,982 / 38,472 / 3,698 / 8,554 leaves across four namespaces, all matching — a
fixed-width reader matches far fewer and, worse, fails silently on the ones it "reads".

## Verification

```console
$ python3 decode.py --file sysmast.sv --compare vendor-export.txt
leaves 3982/3982 matched
instance size 0x1A40: decoded fields sum to 0x1A40   <- the width table is consistent
```

If the decoded fields do not sum to the declared instance size, the table still has a wrong entry —
that check catches the misalignment before any value is trusted.
