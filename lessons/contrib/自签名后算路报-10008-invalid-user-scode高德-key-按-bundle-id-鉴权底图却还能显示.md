---
title: "自签名后算路报 10008 INVALID_USER_SCODE：高德 key 按 Bundle ID 鉴权，底图却还能显示"
domain: "mobile"
tags:
  - "amap"
  - "sidestore"
  - "bundle-id"
  - "10008"
  - "invalid-user-scode"
  - "signing"
  - "ios"
status: "published"
evidence_level: "E1"
created: "2026-10-31"
updated: "2026-10-31"
source: "intake-4173"
summary_plain: "SideStore 装好 App，点「回家」/选目的地，算路直接失败： ``` 算路失败: CalculateRideRouteError:13(1-2) (10008:INVALID_USER_SCODE)(code 13) ```…"
trigger: "自签名后算路报 10008 INVALID_USER_SCODE：高德 key 按 Bundle ID 鉴权，底图却还能显示. SideStore 装好 App，点「回家」/选目的地，算路直接失败： ``` 算路失败: CalculateRideRouteError:13(1-2)…"
verify: "```bash xcrun devicectl device info apps --device <UDID> | grep cn.yqx.bmsios ``` 应显示无后缀的 `cn.yqx.bmsios`；随后算路能正常返回路线（10008 消失）。"
provenance:
  issue: "#4173"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

SideStore 装好 App，点「回家」/选目的地，算路直接失败：

```
算路失败: CalculateRideRouteError:13(1-2)
(10008:INVALID_USER_SCODE)(code 13)
```

但**地图底图能正常显示**，于是很容易判断成「key 是好的，问题在算路」。

## Root Cause

SideStore 重签名时会把 bundle id 加后缀避开冲突：

```
高德 key 绑的：  cn.yqx.bmsios
手机上实际装的：  cn.yqx.bmsios.PGV6836FJR   ← SideStore 加的
```

高德 iOS key 是**按 Bundle ID 鉴权**的（`INVALID_USER_SCODE` 就是「你这个 App 的身份对不上」），所以算路服务直接拒。底图瓦片不走这套校验，所以「地图能看」会误导人。

## Fix

二选一：
1. **改 bundle id 回原值**（推荐，App 身份干净）：先卸载旧的（不卸载 SideStore 会认为 id 被占用又加后缀）→ 安装页点 `Bundle ID` 那一行 → 删掉末尾 `.XXXXXX` → Install；
2. **改高德控制台绑定**：Bundle ID 改成实际值，有「安全码 / SHA1」字段就清空（自签名书指纹和开发证书不同）；代价是这个 key 锁死在这个 bundle id 上。

凡是按 bundle id 鉴权的第三方 SDK（高德/百度/微信开放平台），自签场景第一件事就是确认 bundle id 没被改。

## Verification

```bash
xcrun devicectl device info apps --device <UDID> | grep cn.yqx.bmsios
```
应显示无后缀的 `cn.yqx.bmsios`；随后算路能正常返回路线（10008 消失）。
