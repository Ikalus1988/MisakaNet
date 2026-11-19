---
title: "重建一个含中文目录/文件名（如 图片和附件\\xxx.png）的 zip 交付物时两处翻车：① Python zipfile 默认把中文条目名写成 UTF-8+U"
domain: "windows"
tags:
  - "xxx"
  - "png"
  - "zip"
status: "published"
evidence_level: "E1"
created: "2026-11-19"
updated: "2026-11-19"
source: "intake-5196"
summary_plain: "重建一个含中文目录/文件名（如 图片和附件\\xxx.png）的 zip 交付物时两处翻车：① Python zipfile 默认把中文条目名写成 UTF-8+UTF-8 flag，而待“重建”的旧 zip 是 GBK 编码、无…"
trigger: "zip 重建 中文文件名 GBK 乱码 os.replace WinError 17 跨盘"
verify: "重开 zip：条目数=预期、首条目（md）与源文件字节一致、每条目名 cp437→gbk 还原为正确中文 = PASS"
provenance:
  issue: "#5196"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

重建一个含中文目录/文件名（如 图片和附件\xxx.png）的 zip 交付物时两处翻车：① Python zipfile 默认把中文条目名写成 UTF-8+UTF-8 flag，而待“重建”的旧 zip 是 GBK 编码、无 flag——同一台中文 Windows 上两代产物条目名编码不一致，解压后可能乱码、与原件不可比；② 用 os.replace 把 C: 盘临时 zip 换到 D: 盘目标路径报 WinError 17「系统无法将文件移动到不同的驱动器」。

## Root Cause

① zipfile.ZipInfo._encodeFilenameFlags 对非 ASCII 名强制 filename.encode('utf-8') 并置 0x800 UTF-8 flag；中文 Windows 的解压工具对无 flag 条目按本地 GBK（cp437+GBK 还原）解码，两代 zip 编码不一致导致“重建”并非字节级同构。② os.replace 仅支持同卷原子替换，跨盘直接抛 WinError 17。

## Fix

① 重建前先判定旧 zip 条目名编码（zipfile 按 cp437 解码后再 encode('gbk') 能还原 = GBK 无 flag）；写入时 monkeypatch ZipInfo._encodeFilenameFlags 使非 ASCII 名返回 filename.encode('gbk') 且 flag_bits 清掉 0x800，与原件同构。回读用 zipfile.ZipFile(..., metadata_encoding='gbk') 或 cp437→gbk 还原校验。② 临时文件写到目标同盘（path + '.tmp'）再 os.replace 原子替换；确需跨盘用 shutil.move。

## Verification

重开 zip：条目数=预期、首条目（md）与源文件字节一致、每条目名 cp437→gbk 还原为正确中文 = PASS
