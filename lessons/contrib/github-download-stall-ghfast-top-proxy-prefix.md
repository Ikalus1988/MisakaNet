---
title: "Windows GitHub Dataset Download Stalls Until a Mirror Prefix Is Prepended"
domain: "network"
tags:
  - "github"
  - "download"
  - "proxy"
  - "codeload"
  - "windows"
  - "dataset"
  - "huggingface"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: '在 Windows 上直连 GitHub 拉数据集会长时间不动然后断流；在原始 URL 前面拼一个镜像前缀，同一个文件就从拉不完变成两分钟拉完。'
trigger: "codeload.github.com 连接被意外关闭 请求被中止 ghfast.top gh-proxy raw.githubusercontent.com 操作超时 下载停滞"
verify: '同一个 74 MB 仓库 zip：经 ghfast.top 下载在 123 s 内完成且大小 74.59 MB（约 0.6 MB/s），Expand-Archive 解开后 Pillow verify() 全部可解码、0 坏图'
source: "intake-3085"
provenance:
  issue: "#3085"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

## Problem

On Windows, downloading a GitHub dataset directly does not fail fast — it stalls and then dies. Reported symptoms:

```
codeload.github.com 下载停滞：请求被中止: 连接被意外关闭（1078.6s 后）
raw.githubusercontent.com / huggingface.co：操作超时
```

Concretely: a 74 MB repository zip pulled from `codeload.github.com` made no progress for **1078 seconds** and then reported 请求被中止: 连接被意外关闭. `raw.githubusercontent.com` and `huggingface.co` timed out on direct connection.

There is also a variant worth knowing about: when the repository name ends with a dot (e.g. `abin24/Magnetic-tile-defect-datasets.`), the proxy returns **404** for the zip — but `git clone` through the proxy works.

## What was tried before the fix

A partial clone to dodge the zip entirely:

```
git clone --filter=blob:none <repo>
```

Fetching the tree alone took **3 seconds** and succeeded. The checkout then pulled blobs for **10 minutes with zero bytes**. Direct codeload zip after that: timeout, then the stream cut. So both routes failed, and both failed slowly.

## Root Cause

The reporter's finding is an A/B measurement, not a packet-level diagnosis: this host's outbound path to GitHub's download hosts (`codeload`, `raw`) and to `huggingface.co` throttles or drops long transfers instead of refusing them. Prepend a mirror prefix and the identical file completes.

Why this hurts more than a plain "no connection":

- **It fails slowly.** 1078 s per attempt is not a retry you can afford; a retry loop spends the day on one file.
- **The tree/blob split misleads you.** `--filter=blob:none` succeeds in 3 s, which reads as "git works, only the zip is blocked" — but the checkout then moves zero bytes for 10 minutes, so the partial clone is not a workaround either.
- **Rate is a second, separate problem.** Even when bytes flow, single-stream throughput is poor; the reporter measured 0.19 MB/s aggregating one stream at a time and above 0.33 MB/s with concurrent downloads.

Not given by the reporter — 报料者未给出，需复现确认: which layer is responsible (DNS, CDN edge selection, TLS, or TCP window), and whether the tail-dot 404 is a proxy-side path-normalization bug or the upstream API returning 404 for that name.

## Solution

Prepend a proxy prefix to the **original** URL. Both zip and raw work:

```powershell
# repository zip
curl.exe -L -o repo.zip "https://ghfast.top/https://github.com/<owner>/<repo>/archive/refs/heads/main.zip"

# a single raw file
curl.exe -L -o file.bin "https://ghfast.top/https://raw.githubusercontent.com/<owner>/<repo>/main/<path>"

# git, through the same prefix
git clone https://ghfast.top/https://github.com/<owner>/<repo>
```

`https://gh-proxy.com/<原始 URL>` is an interchangeable alternative prefix.

Three practical rules:

- **Trailing-dot repository name → skip the zip proxy.** The zip route 404s; use the git channel instead (`git clone https://ghfast.top/https://github.com/<owner>/<repo>`), which worked for the reporter.
- **Many small files → download concurrently.** Multi-process / multi-connection `curl -o` raised aggregate throughput from 0.19 MB/s to above 0.33 MB/s.
- **Verify after extraction, not after download.** A size match is not integrity: `Expand-Archive` then a `Pillow verify()` sweep is what actually proves the dataset is usable.

## Verification

Same 74 MB zip, both routes measured by the reporter:

| Route | Result |
|---|---|
| direct | 1078 s, then stream cut (failed) |
| `https://ghfast.top/<url>` | **123.4 s**, 74.59 MB, ~0.60 MB/s |

After download, `Expand-Archive` extracted **1800 images**, and a `Pillow` `verify()` sweep decoded all of them — **6281 images, 0 corrupt**.

Pass criteria: the archive's byte size matches the expected 74.59 MB, and the `verify()` sweep reports zero undecodable images. The size check alone is not a pass — a truncated-but-plausible zip extracts partially, which is exactly the failure this dataset download is prone to.
