---
title: "Symptom GUI 自动化的 OCR 突然「读不到目标面板」：词表全是无关内容（3D 视口纹理/别的窗口/工具栏），锚点点击也全部落空或点进无关区域；但用"
domain: "mcp"
tags:
  - "gui"
  - "ocr"
status: "published"
evidence_level: "E1"
created: "2026-11-19"
updated: "2026-11-19"
source: "intake-5165"
summary_plain: "GUI 自动化的 OCR 突然「读不到目标面板」：词表全是无关内容（3D 视口纹理/别的窗口/工具栏），锚点点击也全部落空或点进无关区域；但用 PrintWindow…"
trigger: "ImageGrab 屏幕截屏被遮挡 OCR 读到背后窗口 点击落空 3D视口 PrintWindow 对照"
verify: "同一矩形双后端各拍一张：screen 拍到背后窗口、printwindow 拍到目标内容 = 中招（FAIL 现状）；把面板置顶/取消遮挡后两后端一致，OCR 词表恢复目标面板特征词 = 修复（PASS）。 同矩形双后端对照：screen≠printwindow=中招；一致且 OCR 恢复特征词=PASS"
provenance:
  issue: "#5165"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

GUI 自动化的 OCR 突然「读不到目标面板」：词表全是无关内容（3D 视口纹理/别的窗口/工具栏），锚点点击也全部落空或点进无关区域；但用 PrintWindow 直取目标窗口句柄截图，内容明明完整可见。表象像「面板没开/按钮不响应」，实际读屏和点击都打在了被遮挡窗口背后的可见层上。

## Root Cause

屏幕区域截屏（ImageGrab 一类）拍的是**该矩形当前可见的像素**：目标子窗口被同进程的其他面板（如 3D 视口）遮挡、或处于自动隐藏/被盖住状态时，截到的是背后窗口的内容，OCR 读垃圾；合成点击走屏幕坐标，同样点在最上层可见窗口上。窗口句柄本身的内容并未丢失——PrintWindow 渲染窗口自身、与遮挡无关，能拍到真身。

## Fix

读屏改走 PrintWindow 类后端（渲染目标 hwnd 自身再裁剪），被遮挡也能拍；并把「同一矩形、双后端对照」做成中招判据（screen 后端≠printwindow 后端 ⇒ 面板被遮挡，先修可见性/窗口归属再调自动化）。注意合成**点击**仍打屏幕坐标，需要目标面板实际可见（或改走窗口消息/键注入）。

## Verification

同一矩形双后端各拍一张：screen 拍到背后窗口、printwindow 拍到目标内容 = 中招（FAIL 现状）；把面板置顶/取消遮挡后两后端一致，OCR 词表恢复目标面板特征词 = 修复（PASS）。

同矩形双后端对照：screen≠printwindow=中招；一致且 OCR 恢复特征词=PASS
