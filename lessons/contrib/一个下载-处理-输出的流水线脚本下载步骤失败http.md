---
title: "一个「下载 → 处理 → 输出」的流水线脚本，下载步骤失败（HTTP 403），但后续步骤**照常跑完了**，还打印了成功信息： 下游拿到的不是这次下载的"
domain: "windows"
tags:
  - "http"
status: "published"
evidence_level: "E1"
created: "2026-11-21"
updated: "2026-11-21"
source: "intake-4900"
summary_plain: "一个「下载 → 处理 → 输出」的流水线脚本，下载步骤失败（HTTP 403），但后续步骤**照常跑完了**，还打印了成功信息： ``` [1/3] 在线地址，用 yt-dlp 拉下来… ERROR: unable to…"
trigger: "一个「下载 → 处理 → 输出」的流水线脚本，下载步骤失败（HTTP 403），但后续步骤**照常跑完了**，还打印了成功信息： 下游拿到的不是这次下载的. 1/3] 在线地址，用 yt-dlp 拉下来… ERROR: unable to download video data: HTTP Error 403…"
verify: "改之前：403 之后静默用了旧文件，报「✓ 0.9 MB」，抽帧得到上一个视频。 改之后：403 之后直接 throw，并指出「目录里有旧文件 X，但那是上一次的，没用它」。 **第二条经验**：同一条命令重试一次就通了（第一次 403，第二次成功）。**偶发的 403 不能作为「这条路不通」的结论。** 加 `--cookies-from-browser` 反而可能失败在浏览器 cookie…"
provenance:
  issue: "#4900"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

一个「下载 → 处理 → 输出」的流水线脚本，下载步骤失败（HTTP 403），但后续步骤**照常跑完了**，还打印了成功信息：

```
[1/3] 在线地址，用 yt-dlp 拉下来…
      ERROR: unable to download video data: HTTP Error 403: Forbidden
      [download]  58.6% of 13.64MiB
      ✓ 0.9 MB                          ← 假的
[2/3] 抽 8 帧拼网格…
      时长 10 秒 | codec_name=h264 width=1280 height=720    ← 这是上一个视频
[3/3] 跳过转文字
```

下游拿到的不是这次下载的文件，而是**缓存目录里上一次的旧文件**。

## Root Cause

脚本的中间产物查找逻辑是：

```powershell
$视频 = Get-ChildItem $工作目录 -Filter '看视频-*.mp4' |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
```

**「目录里最新的匹配文件」不等于「这一次产出的文件」。**

下载失败时，上一次运行留下的文件还躺在同一个目录里，`Select -First 1` 拿的就是它。后续所有步骤都基于一个错误的输入跑完，全程没有任何一步报错。

这是「假成功」：**比直接失败更坏**，因为失败会让人停下，假成功会让人一路错到底。

## Fix

**给「这次的产出」加时间下限。**

```powershell
$下载开始 = Get-Date
# ... 执行下载 ...
$视频 = Get-ChildItem $工作目录 -Filter '看视频-*.mp4' |
        Where-Object { $_.LastWriteTime -ge $下载开始.AddSeconds(-2) } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
if (-not $视频) {
    $旧文件 = Get-ChildItem $工作目录 -Filter '看视频-*.mp4' | Select-Object -First 1
    throw "下载没产出文件。目录里有旧文件 $($旧文件.Name)（$( $旧文件.LastWriteTime)），但那是上一次的，没用它。常见原因：HTTP 403 / 地区限制 / 链接失效。"
}
```

`-2 秒` 是给文件系统时间戳精度留的余量。

**没有新文件就明确 throw。** 报错信息里带上「有个旧文件但我没用它」，这样人一眼就知道发生了什么。

## Verification

改之前：403 之后静默用了旧文件，报「✓ 0.9 MB」，抽帧得到上一个视频。

改之后：403 之后直接 throw，并指出「目录里有旧文件 X，但那是上一次的，没用它」。

**第二条经验**：同一条命令重试一次就通了（第一次 403，第二次成功）。**偶发的 403 不能作为「这条路不通」的结论。** 加 `--cookies-from-browser` 反而可能失败在浏览器 cookie 数据库被占用（`Could not copy Chrome cookie database`），要先把浏览器关掉。
