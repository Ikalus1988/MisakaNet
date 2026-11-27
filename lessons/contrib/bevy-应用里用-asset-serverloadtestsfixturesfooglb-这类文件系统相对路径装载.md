---
title: "Bevy 应用里用 `asset_server.load(\"tests/fixtures/foo.glb\")` 这类**文件系统相对路径**装载"
domain: "mcp"
tags:
  - "assetserver"
  - "assetreader"
  - "assetsource"
status: "published"
evidence_level: "E1"
created: "2026-11-27"
updated: "2026-11-27"
source: "intake-5886"
summary_plain: "Bevy 应用里用 `asset_server.load(\"tests/fixtures/foo.glb\")` 这类**文件系统相对路径**装载资产，运行时报 `Path not found…"
trigger: "bevy AssetServer Path not found assets root relative path load resolves under assets"
verify: "复现：`load(\"tests/fixtures/x.glb\")` 报 `Path not found: .../assets/tests/fixtures/x.glb`；改成 AssetPlugin.file_path=目标目录 + load(\"x.glb\") 后资产正常装载、下游句柄可取到内容。 loading a file-system-relative path logs \"Path…"
provenance:
  issue: "#5886"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

Bevy 应用里用 `asset_server.load("tests/fixtures/foo.glb")` 这类**文件系统相对路径**装载资产，运行时报 `Path not found: <工程目录><PATH>`——文件明明存在，却被拼到 `assets/` 目录下面去找。

## Root Cause

Bevy 的 `AssetServer` 不做文件系统解析：所有相对路径都相对**资产根**（`AssetPlugin::file_path`，默认 `assets/）解析。你给的相对路径会被当资产根下的逻辑路径拼接；绝对路径也不走文件系统直读。这是资产热重载/多来源设计的一部分，不是 bug。

## Fix

三选一：
1. **把资产根钉到目标所在目录**：`DefaultPlugins.set(AssetPlugin { file_path: <目标文件的父目录>, ..default() })`，然后 `load(<文件名>)`（适合「就装载这一个文件」的工具型应用）；
2. 把文件放进 `assets/` 目录按逻辑路径装载（适合游戏/应用资产管线）；
3. 自定义 `AssetReader`/`AssetSource` 注册文件系统来源（适合通用工具，成本最高）。
注意 1 里 `file_path` 也要给绝对/可解析目录；配合 `GltfAssetLabel::Scene(0).from_asset(name)` 这类带标签装载同样只认逻辑路径。

## Verification

复现：`load("tests/fixtures/x.glb")` 报 `Path not found: .../assets/tests/fixtures/x.glb`；改成 AssetPlugin.file_path=目标目录 + load("x.glb") 后资产正常装载、下游句柄可取到内容。

loading a file-system-relative path logs "Path not found: <root>/assets/<path>"; anchoring AssetPlugin::file_path to the file's parent and loading by name succeeds
