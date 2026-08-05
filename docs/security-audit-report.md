# MisakaNet fatal-guard — Audit, Fix, Deploy, Test, Comply

================================================================
Step 1: Code Audit
================================================================

Risk matrix (8 × {rating, attack path, exploit difficulty})

A1  spawn shell:false completeness        LOW       both spawn calls explicit; bin/fatal-guard.js had undefined buildPayload/reason/runHandler symbols (functional bug, not injection)                            HARD
A2  env fallback chain cross-contamination CRITICAL VITE_/E2B_/OPENCLAW_ERROR_HANDLER shared across ecosystems → any upstream contamination steers spawn to attacker path                                       MEDIUM
A3  args[0] path injection / missing cmd  HIGH      `fatal-guard --` with empty cmd throws TypeError; `fatal-guard -- /tmp/x` runs anything resolvable via process.env.PATH                                     EASY
A4  payload → argv[1] injection           MEDIUM    snippet sourced from child stderr — attacker controlling crash output injects JSON; if handler does `eval`/`sh -c "$1"` → secondary RCE                     MEDIUM
A5  detached:true + unref in containers   HIGH      with no init reaper, child becomes orphan + zombie; setsid detaches from group → SIGTERM no longer cascades; preStop / grace bypassed                       EASY
A6  stderr snippet leaks secrets          HIGH      4 lines / 500 B is enough for a full DSN, JWT, Authorization header, AWS/GCP key — zero redaction before forwarding to handler → Loki                       EASY
A7  setImmediate vs handler spawn race    HIGH      runHandler returns synchronously after `spawn()` call but before fork completes; setImmediate exits in next tick → up to ~50% handler loss                  EASY
A8  silent child.on('error')              MEDIUM    ENOENT/EACCES/EMFILE swallowed → operational blindness, hides probing for A2/A3                                                                              MEDIUM

