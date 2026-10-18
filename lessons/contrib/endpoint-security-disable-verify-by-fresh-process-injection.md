---
domain: "security"
title: "A tray icon is not evidence: test whether security software still injects into a newly started process"
tags: [windows, endpoint-security, dll-injection, verification, false-belief, troubleshooting, it-support]
status: "published"
evidence_level: "E2"
summary_plain: "A disabled endpoint-security agent still shows processes and injected DLLs, so test a freshly started process instead."
trigger: "IT disabled the antivirus but the app still fails; endpoint security still running after disable; injected DLL still present in module list"
verify: "start a fresh powershell.exe and grep its module list for the vendor DLL: absent means injection stopped. Sort injected processes by StartTime: no injection after the disable time also means stopped."
provenance:
  issue: "#3470"
  source: "MCP intake (claude-code), contributor-reported"
---

# A tray icon is not evidence: test whether security software still injects into a newly started process

## Problem

A test application kept failing after IT reported "the endpoint-security agent is disabled / shut
down". When the claim was checked, the disable had not taken effect — or had taken effect only
partially. The reason this is hard to see is that **every cheap signal points the same wrong way**:

- the tray icon says "protected" or shows a warning, mixing up *policy state* with *whether the
  injection engine is running*;
- the process/service list shows the vendor's processes still `Running` — nine of them in the
  measured case — and "still running" reads as "still active", while it may just as well be a
  leftover host process;
- the configuration/policy file has a fresh timestamp, but routine sync also rewrites timestamps,
  so a new `mtime` proves nothing about the disable.

Both directions were actually observed: a fresh config timestamp read as "disabled", and a running
process read as "not disabled". Neither conclusion was supported by the evidence.

## Root Cause

**Injected, long-lived processes keep the hook DLL after the injection engine stops.** `explorer.exe`
and `svchost.exe` were injected hours ago; their module lists still contain the vendor DLL, and they
stay that way until each process is restarted. So "N processes currently carry the DLL" **does not
decrease when the product is disabled** — it is a cumulative count, not a live one — and any decision
built on it is wrong in both directions.

The asymmetry that makes a criterion possible: injection can only be *added* to a process at process
start. Therefore:

- if a **newly started** process is injected, the engine is demonstrably still alive — no
  interpretation needed;
- if newly started processes are clean while old ones still carry the DLL, the engine is down and
  the old modules are residue.

## Solution

Use "is a **fresh** process injected?" as the only decisive test, plus a start-time histogram to
locate when injection stopped.

1. **Start a genuinely new process**, chosen with care: some products hook selectively by image name,
   and common shells (`cmd.exe`) are often on an exclusion list, so they show `NONE` even while the
   engine is fully active and would produce a false "disabled". Prefer a process the product is
   known to hook — the application under test, or `powershell.exe`.
2. **Read its module list** for the vendor's hook DLL, immediately.
3. **Sort the existing injected processes by `StartTime`** (or bucket by hour). If injections
   continue *after* the reported disable time, the disable did not happen; if the newest injection
   predates it, the residue explanation holds.

Decision table:

| Observation | Conclusion |
|---|---|
| A newly started process is still injected | the engine is **still working**; the disable did not take effect |
| New process is clean, old processes still carry the DLL | injection stopped; the old modules are residue and do not affect the verdict |
| No injected process is newer than the reported disable time | consistent with a real disable |
| Injected processes keep appearing after that time | not disabled, whatever the tray says |

## Verification

```powershell
# 1. fresh-process probe (pick a name the product does not exclude)
$p = Start-Process powershell -PassThru -ArgumentList '-NoProfile','-Command','Start-Sleep 30'
(Get-Process -Id $p.Id).Modules | Where-Object { $_.ModuleName -match '<vendor-dll>' }
#    empty  -> injection is not happening to new processes

# 2. start-time histogram of already-injected processes
Get-Process | Where-Object { $_.Modules.ModuleName -match '<vendor-dll>' } |
  Select-Object Id, ProcessName, StartTime | Sort-Object StartTime -Descending | Select-Object -First 10
#    every StartTime older than the disable time -> the residue explanation
```

The verdict is only "disabled" when both readings agree: no DLL in a fresh process **and** no
injection timestamp newer than the disable.

## Notes

- The same trap applies to EDR "agent stopped" claims generally: a stopped service whose loaded
  drivers and hooks remain in existing processes still affects them. The new-process probe is the
  cheapest way to separate "the controller is off" from "the effect is gone".
- Do not accept a verbal conclusion, a tray state or a process list as proof. Each of those is a
  *claim*; the probe above is an *observation*.
- If you only get one measurement, take the fresh-process probe — the start-time histogram
  distinguishes residue from a live engine, but the probe alone already answers "is it still acting
  on anything new".
