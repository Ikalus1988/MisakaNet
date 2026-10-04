# Verifying the five MCP-only clients

Issue [#1753](https://github.com/Ikalus1988/MisakaNet/issues/1753) asks for evidence from machines
other than the maintainer's, and it names the five clients it most wants covered:

> **最想要的是后 5 个**（Cursor / Gemini CLI / Copilot CLI / OpenCode / Kiro）

But the steps that issue gives run `claude mcp list`, `codex mcp list`, `codewhale mcp tools`,
`hermes mcp list` and a JSON peek for OpenClaw. **There is no command in it for any of the five.**
Its acceptance checklist still requires two fields that only a real machine can produce:

- `tools-visible:` — the real tool count **from your assistant's own output**
- `live-call-evidence:` — **the raw line** from the event stream

So the five highest-value lanes are the five with no way to fill in the two fields the bounty
scores. This page closes that gap for the part we actually know, and is explicit about the part we
do not.

## First, what these five have in common

They are the installer's **MCP-entry-only** tier. The installer writes one entry into an existing
config file and nothing else — no rule block, no hooks, no install. That makes their verification
two separate questions, and only the first one is answerable without the client running:

| | Question | Answerable from the repo? |
|---|---|---|
| **A** | Did the installer write the entry? | **Yes** — the path and the key are in the installer's own table |
| **B** | Does the client see 7 tools, and call one? | **No** — needs the client on your machine |

## A. Reading the entry back (we know this; here are the commands)

The shapes below are transcribed from the installer's target table in
`packages/misakanet-setup/bin/misakanet-setup.mjs` (the `TARGETS` object) — not from a blog post,
and not from each vendor's documentation. If you change one, change both.

| Client | Config path (under `$HOME`) | Key holding the entry | URL field |
|---|---|---|---|
| Cursor | `.cursor/mcp.json` | `mcpServers` | `url` |
| Gemini CLI | `.gemini/settings.json` | `mcpServers` | `httpUrl` |
| Copilot CLI | `.copilot/mcp-config.json` | `mcpServers` | `url` |
| **OpenCode** | `.config/opencode/opencode.json` | **`mcp`** | `url` |
| Kiro | `.kiro/settings/mcp.json` | `mcpServers` | `url` |

OpenCode is the odd one out: its key is `mcp`, not `mcpServers`. Gemini's URL field is `httpUrl`,
not `url`. A readback written for the other three will silently find nothing on these two.

Save as `mcp_readback.py` and run `python3 mcp_readback.py opencode` (on native Windows, `py -3`).
It takes the client name, prints the whole entry or an explanation of what is missing, and exits
non-zero when there is nothing to show — so it is safe to paste straight into a report.

```python
import json, os, sys
SHAPES = {  # transcribed from the installer's TARGETS table
    "cursor":   (".cursor/mcp.json",               "mcpServers", "url"),
    "gemini":   (".gemini/settings.json",          "mcpServers", "httpUrl"),
    "copilot":  (".copilot/mcp-config.json",       "mcpServers", "url"),
    "opencode": (".config/opencode/opencode.json", "mcp",        "url"),
    "kiro":     (".kiro/settings/mcp.json",        "mcpServers", "url"),
}
name = sys.argv[1] if len(sys.argv) > 1 else ""
if name not in SHAPES:
    sys.exit(f"unknown client: {name!r}; expected one of {', '.join(SHAPES)}")
rel, key, url_field = SHAPES[name]
# OpenCode reads $XDG_CONFIG_HOME/opencode/opencode.json when that is set, not ~/.config/...
home = os.environ.get("XDG_CONFIG_HOME") if name == "opencode" else None
path = os.path.join(home or os.path.expanduser("~"), rel)
if not os.path.isfile(path):
    sys.exit(f"no such file: {path}")
try:
    doc = json.load(open(path, encoding="utf-8"))
except json.JSONDecodeError as e:
    sys.exit(f"{path} is not parseable as JSON ({e}). "
             "If this is opencode.jsonc, the installer cannot parse it either — report as T3.")
entry = (doc.get(key) or {}).get("misakanet")
if entry is None:
    sys.exit(f"NO misakanet ENTRY under {key!r} in {path}")
# Redact before printing. The config file holds the real bearer token; the installer's own
# --report guarantees "the token value never appears (only present/absent)", and this has to
# make the same promise, because the whole point of this output is to be pasted into an issue.
for field, value in list(entry.get("headers", {}).items()):
    entry["headers"][field] = "present" if value else "absent"
print(f"{path}  ->  .{key}.misakanet   (header values redacted: present/absent)")
print(json.dumps(entry, indent=2, ensure_ascii=False))
print(f"\ncheck: {url_field} == {entry.get(url_field)!r}")
```

Expect the URL field to be `https://misakanet.org/mcp`. The script redacts every `headers` value to
`present`/`absent` before printing, because **the config file contains your real bearer token** and
this output is meant to be pasted into a public issue. The installer's own `--report` makes the same
guarantee ("the token value never appears"); this script has to too. If you paste an unredacted
entry anywhere, rotate the token.

Two known traps, both from the installer's own notes:

- **OpenCode honours `XDG_CONFIG_HOME`.** If you set it, the file it reads is
  `$XDG_CONFIG_HOME/opencode/opencode.json`, not the path in the table above.
- **`opencode.jsonc` allows comments, and the installer cannot parse it.** If your OpenCode config
  is the `.jsonc` variant, `npx @misaka-net/misakanet-setup` will not touch it. That is a real
  installer limitation, not a mistake in your setup — please report it (T3) rather than working
  around it silently.

## B. What we do not know, and are not going to invent

**There is no known OpenCode CLI subcommand that lists MCP tools, and this repository has never run
OpenCode.** The field report that looked at it
([`docs/field-reports/opencode-kiro-omp-compat-20261001.md`](../field-reports/opencode-kiro-omp-compat-20261001.md))
records `which opencode` → not found, and the installer itself only says
*"重启 OpenCode 后看它的 MCP 列表"* — look at OpenCode's MCP list in its UI.

So a plausible-looking `opencode mcp list` in a bounty thread is a guess wearing a command's
clothes. If it is wrong, it teaches a contributor that this repo will hand them commands it never
ran — which is the exact failure this bounty was written to prevent ("不要贴你没跑过的输出").
**We would rather leave the gap visible.**

This makes the unknown the interesting deliverable. **If you work out how to see the tool list and
how to capture a tool call for your client, that command belongs in this file**, and the first
person to supply it for a given client is doing the most valuable work available on this issue.
A command that only you have run is worth more here than a polished guess from us.

Roughly, what you are looking for:

- **`tools-visible`** — the client showing `misakanet_*` tools. Seven is the expected number
  (`tools/list` on `https://misakanet.org/mcp` returns 7; `docs/integrations/status.md` records the
  same). Note the Python stdio server exposes **10** — it has `misakanet_memory_context`,
  `misakanet_submit_usage` and `misakanet_usage_status`, which the hosted endpoint does not. If you
  installed the `pip install misakanet` stdio server rather than the hosted endpoint, say which,
  because the number differs and we would otherwise read your 10 as a defect.
- **`live-call-evidence`** — one raw line out of the event stream showing
  `misakanet_search` (or another tool) actually being called. The issue's own suggestion works well
  as a probe: ask in natural language containing a literal error string, e.g.
  `pip install timeout 是什么原因`, and look for the tool name in the stream. Whole-sentence
  natural-language queries score 0 against this corpus — that is why the issue uses error fragments
  like `switch vision model` or `context window exceeded`.

## What counts as a valid report for these five

- ✅ Entry readback (section A) **plus** the client's own tool list **plus** one raw event-stream
  line. That is the full `#1753` T1.
- ✅ **Anything that fails counts.** A client whose config key we have wrong, or which rejects
  `type: "remote"`, is worth more than a clean run. T3 is explicitly equal in value.
- ❌ **A config readback submitted as `tools-visible`.** The config proves an entry exists. It
  proves nothing about what the client did with it. Those are different claims and the issue's
  checklist is asking for the second one.
- ❌ An `npx setup` report from a machine that does not have the client installed. It proves the
  installer skipped it, which we already know.

## Why this page exists at all

The five clients are the only tier whose evidence level in
[`docs/integrations/status.md`](../integrations/status.md) is 🔵 **vendor-only** — the vendor's
documentation says the configuration works, and nothing in this repository has ever run it. A
vendor-only claim is not a defect, but it is not a verification either, and it is the reason these
five are the ones the bounty wants.

Closing it is a one-line-per-client job on any machine that already has one of these assistants.
That is the whole ask.