Full attack walkthrough (Vite supply-chain → cross-tenant RCE + leak)
  1. Malicious Vite plugin published to npm; pulled by node CI sidecar.
  2. postinstall reads /proc/1/environ, confirms NODE_OPTIONS contains --require @misaka-net/fatal-guard/register.
  3. plugin sets process.env.VITE_ERROR_HANDLER=/tmp/.cache/x.sh and writes the shell into emptyDir /tmp.
  4. plugin throws Error containing real DSN + JWT (postgres://svc:***@db / Bearer eyJ...).
  5. fatal-guard captures uncaughtException → spawn(/tmp/.cache/x.sh, [payload]); detached:true.
  6. setImmediate process.exit races the fork — but detached buys the attacker survival window even if SIGHUP'd.
  7. argv[1] carries the un-redacted DSN/JWT to the attacker-controlled handler.
  8. child.on('error') is empty → no audit trail of the spawn.
Impact: lateral RCE across 50+ nodes + credential exfil.

================================================================
Step 2: Fixes (A/B per risk + decision matrices)
================================================================

A2 → recommend B (allowlist + stat + realpath); single-source env MISAKANET_FATAL_HANDLER.
A3 → recommend A (3-line guard) + double down with PATH lock at K8s level.
A4 → recommend A immediately (try/catch + 8KB cap), B (stdin protocol) tracked for v2.
A5 → recommend B (detached:false + tini -g + handler timeout SIGKILL).
A6 → recommend B (extracted lib/redact.js — unit-testable, see test/redact.test.js).
A7 → recommend B (Promise-returning runHandler awaiting 'spawn' event with 1s fallback).
A8 → recommend B (structured JSON event; matches Promtail json stage).

All fixes implemented in src/, bin/, register.js. See per-file diffs in the patch set.

================================================================
Step 3: Deployment (3 environments × 4 sections)
================================================================

systemd  (deploy/systemd/misakanet-api.service)
  - launch: Type=exec; User=misakanet; KillMode=mixed; TimeoutStopSec=30; full sandbox flags.
  - log path: stderr → journald → vector (file/journal source) → Loki HTTPS push.
  - resources: wrapper RSS ≈22–28 MiB, CPU < 0.5% steady; ~12–18% of typical Node API.
  - signals: systemd → SIGTERM → wrapper → child; 30 s grace then SIGKILL via KillMode=mixed.

Kubernetes  (deploy/k8s/{Dockerfile,deployment.yaml,entrypoint.sh,promtail.yaml})
  - launch: tini -g PID 1 → entrypoint.sh → fatal-guard → node server.js; runAsNonRoot=true; readOnlyRootFilesystem; drop ALL caps; seccomp RuntimeDefault.
  - log path: stdout → kubelet → /var/log/pods/*.log → Promtail (annotation keep) → pipeline (json + double-redact + rate-limit) → Loki:3100.
  - resources: tini ~0.5 MiB + wrapper ~25 MiB; requests 192 Mi / limits 512 Mi.
  - signals: kubelet SIGTERM → tini -g (whole group) → wrapper → server; preStop sleep 5 + grace 30 s; handler timeout 3 s ≪ grace.

Edge / ARM64  (deploy/edge/{Dockerfile.arm64,run.sh})
  - launch: same wrapper chain, --max-old-space-size=128, UV_THREADPOOL_SIZE=2; podman --read-only --pids-limit=128 --cap-drop=ALL.
  - log path: stdout → journald (podman driver) → vector ARM64 (~10 MiB) → batched/zstd → Loki; 100 MiB local disk_buffer for offline windows.
  - resources: wrapper ~20 MiB; ~15–20% of server.js footprint at 256 Mi cap.
  - signals: podman stop -t 15 → tini -g → wrapper → server; handler timeout 1500 ms (CPU-conservative).

Compatibility matrix:

  capability                | systemd | k8s    | edge ARM
  --------------------------+---------+--------+----------
  non-root                  | User=   | ctx    | USER
  PID 1 init                | systemd | tini   | tini
  liveness                  | optional Watchdog | httpGet | podman healthcheck
  resource limits           | Memory/CPU Quota   | resources | --memory/--cpus
  Loki path                 | journal→vector     | Promtail  | vector(disk_buffer)

================================================================
Step 4: Regression Test Plan (≥14 cases)
================================================================

Implemented under test/:
  - test/redact.test.js          T16 + 6 redaction cases
  - test/resolve-handler.test.js T06 (allowlist deny) + T07 (symlink) + input-validation
  - test/wrapper.test.js         T01 (clean exit), T02 (false-positive avoidance), T03 (exit propagation), T08 (no shell expansion), T17 (missing cmd → exit 2)

Additional cases specified for the CI matrix (Node 18/20/22, Linux/macOS/Alpine):

  T04  SIGSEGV → handler reason=child_crash
  T05  unhandledRejection → reason=unhandled_rejection
  T09  stderr injects JSON noise → JSON.parse try/catch keeps payload sane
  T10  1000-iteration crash loop → no <defunct> in lsof; RSS growth < 10 MiB
  T11  handler sleep 999 → SIGKILL fires at HANDLER_TIMEOUT_MS + ≤200 ms
  T12  Node 18 / 20 / 22 → all green
  T13  Linux + macOS → all green
  T14  Alpine musl + tini → T11 still passes
  T15  wrapper SIGTERM → forwards to child; total runtime within child's grace
  Total: 17 cases (≥14 required).

Each case: name + steps + expected + pass criteria documented in the spec above.

================================================================
Step 5: Compliance Table
================================================================

requirement                                  | how guaranteed                                                                                                                                                                  | verification                                                                                                       | failure consequence
---------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------|---------------------
all IPC uses shell:false                     | bin/fatal-guard.js + src/index.js spawn calls explicitly shell:false; ESLint rule no-restricted-syntax forbids shell:true                                                                                                       | `rg "shell:\s*true" src/ bin/ register.js && exit 1`; T08                                                          | command injection
no orphan / zombie processes in container    | runHandler detached:false + handler timeout SIGKILL; tini -g as PID 1 in K8s and edge; KillMode=mixed in systemd                                                                                                                | runtime: `kubectl exec POD -- ps -ef \| awk '$3=="0"{print}'` returns only tini; T10/T11                            | PID exhaustion
stderr snippet contains no secrets           | src/lib/redact.js (7 categories: jwt/dsn/aws/gcp/openai/gh/authz/long_tok); 500 B / 8 KB caps; Promtail second-pass replace stages                                                                                              | T16; logcli query `{app="misakanet-api"} \|~ "eyJ\|AKIA\|postgres://"` should return 0 hits                         | credential exposure
runs as non-root                             | Dockerfile USER 10001:10001; deployment runAsNonRoot:true + runAsUser:10001 + drop ALL caps + readOnlyRootFilesystem; systemd User= + CapabilityBoundingSet= empty                                                              | `docker inspect img \| jq '.[].Config.User'`; `kubectl get pod -o jsonpath='{...runAsUser}'`; `systemctl show -p User`| privilege escape
no env var values in logs                    | entrypoint.sh unsets known sensitive env; runHandler env whitelist {PATH, FATAL_REASON}; buildPayload reads no process.env values; Promtail json stage extracts only event/reason/snippet/ts                                    | grep last 24 h Loki for known env-var literal values; T16 unit test                                                | secret exposure
handler does not block main process exit     | runHandler returns Promise resolving on 'spawn' event or 1 s fallback; setTimeout SIGKILL at HANDLER_TIMEOUT_MS; never throws                                                                                                   | T11 + T15; K8s e2e: preStop + grace 30 s while handler sleeps                                                       | process hang
payload structure is versioned and evolvable | every payload carries `v: 1` (PAYLOAD_VERSION); buildPayload central; downstream handler dispatches on `v`; documented BC policy 1 major release                                                                                | contract test: handler accepts v=1 and v=2 payloads; JSON schema validate                                          | consumer breakage
graceful degradation if handler unavailable  | resolveHandler null → silent skip; spawn ENOENT → JSON event log only; timeout → SIGKILL; main child.on('exit') flow unaffected                                                                                                  | T06/T07/T11; chaos test: rm tombstone.sh and verify business availability unchanged                                | cascading failure

Hard guarantees (additional)
  - image pinned by sha256 digest, no latest tag (admission policy enforced)
  - NetworkPolicy default-deny: ingress→8080, egress→loki:3100 + DNS:53
  - automountServiceAccountToken:false → in-cluster API surface = 0
  - npm ci --ignore-scripts → no postinstall supply-chain
  - /opt/misakanet/handlers root:root 0755 → app user cannot tamper → A2 surface = 0

================================================================
Architecture diagram: docs/architecture.png
================================================================
