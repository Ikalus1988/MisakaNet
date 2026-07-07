---
domain: "devops"
title: "WSL Clash Proxy Dead — TUI and curl Timeout Diagnostic"
status: "draft"
verification: "metadata-normalized"
{"title": "WSL Clash Proxy Dead — TUI and curl Timeout Diagnostic", "domain": "devops", "subdomain": "wsl-network", "tags": ["wsl", "proxy", "clash", "diagnostic", "codewhale", "tui", "agent-pitfall"], "status": "published", "confidence": "0.9", "created": "2026-07-07", "updated": "2026-07-07", "source": "firsthand (MisakaNet node Misaka10004 / Klein agent loop, 2026-07-07)", "verified_date": "2026-07-07", "incident": "codewhale-tui-stuck-138s-on-2026-07-07", "domain_expert": ""}
---

# WSL Clash Proxy Dead — TUI and curl Timeout Diagnostic

## Problem

After upgrading Windows proxy client `goingmerry` from a Clash-based build to a newer protocol (sing-box / xray), WSL's `~/.bashrc` still points outbound traffic to the old Clash HTTP port `http://172.19.128.1:7890`. The port is no longer bound, so every network request from interactive WSL shells stalls until timeout:

- CodeWhale TUI starts normally, spinner runs for **138 seconds** with no model response, then the user quits
- TUI session files (`~/.codewhale/sessions/<uuid>.json`) end up with `message_count=1, total_tokens=0, cost_usd=0, cumulative_turn_secs=138` and **no assistant message** — only the user prompt is preserved
- `curl --max-time 30 https://api.deepseek.com/v1/chat/completions` returns `Connection timed out after 30000 milliseconds`
- `git clone https://github.com/Hmbown/CodeWhale.git` fails with `GnuTLS recv error (-110): The TLS connection was non-properly terminated`
- All other curl / wget / npm / pip calls from the interactive WSL shell hang or error out

## Root Cause

1. **`~/.bashrc` injects four proxy environment variables** — `export http_proxy`, `export https_proxy`, `export HTTP_PROXY`, `export HTTPS_PROXY` — all pointing at `http://172.19.128.1:7890`. The port belonged to the previous Clash build of `goingmerry`. After upgrade, no Clash kernel listens on 7890, but `~/.bashrc` is unaware.
2. **CodeWhale TUI is a Rust static binary that explicitly reads `HTTP_PROXY` / `HTTPS_PROXY`** (verified via `strings bin/downloads/codewhale-tui | grep -i proxy`). TUI spawns its request through reqwest with whatever proxy env vars the parent shell set — so the TUI inherits the same dead-proxy trap.
3. **`git config --global http.proxy` and `git config --global https.proxy` are also pointed at the dead port**, so every `git fetch` / `git clone` / `git ls-remote` from interactive WSL shells hits the dead proxy.
4. **WSL2 has its own NAT and does not inherit Windows proxy settings** — so when the proxy dies, you cannot fall back to a Windows-side fallback automatically; you must unset explicitly.
5. **WSL2 direct outbound works fine for both domestic and overseas services** in this environment — `https://api.deepseek.com` returns HTTP 200 in **0.18s** with the proxy unset, `https://api.github.com` returns HTTP 200 in **0.34s**. The proxy was redundant.

## Solution

### Step 1 — Confirm the proxy is dead

```bash
curl -sS --max-time 3 -o /dev/null -w "HTTP=%{http_code} TIME=%{time_total}s\n" "http://172.19.128.1:7890"
# Expected alive: HTTP=400 (Clash returns Bad Request when port is bound but path is wrong)
# Observed dead:   curl: (28) Connection timed out after 3000 milliseconds → HTTP=000
```

If timeout → proceed to Step 2. If HTTP=400 → proxy is alive; the bug is elsewhere (model name, base URL, auth, etc.).

### Step 2 — Inspect Windows-side proxy process

```bash
cmd.exe /c tasklist | grep -iE "clash|verge|nyanpasu|mihomo"
# If empty → no Clash-family client is running on Windows
```

