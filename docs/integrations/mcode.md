# MiniMax Code (mcode) Integration

**MiniMax Code** (`mcode`, the `@minimax-ai/code` CLI) takes MisakaNet through a **plugin
directory** plus a **global rules file**. It does *not* take a user-level MCP config, so this page
is deliberately different from the other client guides — the usual "paste this entry into
`mcpServers`" advice registers nothing here.

> Evidence status: the shape below is measured (issue #3777): with the plugin directory in place,
> `mcode plugin list` reports `misakanet@local enabled` and the tools are visible. The **installer
> side** is covered by this repository's tests (the npx installer and the Python bootstrap write the
> same manifest); the live `mcode` run was not re-executed in this repository's CI — treat it as a
> recipe, not a field report.

## What the installer writes

```bash
npx @misaka-net/misakanet-setup --only mcode
```

| File | What it is |
|---|---|
| `~/.minimax/plugins/misakanet/.claude-plugin/plugin.json` | the plugin manifest mcode reads as source `LOCAL_CLAUDE`; it carries the `misakanet` MCP entry |
| `~/.minimax/AGENTS.md` | the rules block (`misakanet:start` / `misakanet:end`), global scope — applied to every session |

`mcode` is detected by `~/.minimax/` (or the older `~/.minimax-code/`), so running the installer
without `--only` includes it. `--mcp-only` writes the plugin manifest and skips the rules block
(tier ① only).

The manifest the installer writes looks like this:

```json
{
  "name": "misakanet",
  "version": "<installer version>",
  "description": "MisakaNet failure memory: …",
  "mcpServers": {
    "misakanet": {
      "type": "http",
      "url": "https://misakanet.org/mcp",
      "headers": {
        "X-MisakaNet-Agent": "mcode"
      }
    }
  }
}
```

There is **no user-level MCP config to edit**: `~/.minimax/config.yaml` is read for other settings,
but its `mcpServers` key is not. An entry written there looks installed and registers nothing
(measured in #3777). The plugin directory is the only MCP path.

The installer does not overwrite a manifest that is not its own: a `plugin.json` with a different
`name`, or one that is not valid JSON, is left untouched and reported as a manual step.

## Verify

Two checks, because there are two layers:

```bash
mcode plugin list                          # ① the plugin is enabled
npx @misaka-net/misakanet-setup --verify   # ② our files are the ones we wrote
```

* **`mcode plugin list` must show `misakanet@local enabled`.** That string is the criterion — not
  the exit code of `mcode plugin add`.
* `--verify` reports, under 安装完整性, `MiniMax Code：插件清单已注册` and `MiniMax Code：规则块已装`.
* A fresh session should see the usual tool set (8 tools) — ask it something only a lesson answers,
  e.g. `tool call permission denied`.

### `LOCAL_PLUGIN_INSTALL_UNSUPPORTED` is not a failure

`mcode plugin add misakanet@local` answers `LOCAL_PLUGIN_INSTALL_UNSUPPORTED`. That is mcode
refusing to *link* a local plugin through its CLI — it is **not** evidence that the plugin is
missing or broken. While the directory is in place, `mcode plugin list` still shows the plugin
enabled. Deleting the directory to "fix" that error is the one action that breaks the install.

## Proxy machines: set `NODE_USE_ENV_PROXY=1`

mcode budgets roughly **2000 ms** for HTTP MCP discovery. Node's `fetch` does **not** read
`HTTP_PROXY` / `HTTPS_PROXY` unless the runtime is told to, so on a machine behind a corporate
proxy the endpoint never answers inside that budget and the symptom is **"installed, but 0 tools"**
— no error, just an empty tool list.

```bash
export HTTPS_PROXY=http://proxy.example.com:8080   # your proxy
export NODE_USE_ENV_PROXY=1                        # makes Node's fetch honour it
mcode
```

This is a runtime setting on the client side; **no installer can fix it** (`--verify` can only
confirm the manifest). If the tools are missing while `plugin list` is enabled, check this first.

## Rules, and what mcode does not have

`~/.minimax/AGENTS.md` is mcode's **global** rules scope — the block applies to every session, and
a project's own `AGENTS.md` keeps working alongside it. The installer writes the global one (route
A), so a session started anywhere gets the "search before retrying" behaviour.

mcode has **no Claude-Code-style hook mechanism**. There is therefore no checkpoint that counts
turns and no automatic distillation reminder: the rules block asks the agent to submit at a natural
stopping point, and that is all that can be installed. Do not expect a hook line in the config —
there is nowhere for it to go.

## Uninstall

```bash
npx @misaka-net/misakanet-setup --uninstall
```

That removes the rules block from `~/.minimax/AGENTS.md` (the file itself goes away when nothing
else was in it) and deletes `~/.minimax/plugins/misakanet/` — **only** that directory: your other
plugins under `~/.minimax/plugins/` and the parent directories are left alone. Rewritten files keep
a `*.misakanet.bak` copy.

## Learn more

- [MCP quickstart](../mcp-quickstart.md)
- [Full MCP docs](../mcp.md)
- [Token acquisition](token-acquisition.md) — only needed for the write tools
- [All integrations](README.md)
