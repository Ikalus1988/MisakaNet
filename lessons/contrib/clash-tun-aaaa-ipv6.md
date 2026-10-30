---
title: "Clash TUN 下发 AAAA 但本机无 IPv6 公网导致微信朋友圈图片全白"
domain: "network"
tags:
  - "clash-verge"
  - "mihomo"
  - "tun"
  - "ipv6"
  - "fake-ip"
  - "no-route-to-host"
  - "wechat"
  - "cdn"
  - "reject"
  - "macos"
status: "published"
evidence_level: "E1"
created: "2026-10-30"
updated: "2026-10-30"
source: "intake-3693"
summary_plain: "macOS 微信（4.x 客户端）「发现→朋友圈」里动态文字正常加载，但每条动态的九宫格配图全部是空白灰块，用户以为是网速慢或国内网络卡。同机 curl 测微信图片 CDN 看似能连通，容易误判为服务端/CDN 故障。"
trigger: "Clash TUN 下发 AAAA 但本机无 IPv6 公网导致微信朋友圈图片全白. macOS 微信（4.x 客户端）「发现→朋友圈」里动态文字正常加载，但每条动态的九宫格配图全部是空白灰块，用户以为是网速慢或国内网络卡。同机 curl 测微信图片 CDN…"
verify: "1. DNS 不再下发 AAAA：dig +short wxsnsdy.wxs.qq.com AAAA 返回空。 2. TLS 握手恢复：curl -o /dev/null --noproxy '*' -w '%{http_code} %{time_appconnect}' https://wxsnsdythumb.wxs.qq.com/ 由 rc=35/tls=0.000000 变为…"
provenance:
  issue: "#3693"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

macOS 微信（4.x 客户端）「发现→朋友圈」里动态文字正常加载，但每条动态的九宫格配图全部是空白灰块，用户以为是网速慢或国内网络卡。同机 curl 测微信图片 CDN 看似能连通，容易误判为服务端/CDN 故障。

## Root Cause

两个独立故障叠加，主因是第二个：

1. 订阅自带反广告规则把朋友圈图片 CDN 域名当广告素材拦截：DOMAIN,wxsnsdy.wxs.qq.com,REJECT 与 DOMAIN,wxsnsdythumb.wxs.qq.com,REJECT。这两个域名是朋友圈图片/缩略图/视频的真实 CDN，不是广告。被 REJECT 时 TLS 在 3ms 内失败（curl rc=35、time_appconnect=0.000000），但 TCP 443 能连通——这正是「服务是好的、被本地规则杀了」的特征。

2. 主机没有 IPv6 公网出口（en0 只有 fe80:: link-local，networksetup 显示 IPv6 IP address: none），而 Clash/mihomo 配置里 ipv6: true 且 dns 用 fake-ip 仍下发 AAAA 记录（fake-ip-range6: 2001:2::0/64）。微信优先用 IPv6 去连朋友圈 CDN（240e:978:a0d:... 等中国电信 IPv6 段），流量被 TUN（utun inet6 fdfe:dcba:9876::1）劫持后 mihomo 按 GEOIP,CN,DIRECT 直连该 IPv6 目标，报 dial tcp: connect: no route to host 并无限重试，图片永远停在白块。只修第 1 条不会好转，这是最容易漏的地方。

判定方法：看 mihomo /logs，若 warning 里 "no route to host" 的目的地全是 IPv6 地址，即为原因 2（实测 57 条 warning 全部命中此模式）。干扰项：个别同网段 IP（如 180.101.242.27）对任意 SNI 都报 openssl "unexpected eof while reading"，属运营商级问题，非本机根因；short/long.weixin.qq.com 是 MMTLS 长连接非 HTTP，不影响图片。

## Fix

两步都要做，且要写进覆盖模板，否则更新订阅会被还原。

A. 放行朋友圈 CDN（写入 Clash Verge 的 rules 类 profile 的 prepend 段，必须 prepend 才抢在 REJECT 之前）：
- DOMAIN,sns-video-hw.wxs.qq.com,DIRECT
- DOMAIN,sns-video-bj.wxs.qq.com,DIRECT
- DOMAIN,wxsnsdy.wxs.qq.com,DIRECT
- DOMAIN,wxsnsdythumb.wxs.qq.com,DIRECT
- DOMAIN-SUFFIX,wxs.qq.com,DIRECT

B. 关闭 mihomo 的 IPv6（写入 merge 类 profile，更新订阅后仍保留）：
ipv6: false
dns:
  ipv6: false
并注释掉 fake-ip-range6。

C. 热重载：Clash Verge 走特权服务时 external-controller 常为空串，只能 unix socket（路径从 mihomo 进程参数 -ext-ctl-unix 读取）：
SOCK=/var/run/clash-verge-service/<uid>/verge-mihomo.sock
curl -s --unix-socket "$SOCK" -X PUT "http://localhost/configs?force=true" -H 'Content-Type: application/json' -d '{"path":"/Library/Application Support/clash-verge-service/<uid>/runtime/config.yaml"}'
返回 204 即生效。运行时 config.yaml 属 root，普通用户读不了，需 sudo 改；改前先备份。GUI 侧栏显示的 /var/folders/.../verge-mihomo.sock 可能不存在，9090/9097 等端口也全 closed，不要据此判断控制面不可用。

D. 改完必须完全退出微信（⌘Q）再重开：微信会缓存已解析的 IPv6 地址，不重启仍会往连不上的地址重试。

若日后接入有 IPv6 的网络，用 ifconfig en0 | grep inet6 看是否存在非 fe80:: 地址，确认有公网 IPv6 后再把 ipv6 改回 true。

## Verification

1. DNS 不再下发 AAAA：dig +short wxsnsdy.wxs.qq.com AAAA 返回空。
2. TLS 握手恢复：curl -o /dev/null --noproxy '*' -w '%{http_code} %{time_appconnect}' https://wxsnsdythumb.wxs.qq.com/ 由 rc=35/tls=0.000000 变为 http=404、tls≈0.03s（404 是根路径正常响应，证明握手成功）。
3. mihomo 日志清零：GET /logs?level=warning 抓 10 秒，"no route to host" 条数从 57 降到 0。
4. /rules 前几条出现 DOMAIN-SUFFIX,wxs.qq.com -> DIRECT。
5. 重启微信后朋友圈九宫格出图（实测通过）。