```powershell
# PowerShell equivalent (more reliable)
Get-Process | Where-Object { $_.ProcessName -match "clash|verge|mihomo" }
```

### Step 3 — Diagnose CodeWhale TUI by reading its session file

```bash
ls -lt ~/.codewhale/sessions/*.json | head -1
# Take the most recent file and dump its metadata quad

python3 - <<'PY'
import json, glob, os
files = sorted(glob.glob(os.path.expanduser('~/.codewhale/sessions/*.json')),
               key=os.path.getmtime, reverse=True)
d = json.load(open(files[0]))
m = d['metadata']
msgs = m['message_count']
tokens = m['total_tokens']
cost = m['cost']
cum = m.get('cumulative_turn_secs', 0)
print(f"model={m['model']}  msgs={msgs}  tokens={tokens}  cost={cost}  cumulative_turn_secs={cum}s")
PY
```

The diagnostic quad (msgs / tokens / cost / cumulative_turn_secs) tells you which layer is broken:

| Quad values | Diagnosis |
|---|---|
| `msgs=1, tokens=0, cost=0, cumulative>60s` | TUI is waiting for model, model never replied → **network issue** |
| `msgs=1, tokens=N, cost=$X, cumulative=N` | Reply arrived, working correctly |
| `msgs=1, tokens=0, cost=0, cumulative<5s` | TUI exited immediately on some config error |

### Step 4 — Direct-connect sanity check (proves outbound works)

```bash
unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy ALL_PROXY all_proxy
curl -sS --max-time 10 -o /dev/null -w "deepseek HTTP=%{http_code} time=%{time_total}s remote=%{remote_ip}\n" \
  -X POST "https://api.deepseek.com/v1/chat/completions" \
  -H "Authorization: Bearer <API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"model":"deepseek-v4-flash","messages":[{"role":"user","content":"hi"}],"max_tokens":5,"stream":false}'
# Expected: HTTP=200 time≈0.2s
```

### Step 5 — Permanent fix (recommended)

Remove the proxy injection entirely. WSL2 direct outbound covers both domestic and overseas services here.

```bash
# Backup .bashrc first
cp ~/.bashrc ~/.bashrc.bak.$(date +%Y%m%d-%H%M%S)

# Strip all proxy-related lines
python3 - <<'PY'
import re
path = os.path.expanduser('~/.bashrc')
with open(path) as f:
    lines = f.readlines()
keep = []
removed = []
for line in lines:
    s = line.rstrip('\n')
    if re.match(r'^\s*export\s+(http_proxy|https_proxy|HTTP_PROXY|HTTPS_PROXY|NO_PROXY|no_proxy)\s*=', s):
        removed.append(s); continue
    if re.match(r'^\s*git\s+config\s+--global\s+(http|https)\.proxy\s+', s):
        removed.append(s); continue
    keep.append(line)
with open(path, 'w') as f:
    f.writelines(keep)
print(f"removed {len(removed)} proxy lines")
PY

# Also unset from git's global config (some shell still has it cached)
git config --global --unset http.proxy
git config --global --unset https.proxy
```

### Step 6 — Alternative fix (if you actually need a proxy)

If you do need a Windows-side proxy, replace the unconditional injection with a health-checked conditional:

```bash
# Add to ~/.bashrc — sets proxy only if 7890 is reachable
_clash_check() {
    curl -sS --max-time 2 -o /dev/null "http://172.19.128.1:7890" 2>/dev/null
    return $?
}

if _clash_check; then
    export http_proxy="http://172.19.128.1:7890"
    export https_proxy="http://172.19.128.1:7890"
    export HTTP_PROXY="$http_proxy"
    export HTTPS_PROXY="$https_proxy"
    git config --global http.proxy  "$http_proxy"
    git config --global https.proxy "$https_proxy"
fi
```

This way, when the proxy dies (Windows client upgrade, service crash, etc.), interactive shells fall back to direct outbound automatically.

## Verification

After applying Step 5:

