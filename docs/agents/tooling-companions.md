# Companion MCP servers: GitHub for repo operations

MisakaNet answers one question — *"has someone hit this before, and how did they fix it?"* — and it
answers it from a curated lesson corpus. It deliberately knows nothing about your repository's issues,
pull requests or CI runs. When an agent is working **inside a repo**, that missing half shows up
immediately: triage means reading issues, review means reading a diff and its checks, and debugging CI
means reading a run.

[GitHub's MCP server](https://github.com/github/github-mcp-server) is that half. This page says when to
reach for it, when not to, and the settings that keep it from becoming a second, unaudited way into the
repository.

> **This repository does not install, bundle or ship it.** Nothing in `install_misakanet_agent.py`
> configures it, and nothing in CI calls it. It is a tool *you* add to *your* agent, with *your* token.

## The division of labour

| Question | Server |
|---|---|
| "Has someone hit this error before?" | **MisakaNet** (`https://misakanet.org/mcp`) |
| "What did the reviewer ask for, and did CI pass?" | **GitHub MCP** |
| "Which lessons does this repo's failure resemble?" | **MisakaNet** |
| "Open an issue for this failure so a human sees it" | **MisakaNet** (`misakanet_submit_intake`) — it does the redaction and the receipt |
| "Close this issue, label that one, merge the PR" | **neither**: use `gh`/REST so the action is in a transcript the repo can audit |

The last row is the load-bearing one. MisakaNet's intake is auditable because every report becomes an
issue with a receipt; a write through an interactive MCP server is just a tool call in a session.

## Use it for reads

Good fits, and the reason each is better here than a shell string:

* **Issue and PR triage** — the repo's own scripts learned this the hard way: `question_autopilot` read
  one page and concluded the backlog was 12 questions (it was 54), and `behindBy` compared the index
  against the wrong denominator. Structured tools paginate; hand-rolled `gh` invocations forget to.
* **CI investigation** — `actions_list` / `actions_get` / `get_job_logs` turn "why is this red" into a
  few tool calls instead of `gh run view --log | grep`.
* **Code reading at a known ref** — `get_file_contents` with `ref:` is cheaper and safer than a base64
  round-trip through the REST API.

## Do not use it for CI automation

An MCP server is an interactive protocol driven by a model. Workflows need the opposite: deterministic,
bounded, reviewable calls. There are three concrete costs to putting one on a runner:

1. **Credential surface.** A PAT good enough for the toolsets below carries `repo`; `GITHUB_TOKEN` in a
   workflow carries what the job needs and expires with it.
2. **Non-determinism.** "The agent chose `update_issue`" is not a step anyone can review; `gh api -X
   PATCH …` is.
3. **Supply chain.** A Docker image or Go binary on a runner is a new unverified execution path — the
   exact class of finding this repo spent 2026-10-31 closing on the installer side (pin the ref, check
   the digest, refuse to run what you cannot vouch for).

## Configuration that is safe by default

Read-only, narrow toolsets, token from the environment, image version pinned. The PAT never belongs in
a config file — same rule as `docs/maintainer/credentials-and-environments.md`.

```bash
# Claude Code. `GITHUB_PAT` comes from your environment, never from the command's history if you can
# avoid it (`claude mcp add` records the flag values in its config).
claude mcp add github --transport stdio \
  -e GITHUB_PERSONAL_ACCESS_TOKEN \
  -- docker run -i --rm \
     -e GITHUB_PERSONAL_ACCESS_TOKEN \
     -e GITHUB_TOOLSETS=context,repos,issues,pull_requests,actions \
     -e GITHUB_READ_ONLY=1 \
     ghcr.io/github/github-mcp-server
```

Why each part:

| Setting | What it removes |
|---|---|
| `GITHUB_READ_ONLY=1` | every write tool, **including** ones named explicitly in `--tools` |
| `GITHUB_TOOLSETS=context,repos,issues,pull_requests,actions` | `code_security`, `dependabot`, `discussions`, `gists`, `orgs`, `secrets` — each is context the model pays for and a surface you did not ask for |
| `context` in the list | it is the toolset the server itself calls "strongly recommended": without it the model does not know which user/repo it is operating on |
| token by env var | a PAT in a config file is a PAT in a backup, a screenshot and a support paste |
| the image tag | `ghcr.io/github/github-mcp-server` is `latest`; pin the digest or the version your review covered |

Prefer no token at all? The **remote** server (`https://api.githubcopilot.com/mcp/`) supports OAuth on
hosts that implement it, so the credential stays out of your files entirely. The local server also
supports OAuth (browser flow, token kept in memory) — PAT is the fallback, not the default.

## Tool-choice hygiene

Two MCP servers in one session is ordinary; three start competing for the model's attention. If both
are connected, say which is which in the system prompt — one line is enough:

> Use **GitHub MCP** for repository operations (issues, PRs, CI). Use **MisakaNet** before debugging:
> search it with the error text, and submit an intake when it has nothing.

That sentence is also why this page exists: an agent that searches MisakaNet *and* can read the repo
around it is the version of the workflow this project is built for. The failure memory supplies the
prior; the repo read supplies the specifics.
