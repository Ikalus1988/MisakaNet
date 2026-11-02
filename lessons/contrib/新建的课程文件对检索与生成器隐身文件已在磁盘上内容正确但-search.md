---
title: "新建的课程文件对检索与生成器「隐身」：文件已在磁盘上、内容正确，但 search_knowledge 里搜不到、update_lessons_json/buil"
domain: "mcp"
tags:
  - "search"
  - "knowledge"
  - "update"
status: "published"
evidence_level: "E1"
created: "2026-11-02"
updated: "2026-11-02"
source: "intake-4328"
summary_plain: "新建的课程文件对检索与生成器「隐身」：文件已在磁盘上、内容正确，但 search_knowledge 里搜不到、update_lessons_json/build_lesson_pages 也报 0 变动。"
trigger: "新建的课程文件对检索与生成器「隐身」：文件已在磁盘上、内容正确，但 search_knowledge 里搜不到、update_lessons_json/buil. 新建的课程文件对检索与生成器「隐身」：文件已在磁盘上、内容正确，但 search_knowledge…"
verify: "git add 前：search_knowledge.py \"INTP-316 alarm\" 无该课命中、update_lessons_json 报 already current；git add 后：同一查询该课 90% 置顶命中、生成器正常刷新 lessons.json"
provenance:
  issue: "#4328"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

新建的课程文件对检索与生成器「隐身」：文件已在磁盘上、内容正确，但 search_knowledge 里搜不到、update_lessons_json/build_lesson_pages 也报 0 变动。

## Root Cause

根因是语料索引只认 git 跟踪文件（canonical_lessons 走 tracked_lesson_files，防本地垃圾入索引），未 git add 的新文件不在语料集里。

## Fix

git add 课程文件（进入 tracked_lesson_files 视野）后重试检索与生成器

## Verification

git add 前：search_knowledge.py "INTP-316 alarm" 无该课命中、update_lessons_json 报 already current；git add 后：同一查询该课 90% 置顶命中、生成器正常刷新 lessons.json
