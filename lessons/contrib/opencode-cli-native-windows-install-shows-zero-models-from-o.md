---
title: "OpenCode CLI on native Windows lists zero models: WSL-style `file://` paths break plugin loading"
domain: "windows"
tags:
  - "opencode"
  - "windows"
  - "file-url"
  - "plugin-loading"
  - "model-list"
  - "ollama"
  - "npm-package"
  - "wsl-path"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "原生 Windows 上 opencode models 一个模型都不列：opencode.json 里 WSL 风格的 file:// 路径让插件加载失败，另外自定义 provider 的 npm 包没装。"
trigger: "ERR_INVALID_FILE_URL_PATH: File URL path must be an absolute path; Location plugins did not finish activating"
verify: "After `opencode service stop`: `opencode models` lists the provider catalog and `ollama/*` models, and the debug log has no ERR_INVALID_FILE_URL_PATH, plugin-reload error, or /api/model 503."
source: "intake-3800"
provenance:
  issue: "#3800"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# OpenCode CLI on native Windows lists zero models: WSL-style `file://` paths break plugin loading

## Problem

A native Windows install of the OpenCode CLI printed **zero models** for both listing commands:

```bash
opencode models
opencode models --standalone
```

Nothing on stdout said why, and the things that usually break model access looked correct:
`opencode auth list` was fine, the environment variables were set, the provider block in
`opencode.json` was present, and `opencode debug config` / `opencode debug paths` looked normal.

The reason only appears in the debug log, and it appears twice — once at every server start, and once
on the request that should have listed models:

```
level=ERROR message="failed to reload plugins" cause="Cause([Die(TypeError [ERR_INVALID_FILE_URL_PATH]: File URL path must be an absolute path)])"
```

```
GET /api/model http.status=503
ServiceUnavailableError: Location plugins did not finish activating
```

Observed with:

```bash
opencode models --standalone --print-logs --log-level debug
```

The log file tailed during diagnosis was `~/.local/share/opencode/log/opencode.log` (on Windows,
`%USERPROFILE%\.local\share\opencode\log\opencode.log`).

## Root Cause

Two independent faults are stacked, and each one alone produces a misleading symptom.

**1. Two WSL-style paths in `opencode.json` break plugin activation.** The `plugin` and `instructions`
arrays carried paths written in the WSL filesystem style (`/mnt/...`-shaped, as used inside a WSL
distro), wrapped in a `file://` URL. On a **native** Windows install those are not absolute Windows
file URLs, so Node throws `ERR_INVALID_FILE_URL_PATH` while reloading plugins. Plugin activation never
finishes, the model endpoint answers 503 `ServiceUnavailableError: Location plugins did not finish
activating`, and the CLI prints an empty model list instead of an error.

**2. A custom provider contributes zero models when its npm package is not installed, silently.** The
`opencode.json` provider block for the local Ollama endpoint names an npm package (`npm` field:
`@ai-sdk/openai-compatible` in the reporter's config, or whatever package that field names). OpenCode
does not install it; if it is not already in the opencode configuration directory's `node_modules`,
that provider simply contributes no models — no error, just an omission. Fixing the paths alone
restores the cloud catalogs but still leaves `ollama/*` empty, which reads as "the fix did not work".

## Solution

### Step 1: read the resolved config and find every `file://` path

```bash
opencode debug config
opencode debug paths
```

Inspect the `plugin` and `instructions` entries. Any path you would normally use *inside* WSL
(`/mnt/c/...`, `/home/...`) is wrong for a native Windows install.

### Step 2: rewrite those paths as native Windows file URLs

Use an absolute Windows path in URL form: three slashes, drive letter, forward slashes:

```json
{
  "plugin": ["file:///C:/Users/<user>/.../plugin.js"],
  "instructions": ["file:///C:/Users/<user>/.../AGENTS.md"]
}
```

The reporter's config had two such paths across the `plugin` and `instructions` arrays; both have to
be rewritten. The files stay where they are — this is a URL-form fix, not a move.

### Step 3: install the custom provider's package into the opencode config dir

```bash
cd <opencode-config-dir>          # the directory that holds opencode.json
npm install @ai-sdk/openai-compatible
```

Use the package named by the provider's `npm` field. It has to live in the opencode config directory's
`node_modules` — that is where the reporter installed it; installing it in an unrelated project
directory is not the configuration that was verified.

### Step 4: restart the service and list again

```bash
opencode service stop
opencode models
```

On the reporter's machine this returned 66 models, including the local `ollama/*` models and the
`opencode/*` / `anthropic/*` catalog, with no 503 or plugin errors in the debug log.

## Verification

Re-run the command that failed before:

```bash
opencode models --print-logs --log-level debug
```

Pass criteria, all three at once:

- the output lists models again, including the custom provider's `ollama/*` entries;
- the debug log contains no `ERR_INVALID_FILE_URL_PATH` and no `failed to reload plugins`;
- no `GET /api/model http.status=503` / `ServiceUnavailableError: Location plugins did not finish
  activating`.

The reporter's count after the full run was 66 models. Treat "the catalog is listed **and** the custom
provider's entries are present" as the portable criterion, not the number.

## Notes

- Evidence E1: the reporter fixed and measured this on their own host (66 models after both fixes); it
  was not reproduced in this repository.
- Zero models with a clean `auth list` and a clean provider block rules out neither cause: plugin URL
  errors are not provider configuration, and a missing npm package is not an auth problem.
- The 503 is downstream of the plugin reload failure. Re-authenticating or retrying the listing command
  does not help while plugin activation is failing.
- Fix both faults before judging the result. With only the paths fixed, the catalog comes back but a
  custom provider whose `npm` package is missing still shows no models.
- Native Windows only: the same `/mnt/...` paths are correct inside WSL, so a config copied out of a WSL
  install needs this rewrite.
