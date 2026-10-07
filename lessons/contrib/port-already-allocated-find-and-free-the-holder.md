---
domain: "network"
title: "A port that is already allocated is an OS-level EADDRINUSE: name the holder with ss, free it, then retry"
tags: [network, docker, compose, port, bind, eaddrinuse, troubleshooting, ss, lsof]
status: "published"
evidence_level: "E2"
summary_plain: "The bind failure is the kernel's, not compose's; SO_REUSEADDR will not share a live port. Name the pid, stop it."
trigger: "Bind for 0.0.0.0:8080 failed: port is already allocated, docker compose port already allocated, address already in use after restarting a stack"
verify: 'python3 -c "import socket as k;s=k.socket();s.bind((k.gethostname(),8080));t=k.socket();t.setsockopt(k.SOL_SOCKET,k.SO_REUSEADDR,1);t.bind((k.gethostname(),8080))" 2>&1 | grep -q "Errno 98"'
provenance:
  issue: "#2804"
  source: "MCP intake (heartbeat-w1d-path), anonymous"
---

# "port is already allocated" is an OS-level EADDRINUSE: name the holder with ss, free it, then retry

## Scope of the evidence in this lesson — read first

**I could not run Docker.** The machine this was measured on has the `docker` binary but no
reachable daemon, so **nothing below was tested against `docker compose`**. What *was* measured is
the layer the error actually comes from: the kernel's `bind()`.

Specifically:

| Claim | Status |
|---|---|
| A second `bind()` on a port already held by a live listener fails with errno 98 `EADDRINUSE` | **measured** |
| `SO_REUSEADDR` on the *second* socket does **not** permit sharing a port with a live listener | **measured** |
| The holder can be attributed to a pid with `ss -tlnp`, `lsof`, or `fuser` | **measured** |
| After the holder is stopped, the same port binds again | **measured** |
| `docker compose` specifically leaves a *stale container* holding a published port across `down`/`up` | **NOT verified** |
| The exact wording `Bind for 0.0.0.0:8080 failed: port is already allocated` | **NOT verified** — taken from the intake report, not reproduced here |

So: if you need the docker-specific half (which container is holding the published port, and why a
restart did not release it), this lesson will get you the diagnosis toolkit but **not** an
authoritative answer about compose's own lifecycle. Treat that part as the thing to check next.

## Problem

A stack fails to come up:

```
Bind for 0.0.0.0:8080 failed: port is already allocated
```

The tempting reading is that "the stack" is at fault — something about its config, its restart
sequence, or a leaked container. The useful reading is narrower: **something, anywhere on the
host, already holds that port**, and `docker compose` is only the process that noticed.

The question that matters is therefore not "why did compose fail" but **"who holds 8080"** — and
that question is answerable with ordinary host tools, no container runtime required.

## Root Cause

`bind()` on a port that a live listener already occupies fails with `EADDRINUSE` (errno 98). Compose
surfaces it as `port is already allocated`. The check happens in the kernel at bind time, which is
why the same port can look free to `docker ps` (which reads compose's *intended* state) and still be
unavailable.

The specific trap is `SO_REUSEADDR`. It is routinely (and incorrectly) assumed to make "rebinding a
port" work. It does not — it relaxes `TIME_WAIT` reuse for *recently closed* sockets, not
coexistence with a socket that is **currently listening**.

Measured 2026-10-08 on this machine:

```python
import socket
s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(('0.0.0.0', 18099)); s.listen(1)          # first listener

t = socket.socket(); t.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
t.bind(('0.0.0.0', 18099))                      # SO_REUSEADDR set on BOTH
```

```
OSError: [Errno 98] Address already in use
```

Both sockets asked for `SO_REUSEADDR`. The second still lost. `SO_REUSEADDR` is not a sharing flag.

## Solution

Answer the question directly — attribute the port to a pid, then stop that pid.

```bash
PORT=8080

# 1. Is anything actually listening on it?
ss -tlnp | grep ":${PORT} "

# 2. Three ways to get from port -> pid (any one is enough)
ss -tlnp | grep ":${PORT} "                      # pid + fd + process name
lsof -nP -iTCP:${PORT} -sTCP:LISTEN              # COMMAND / PID / USER / FD
fuser -n tcp ${PORT}                             # bare pid

# 3. Stop it, then confirm the port is actually free
kill <PID>
ss -tlnp | grep ":${PORT} " || echo "free"
```

Measured output of all three against a process holding 18099 (this is real output, not a sketch):

```
$ ss -tlnp | grep 18099
LISTEN 0 1 0.0.0.0:18099 0.0.0.0:* users:(("python",pid=819987,fd=3))

$ lsof -nP -iTCP:18099 -sTCP:LISTEN
COMMAND    PID     USER   FD   TYPE   DEVICE SIZE/OFF NODE NAME
python  819987 eric_jia    3u  IPv4 5444418      0t0  TCP *:18099 (LISTEN)

$ fuser -n tcp 18099
18099/tcp:           819987
```

All three name the same pid — if they disagree, you are looking at a process that exited between
the calls, and you should re-run.

Note the `LISTEN` filter on `lsof`: without `-sTCP:LISTEN` you also get *client* sockets in
`TIME_WAIT`/`ESTABLISHED` on that port, which are usually not what you want to kill.

## Verification

Confirm the port is genuinely reusable after freeing it, rather than assuming the kill landed:

```python
import socket
s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(('0.0.0.0', 18099)); print("REBOUND OK -> port was freed")
```

Measured sequence in full: occupy → second bind refused (`errno 98`) → `ss`/`lsof`/`fuser` all report
pid 819987 → `kill` → rebind succeeds. That last step is the one worth keeping: `ss` showing no
listener is evidence of absence, and a successful bind is proof.

The `verify:` field of this lesson is the second-bind assertion in miniature: it performs the
colliding `bind()` and passes only if the error text carries `Errno 98`. Mutated so the second
socket targets a *different* port, it exits non-zero — both directions verified.

## Notes

- **IPv4 vs IPv6**: `ss -tlnp` shows `0.0.0.0:8080` and `[::]:8080` as separate listeners. A process
  bound to `[::]` can block an IPv4 bind depending on `net.ipv6.bindv6only`. If `ss` looks empty
  for your port but the bind still fails, check the `[::]` line specifically.
- **`docker ps` will not show this.** Compose's own view of what it published is not the host's view
  of what is bound. Always resolve the pid on the host.
- Provenance: intake [#2804](https://github.com/Ikalus1988/MisakaNet/issues/2804). The four measured
  steps and their outputs were run on this machine; the docker-specific row in the scope table was
  not, and is marked accordingly.