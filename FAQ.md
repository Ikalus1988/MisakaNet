# MisakaNet FAQ

This page collects the questions that most often come up when installing,
pairing, troubleshooting, or contributing to MisakaNet. Commands assume that
the shell is running from the root of a MisakaNet checkout unless stated
otherwise.

## Getting started

### 1. What is MisakaNet?

MisakaNet is a searchable, redacted failure-memory layer for AI coding agents
and developers. It stores lessons in the repository so an agent can search for
a known failure, read the documented root cause, and verify the fix before
retrying. A lesson is not an executable skill: it describes a failure and its
recovery path.

See the [README overview](README.md#what-is-the-failure-memory-network) and
the [architecture guide](ARCHITECTURE.md).

### 2. What do I need to run the local search?

Use Python 3.10 or newer, Git, and the MisakaNet checkout. The core search
engine is designed to stay dependency-light, but the command-line entry point
uses the separately published misakanet-core package:

```bash
git clone https://github.com/Ikalus1988/MisakaNet.git
cd MisakaNet
python3 -m pip install misakanet-core
python3 search_knowledge.py "database locked"
```

The project metadata lists Python >=3.10; optional integrations are described
in the [quickstart](docs/quickstart.md).

### 3. Why does ModuleNotFoundError: No module named misakanet_core appear?

The core package is not the same thing as the repository package. Install the
PyPI dependency in the active interpreter, then retry:

```bash
python3 -m pip install misakanet-core
python3 search_knowledge.py "DCO sign-off"
```

Using python3 -m pip helps ensure that pip installs into the interpreter that
will run the search command.

### 4. Can I try MisakaNet without installing Python locally?

Yes. The quickstart documents the GHCR image:

```bash
docker pull ghcr.io/ikalus1988/misakanet:latest
docker run -i ghcr.io/ikalus1988/misakanet:latest search_knowledge.py "database locked"
```

Docker must be installed and running. For an MCP client, use the same image as
the command in the client's MCP configuration.

### 5. Do I need a GitHub account?

No for searching or for the email intake path. You can send a redacted story to
bot@misakanet.org; the [email intake guide](docs/email-intake.md) explains what
is accepted and how personal data and secrets are handled. A GitHub account is
still recommended for code changes because a PR provides CI, DCO, review, and
an auditable history.

### 6. How do I register a node?

The web path is to open [misakanet.org](https://misakanet.org/), enter a node
name, and choose **Register**. The API and email alternatives are documented
in [JOIN.md](JOIN.md#join-as-a-node-optional-but-recommended) and the
[CLI reference](docs/cli-reference.md). Registration is optional for local
lesson search.

## Pairing and MCP

### 7. What is the quickest way to connect a remote MCP client?

Open the [connect page](https://misakanet.org/connect), choose **Generate
Code**, and add the returned bearer token to the MCP configuration:

```json
{
  "mcpServers": {
    "misakanet": {
      "url": "https://misakanet.org/mcp",
      "headers": {"Authorization": "Bearer YOUR_TOKEN"}
    }
  }
}
```

Restart the client after saving its configuration, then ask it to search for a
concrete error. Treat the token like a credential and do not commit it.

### 8. How do I configure the local MCP server?

Point the MCP client at the repository's scripts/mcp_server.py using an
absolute path. For example:

```json
{
  "mcpServers": {
    "misakanet": {
      "command": "python3",
      "args": ["/absolute/path/to/MisakaNet/scripts/mcp_server.py"]
    }
  }
}
```

The same shape works in Claude Code, Claude Desktop, and Cursor; the location
of each client's configuration file differs. See the
[MCP quickstart](docs/mcp-quickstart.md) for client-specific examples.

### 9. How can I smoke-test the local MCP setup?

Start the stdio server with an empty input stream and run a direct search before
debugging the MCP client. An empty stream lets the process exit after checking
imports; an MCP client keeps stdin open during normal use:

```bash
python3 scripts/mcp_server.py </dev/null
python3 search_knowledge.py "DCO sign-off" --top=3
```

If both commands work, restart the MCP client and make a first query through
the client. This separates Python/index problems from client configuration
problems.

### 10. Why does my MCP client say that MisakaNet was not found?

The most common causes are a relative script path, a stale client process, or
an invalid JSON configuration. Use an absolute path, validate the JSON, run
python3 scripts/mcp_server.py </dev/null from the checkout, and restart the
client. The [MCP troubleshooting section](docs/troubleshooting.md#mcp-server-not-discovered-by-claudecursor)
has the same checklist.

## Searching and lessons

### 11. How do I make a search more useful?

Start with the exact error text or a distinctive phrase, then narrow or widen
the result set with the CLI flags:

```bash
python3 search_knowledge.py "pip install timeout" --top=5
python3 search_knowledge.py "token expired" --domain=devops --json
python3 search_knowledge.py "database" --broad --titles
```

The --json flag is useful for scripts, --titles gives a compact list, --domain
filters by domain, and --broad expands matching. The full option list is in
the [CLI reference](docs/cli-reference.md#search_knowledgepy--core-search-tool).

### 12. Why did a search return no results?

First confirm that you are in the repository root and have the current lesson
files:

```bash
git pull --ff-only
python3 -m pip install misakanet-core
python3 search_knowledge.py "a distinctive error phrase" --top=10
python3 search_knowledge.py "timeout" --broad --top=10
```

The CLI uses exit code 1 for no results or an error. A no-result search is a
signal to try a more specific phrase, a broader query, or the public lesson
index. Do not treat an unverified result as a fix.

### 13. How do I read the full lesson behind a result?

The result includes a repository path. Read that file locally, or fetch the
corresponding raw file when you are working outside the checkout:

```bash
python3 search_knowledge.py "DCO sign-off" --json --top=3
curl -sS https://raw.githubusercontent.com/Ikalus1988/MisakaNet/main/lessons/core/dco-auto-fix-workflow.md
```

Review the **Problem**, **Root Cause**, **Solution**, and **Verification**
sections before applying commands from a community lesson.

### 14. What should I do when no lesson matches my failure?

Do not invent a fix from a weak match. Redact secrets and personal data, then
submit a small failure note through the
[lesson-feedback form](https://github.com/Ikalus1988/MisakaNet/issues/new?template=lesson-feedback.yml)
or use the queue helper:

```bash
python3 scripts/queue_lesson.py \
  --title "Short error description" \
  --domain general \
  "Root cause: ... Fix: ... Verification: ..."
```

Maintainers review the draft before it becomes a published lesson.

## Contributing

### 15. What makes a useful lesson contribution?

Include the exact error or symptom, the environment when it matters, the root
cause, a copy-pasteable solution, and a verification step. Keep the lesson
focused on one failure pattern. Never include access tokens, private logs,
email addresses, or other secrets. The [lesson checklist](docs/lesson-checklist.md)
has the review criteria.

### 16. How do I submit a lesson by pull request?

Create the file under lessons/contrib/, add frontmatter with at least a title,
domain, tags, and status, then run the relevant checks before opening a PR:

```bash
git checkout -b docs/my-failure-lesson
git add lessons/contrib/my-failure-lesson.md
git commit -s -m "docs: add lesson for my failure"
git push origin docs/my-failure-lesson
```

The [contribution quickstart](docs/quickstart.md#step-2-contribute-a-lesson-2-minutes)
contains a complete frontmatter example. The -s flag adds the required DCO
sign-off.

### 17. What does a DCO failure mean, and how do I fix it?

The commit is missing a Signed-off-by trailer. Amend a single-commit branch
and push it safely:

```bash
git commit --amend --signoff --no-edit
git push --force-with-lease
```

For multiple commits, sign off each commit before pushing. See the
[DCO troubleshooting entry](docs/troubleshooting.md#dco-sign-off-failed) and
the repository's DCO guide for Windows-specific details.

### 18. How do I report a bug or onboarding problem?

For a reproducible software failure, open a GitHub issue with the command,
environment, exact error, and a redacted reproduction. For onboarding or UX
friction, use the [journey report issue #510](https://github.com/Ikalus1988/MisakaNet/issues/510)
or the email intake path. Do not paste credentials or unredacted logs into an
issue.

### 19. What should I do if a token was committed or exposed?

Revoke or rotate it immediately, remove it from the working tree and history,
and then open a clean replacement commit. Do not rely on deleting the latest
file alone: Git history and CI logs may still contain the secret. The
[token/secret troubleshooting guide](docs/troubleshooting.md#github-token-exposed--secret-scan-blocked)
lists the recovery sequence.
