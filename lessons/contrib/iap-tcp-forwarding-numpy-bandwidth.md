---
title: "IAP TCP Forwarding: Numpy Upload Bandwidth Optimization and Buffer Tuning"
domain: networking
tags:
  - iap
  - gcp
  - tcp-forwarding
  - numpy
  - bandwidth
  - socket-buffer
  - performance
status: published
created: "2026-09-08"
language: en
evidence_level: E2
provenance:
  source: "community"
  contributor: "s6pa1rta3n-lab"
  merged_at: "2026-09-08"
  evidence: "post-publication"
---

## Problem

When uploading large NumPy array datasets (such as model weights, embeddings, or serialized tensors) to Google Cloud Compute Engine instances over Identity-Aware Proxy (IAP) TCP forwarding tunnels (`gcloud compute start-iap-tunnel`), throughput drops by 40% to 85% compared to direct internal VPC connections. Transfers of multi-hundred megabyte arrays stall, encounter high latency variance, or fail with socket timeout errors (`BrokenPipeError`, `ConnectionResetError`).

## Root Cause

1. **Proxy Tunnel Encapsulation and Socket Buffer Limits**: Google Cloud IAP tunnels wrap raw TCP streams within WebSocket and TLS framing. Default OS socket send buffer sizes (`SO_SNDBUF`, typically 128KB to 256KB) quickly saturate under high-throughput NumPy binary streams. When the local buffer fills before the IAP gateway acknowledges packets across the WebSocket hop, TCP window collapses occur, throttling stream rate.

2. **Unbuffered Serialization and Memory Copying**: Standard unbuffered transfers or naive `np.save()` serialization create intermediate byte copies in user-space memory, triggering CPU stalls and uneven transmission burst rates that destabilize the IAP proxy rate limiter.

3. **Suboptimal MTU Negotiation**: IAP encapsulation reduces the effective path MTU below standard 1500 bytes. Large uncompressed array chunks without proper socket MSS negotiation lead to IP packet fragmentation and retransmission penalties across the proxy boundary.

## Fix

### 1. Tune OS Kernel TCP Buffers and Socket Options

Configure Linux kernel buffer parameters on both client and VM endpoints to allow dynamic window scaling up to 16MB:

```bash
sudo sysctl -w net.core.rmem_max=16777216
sudo sysctl -w net.core.wmem_max=16777216
sudo sysctl -w net.ipv4.tcp_rmem="4096 87380 16777216"
sudo sysctl -w net.ipv4.tcp_wmem="4096 65536 16777216"
sudo sysctl -w net.ipv4.tcp_window_scaling=1
sudo sysctl -w net.ipv4.tcp_slow_start_after_idle=0
```

### 2. Configure Python Socket Buffer and Disable Nagle Algorithm

Set explicit socket options before sending array bytes:

```python
import socket
import numpy as np
import io

def create_tuned_socket(host: str, port: int) -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4 * 1024 * 1024)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * 1024 * 1024)
    sock.connect((host, port))
    return sock

def stream_numpy_array(sock: socket.socket, array: np.ndarray, chunk_size: int = 1048576) -> int:
    buffer = io.BytesIO()
    np.save(buffer, array, allow_pickle=False)
    payload = buffer.getvalue()
    total_bytes = len(payload)
    view = memoryview(payload)
    bytes_sent = 0
    while bytes_sent < total_bytes:
        chunk = view[bytes_sent : bytes_sent + chunk_size]
        sent = sock.send(chunk)
        if sent == 0:
            raise RuntimeError("Socket connection broken during array transfer")
        bytes_sent += sent
    return bytes_sent
```

### 3. Compress Arrays Prior to Forwarding

For sparse or redundant tensor data, apply `np.savez_compressed` to reduce network payload volume before transmitting across the tunnel:

```python
def compress_and_send(sock: socket.socket, array: np.ndarray) -> None:
    buffer = io.BytesIO()
    np.savez_compressed(buffer, data=array)
    payload = buffer.getvalue()
    header = len(payload).to_bytes(8, byteorder="big")
    sock.sendall(header + payload)
```

## Verification

Execute verification commands to inspect socket metrics and test transfer throughput across the IAP forwarding port:

```bash
# Verify active socket buffer and window scaling parameters
ss -t -i '( sport = :8000 or dport = :8000 )'

# Execute end-to-end synthetic array transfer test
python3 -c "
import time, socket, numpy as np, io
data = np.random.randn(2500, 5000).astype(np.float32)
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4 * 1024 * 1024)
sock.connect(('127.0.0.1', 8000))
buf = io.BytesIO()
np.save(buf, data, allow_pickle=False)
payload = buf.getvalue()
start = time.perf_counter()
sock.sendall(payload)
elapsed = time.perf_counter() - start
mbps = (len(payload) * 8) / (elapsed * 1000000)
print(f'Transferred {len(payload)} bytes in {elapsed:.2f}s ({mbps:.2f} Mbps)')
sock.close()
"
```

**Expected output:**

Socket inspection confirms active window scaling and expanded send window buffer:

```
cubic wscale:7,7 rto:200 rtt:18.2/4.1 ato:40 snd_cwnd:128 ssthresh:96 snd_wnd:4194304
```

Array transfer throughput benchmark outputs sustained transfer rate exceeding 400 Mbps:

```
Transferred 50000128 bytes in 0.95s (421.05 Mbps)
```
