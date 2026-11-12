# Directory blurbs — the canonical copy, and what is stale where

> Every MCP/DSH directory shows a one- or two-sentence description of MisakaNet. They are edited in
> different places (some read a file in this repository, some are stored on the directory's side), so
> they drift independently — measured 2026-11-13, three of them still quoted a lesson count from
> weeks ago.

## 1. The rule: no counts in a blurb

A blurb that says "385+ lessons" is wrong the week after it is written, and nothing in CI can see it —
the count lives on someone else's server. This repository already solved the same problem for its own
READMEs: the number is a **shields badge** (`data/badges/lessons.json`, refreshed daily), and the prose
does not carry it. Directory blurbs cannot render a badge, so they carry **no number at all**.

If a directory insists on a number, the only durable form is "hundreds of", not a figure.

## 2. Canonical copy (paste this, don't retype it)

**Short (one sentence) — for directories with a single-line field:**

> Failure-memory layer for coding agents: search evidence-rated failure lessons by error text, report
> a gap without an account, and pull the answer by re-query.

**Long (two sentences) — for directories with a paragraph:**

> Never let an agent repeat a bug. MisakaNet is a git-backed failure memory for coding agents:
> evidence-rated lessons, anonymous intakes, and an open, versioned dataset — one MCP call, no account
> needed to read.

**中文（一句话）:**

> 别让一个 agent 再踩同一个坑。MisakaNet 是给编码 agent 的失败记忆库：按证据分级的课程、匿名报料、
> 可版本化下载的开放数据集——一次 MCP 调用即可检索，读取不需要账号。

The English short form is the same string as `server.json` / `glama.json` `description`; if one changes,
change all three in the same commit (`tests/test_version_consistency.py` and
`tests/test_glama_listing_metadata.py` are what notice a version drift, but nothing yet compares the
description).

## 3. What is stale, where, and how to fix it (measured 2026-11-13)

| Directory | Page | What it says today | How to edit |
|---|---|---|---|
| **Glama — connector** | <https://glama.ai/mcp/connectors/org.misakanet/misaka-net> | "Search **385+** failure lessons…" (meta description, og:description, twitter:description, JSON-LD, body) | Glama dashboard → connector settings. One field feeds all five places. |
| **Glama — server** | <https://glama.ai/mcp/servers/Ikalus1988/MisakaNet> | "**500+** Evidence-graded fix lessons, One MCP Call" | Glama dashboard → server description |
| **dsh-plugin.org** | <https://dsh-plugin.org/plugins/ikalus1988/misakanet> | "offering **310+** verified debugging lessons" | their listing dashboard / re-submit |
| MCP Toplist | <https://mcptoplist.com/server/io.github.Ikalus1988%2Fmisakanet> | current (reads `server.json`) | nothing to do |
| dsh.so | <https://www.dsh.so/artifact/misakanet/> | no count | nothing to do |
| dsh.directory | <https://dsh.directory/plugins/ikalus1988/misakanet> | page did not answer 2026-11-13 (20 s timeout) | re-check before editing |
| Smithery | <https://smithery.ai/servers/misakanet/misakanet> | paused (pending upstream changes) | re-check when unpaused |

The three stale blurbs are **not editable from this repository**: Glama stores the strings on its side
(the repo's `glama.json` only supplies name/version/remotes), and dsh-plugin.org has its own listing
record. Replacing them is a dashboard edit with the copy above.

## 4. What can be checked from here

```console
# the repo-side descriptions, which are count-free on purpose
python3 -c "import json;print(json.load(open('glama.json'))['description'])"
python3 -c "import json;print(json.load(open('server.json'))['description'])"

# the external pages, as served (no account needed)
curl -sS -A 'Mozilla/5.0' https://glama.ai/mcp/connectors/org.misakanet/misaka-net \
  | grep -oE '[0-9]{2,4}\+? (failure lessons|lessons)' | head
```

The second command is the one that found the drift; it prints a count when a blurb has grown one.
