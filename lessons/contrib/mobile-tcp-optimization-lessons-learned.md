---
title: Mobile TCP Optimization in Production Networks
domain: networking
tags: [TCP, mobile-networks, optimization, middlebox, latency]
language: en
status: published
source: https://www.snellman.net/blog/archive/2015-08-25-tcp-optimization-in-mobile-networks/
created: 2026-07-27
confidence: 0.85
---

## Problem

Mobile networks present unique challenges for TCP performance due to variable radio conditions, packet loss patterns, and network characteristics that differ significantly across operators. Standard TCP implementations do not account for mobile-specific issues, leading to suboptimal performance in production deployments.

## Root Cause

Not specified in source. The article describes symptoms (packet reordering, strange packet loss patterns, conflicting middleboxes) but does not provide detailed root cause analysis for why mobile networks present these specific challenges.

## Solution

Teclo Networks implemented a custom TCP optimization system deployed as a transparent network element ("bump in the wire") on the Gi link next to the GGSN:

**Architecture:**
- Completely custom user space TCP stack built from scratch
- Custom user space NIC drivers with direct PCI register manipulation
- Zero-copy packet handling implementation
- Data plane entirely in user space; control plane in kernel

**Connection Optimization Approach:**
- Pass initial TCP handshake (SYN, SYN-ACK, ACK) through unmodified
- Split connection into two parts without sacrificing transparency
- ACK data packets from clients and take responsibility for delivery
- Maintain TCP sequence number and option transparency with endpoints

**Key Design Principles:**
- Maintain transparency of TCP options and sequence numbers
- Preserve original segment sizes (avoid repacketization)
- Allow graceful stop of optimization without breaking connections
- Handle asymmetric routing scenarios

**System Capabilities:**
- Scales to 10 million connections and 20Gbps optimization in single 2U box
- Handles all radio technologies (2G, 3G, LTE, WiMAX, CDMA)
- Deployed across approximately 50 mobile networks with 20 commercial deployments
- Handles traffic from small MVNOs (100Mbps) to major operator groups (100Gbps)
- Uses standard hardware: normal Xeon CPUs and Intel 82580 or 82599 NICs

**Optimization Types:**
- Latency splitting for initial connection phase (not fully specified in source)
- Buffer management strategies
- Burst control
- Simple optimizations and speedups (specific techniques not provided in source)

## Verification

Not specified in source. The article does not provide explicit verification steps or testing procedures for validating the optimization implementation.

## Notes

**Operational Lessons Learned:**

- **Hardware dependency:** Do not rely on hardware features; maintain portability across different NIC models and manufacturers
- **Network variability:** Two mobile networks are never equal; expect different characteristics, packet loss patterns, and middlebox behavior
- **Technical challenges:** Encountered issues with packet reordering, strange packet loss patterns, bad or conflicting middleboxes
- **Operations complexity:** Operations and maintenance (O&M) is a lot of work; requires careful monitoring and management
- **Transparency importance:** Transparency of optimization was emphasized as critical for being a good networking citizen

**Design Advantages:**

- Short idle timeouts possible (couple of minutes vs. 15 minutes traditional)
- Graceful degradation: can stop optimizing connections at any time without breaking them
- Service upgrade capability: can transition to bypass without interruption
- Handles asymmetric routing issues
- Passes through unknown TCP options without breaking them (supports future protocols like Multipath TCP, TCP Fast Open)
- Prevents MSS repacketization issues that occur with terminating proxies

**Integration Method:**

Deployed as bump-in-the-wire on Gi link with no L2/L3 address, appearing as transparent network element to endpoints.

## References

- Snellman, J. (2015). "Mobile TCP optimization - lessons learned in production." SIGCOMM'15 HotMiddlebox workshop keynote presentation.
- Source: https://www.snellman.net/blog/archive/2015-08-25-tcp-optimization-in-mobile-networks/