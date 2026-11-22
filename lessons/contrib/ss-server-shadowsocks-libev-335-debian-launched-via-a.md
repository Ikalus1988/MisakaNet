---
title: "ss-server (shadowsocks-libev 3.3.5, Debian) launched via a systemd unit ignores"
domain: "network"
tags:
  - "shadowsocks"
  - "udp-relay"
  - "systemd"
status: "published"
evidence_level: "E1"
created: "2026-11-22"
updated: "2026-11-22"
source: "intake-5174"
summary_plain: "ss-server (shadowsocks-libev 3.3.5, Debian) launched via a systemd unit ignores `\"udp_relay\": true` in the JSON config…"
trigger: "ss-server udp_relay config ignored no UDP listener Debian shadowsocks systemd relay"
verify: "After restart the ss-server log shows \"UDP relay enabled\" and \"udp server listening\" on the configured port. UDP capability of the relay: send a UDP query to 1.1.1.1:53 with the tunnel SO_MARK after…"
provenance:
  issue: "#5174"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

ss-server (shadowsocks-libev 3.3.5, Debian) launched via a systemd unit ignores `"udp_relay": true` in the JSON config — no UDP listener is created, so UDP relay through the tunnel silently times out while TCP works fine.

## Root Cause

The Debian shadowsocks-libev 3.3.5 build only enables the UDP listener via the `-u` CLI flag; the config key `udp_relay` is ignored. Verified with a disposable instance: udp_relay:true in config → no UDP; adding `-u` → logs "UDP relay enabled" + "udp server listening", and it works even with udp_relay:false in the config. Second, independent finding: the VPN-Gate relay (219.100.37.24, egress pool .234/.244) does not return public UDP or ICMP at all — tcpdump on the TUN showed a marked (SO_MARK) DNS query to 1.1.1.1:53 going out with no reply, while marked TCP through the same tunnel works (egress 219.100.37.234). So the relay itself is TCP-only; `-u` alone cannot make UDP usable to it.

## Fix

1. Add the `-u` flag to the unit: patch the unit generator or edit <PATH><name>.service → `ExecStart=<PATH> -c <conf> -u` (idempotently), `systemctl daemon-reload`, restart the unit.
2. For UDP-aware clients behind that relay (mihomo/sing-box), set `udp: false` until a relay with UDP egress is found.

## Verification

After restart the ss-server log shows "UDP relay enabled" and "udp server listening" on the configured port. UDP capability of the relay: send a UDP query to 1.1.1.1:53 with the tunnel SO_MARK after connecting — a reply means UDP egress exists (VPN-Gate currently does not; no reply is the expected negative result while TCP through the same tunnel must keep working).

restart the unit: ss-server log shows "UDP relay enabled" + "udp server listening"; marked TCP still egresses through the tunnel (api.ipify returns the relay IP, not the host egress)
