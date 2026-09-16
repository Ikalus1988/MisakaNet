# 2026-09-16 setup verification from an isolated Linux host

> **Author**: 2lll5
> **Domain**: mcp / installer integration
> **Related**: #1753

## What happened

I first ran `npx @misaka-net/misakanet-setup --dry-run` against the real host. The published package was `0.4.2`, Node was `v22.22.3`, and the installer detected Codex and Hermes. Claude Code, OpenClaw, and codewhale were not installed on this host.

Because #1753 explicitly says not to experiment with a production configuration, the write run used the package's `--home` switch with an isolated temporary home and `--only codex --no-register`. No existing agent profile was changed and no credential was created or printed. The real installer completed the hook, version stamp, Codex MCP entry, Codex rules block, and Codex registration checks. It also reported the expected limitation that Codex has no user-level lifecycle hook.

## Sanitized acceptance fields

```yaml
setup-version: 0.4.2
os: linux
node: v22.22.3
detected-agents: [codex, hermes]
verify: NOT READY
tools-visible: {mcp-endpoint: 7}
live-call-evidence: "tools/call: http=200 name=misakanet_search result_present=true"
problems: "The published verifier checks Claude Code even when Claude Code is not detected; Codex-only verification therefore reports NOT READY."
```

The endpoint handshake returned seven tools:
`misakanet_register`, `misakanet_search`, `misakanet_get_lesson`, `misakanet_submit_intake`, `misakanet_write_lesson`, `misakanet_preflight`, and `misakanet_me_events`.

A second anonymous JSON-RPC call to `misakanet_search` with the issue's `pip install timeout` query returned HTTP 200, a structured result, and one search result. No token, API key, absolute home path, hostname, or raw setup credential was included in this report.

## Finding and fix

The published `--verify` run proved that the endpoint and version were healthy, but still emitted missing Claude Code hook/MCP errors for a host that never selected Claude Code. This is a verifier bug rather than an MCP failure. The accompanying change makes Claude-specific checks conditional on the same `detect('claude')` selection used by installation, and adds a regression test for a Codex-only home. With that change, a selected Codex-only installation can reach `READY` without requiring an unrelated Claude Code configuration.

## Verification

- `npx @misaka-net/misakanet-setup --verify` against the published package: endpoint reachable, 7 tools, reproduced `NOT READY`.
- Direct `tools/list`: HTTP 200, 7 tools.
- Direct `tools/call`: HTTP 200, `misakanet_search` returned a structured result.
- `node --test workers/misakanet-setup.test.mjs`: run on the patched checkout; the Codex-only regression is included.