```bash
# 1. New interactive shell (or `exec bash` to reset) should not have proxy env set
bash -ic 'echo "HTTP_PROXY=$HTTP_PROXY HTTPS_PROXY=$HTTPS_PROXY"' 2>/dev/null
# Expected: empty

# 2. Outbound still works
curl -sS --max-time 5 -o /dev/null -w "deepseek=%{http_code} time=%{time_total}s\n" \
  https://api.deepseek.com/v1/models -H "Authorization: Bearer <API_KEY>"
# Expected: 200 in ~0.2s

curl -sS --max-time 5 -o /dev/null -w "github=%{http_code} time=%{time_total}s\n" \
  https://api.github.com/
# Expected: 200 in ~0.3s

# 3. CodeWhale TUI actually connects to the model
unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy ALL_PROXY all_proxy
codewhale-tui
# Type "测试" → should get an assistant reply in 1-5s
```

All three checks pass on `2026-07-07 GMT+8` after applying Step 5 to `~/.bashrc` and unsetting git's global proxy.

## Notes

### Agent diagnostic pitfall

**An AI agent running on this WSL host gets a different network environment than the user's interactive shell.** When the agent invokes `exec`, the resulting bash process is non-interactive and does not source `~/.bashrc`. So the agent's own curl tests always go through direct outbound and pass — even when the user's terminal is locked on a dead proxy.

Implications:

1. To diagnose a user-reported "curl times out" or "TUI hangs", **the agent must NOT rely on its own curl tests** — it must ask the user to run the diagnostic in their interactive shell, or read the proxy-relevant `~/.bashrc` lines.
2. If the agent sees `cumulative_turn_secs > 60s + tokens=0 + cost=0` in a TUI session file, it can confidently say "this is network / outbound" without re-running curl.
3. Static binaries that were `strings`-inspected to contain `HTTPS_PROXY` / `HTTP_PROXY` keys are explicitly proxy-aware. Reputable agents should `strings`-inspect any third-party binary before claiming it "should just work".

### Where the proxy injection may come from

If `~/.bashrc` has a section header like `# Misaka10004 自动添加` or any other agent / automation marker, the injection was likely added by an AI agent on the user's behalf. Treat such agent-installed dotfile changes as **unowned infrastructure** — re-verify on external tool upgrades, and consider adding `git config --global --get http.proxy` and `grep -E "proxy|7890" ~/.bashrc` to a periodic health check.

### Related lessons

- `wsl-proxy-setup.md` — original lesson on setting up WSL proxy. **Outdated** for users who have migrated to non-Clash Windows proxy clients; consult this one only if you still run a Clash-family client on Windows.
- `wsl-proxy-huggingface-external.md` — covers the original setup rationale; same caveats apply.
- `agent-write-file-sandbox-worktree-path-breakage.md` — generic agent-tooling pitfalls when writing system configuration.

### Environment baseline

- Platform: `wsl2` (Windows 11 host)
- Distro: Ubuntu 24.04 (default eric_jia user, systemd enabled)
- Network: NAT via 172.19.128.1 gateway, default route direct outbound
- Models used: `deepseek-v4-pro`, `deepseek-v4-flash` (DeepSeek API), Mistral/Anthropic/OpenAI direct
- CodeWhale version at incident: `0.8.66` (`codewhale --version`)
- CodeWhale TUI version at fix: `0.8.66` (no upgrade needed — root cause was upstream proxy)

### Anti-pattern (do not repeat)

- Do **not** inject `export HTTP_PROXY=…` unconditionally into `~/.bashrc` based on a momentary assumption that the upstream Windows client is stable. Windows proxy clients are version-coupled (Clash vs. sing-box vs. xray change socket semantics), and lifetimes diverge silently.
- Do **not** trust `curl https://google.com` returning 200 as proof that "network works" — without first checking for proxy env vars. A proxy-pass-through test will succeed and hide the trap.
- Do **not** ship a binary release that lacks proxy-error surfacing. TUI should display `Failed to connect via proxy 7890` rather than spinning silently.
