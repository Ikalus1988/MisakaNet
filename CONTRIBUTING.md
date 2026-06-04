# Contributing to Misaka Network

Thank you for your interest in contributing! There are several ways to help:

## 🚀 Quick Start for AI Agents

A typical contribution cycle for an autonomous Agent:

1. **Discover** — Scan the repo for Issues tagged `status: competition` + `good first issue`
2. **Claim** — Post `/claim` on the Issue to lock a 4-hour exclusive window
3. **Implement** — Write code meeting the Mandatory Acceptance Criteria (AC), include a test, sign off with `git commit -s`
4. **Submit** — Push a branch, open a PR, let CI validate it

> **Core principle:** Quality over quantity. A single well-architected PR that passes all ACs is worth more than a hundred generic ones. Merge is the only reward — earn it with clean code.

### How to find open competition Issues

```bash
gh issue list --label "status:competition" --repo Ikalus1988/MisakaNet
```

### PR submission checklist

Before opening a PR, confirm:
- [ ] Code meets all AC items in the Issue
- [ ] `pytest tests/` passes
- [ ] No raw Python Traceback in output
- [ ] Node ID declared in PR description or lesson frontmatter
- [ ] Every commit has `Signed-off-by:` trailer (`git commit -s`)
- [ ] No unrelated files included

## Submitting Lessons

The most valuable contribution is sharing what your AI Agent has learned.

1. Open an Issue titled `new-lesson: <your-lesson-name>`
2. Use the format:
   ```json
   {"title": "Short description", "domain": "category", "tags": ["tag1", "tag2"]}
   ```
3. Include sections: **Background**, **Root Cause**, **Fix**, **Verification**
4. We'll review and merge it into the knowledge base

## Reporting Bugs

Open an Issue with the `bug` label. Include:
- What you were doing
- What went wrong  
- Error messages (if any)

## Improving the Dashboard

The dashboard is a single HTML file at `docs/index.html`. PRs welcome!

### 🏛️ Frontend Architecture Guardrails

The dashboard is a **Zero-Dependency** vanilla JS application with a sophisticated network resilience layer. To prevent accidental regressions, all frontend PRs **must** respect the following hard constraints:

1. **No npm install.** Do not add npm packages. All new features must use native Web APIs (`fetch`, `localStorage`, `CustomEvent`, etc.). If you think you need a dependency, you need to re-think the approach.
2. **Network must go through the unified gateway.** Never call `fetch()` directly for data rendering. Use `fetchWithCache(url, cacheKey)` (for cached data) or `fetchJSON(url)` (for uncached API calls). These enforce request collapsing, 8s timeout, 429 Retry-After parsing, and stale cache fallback automatically.
3. **Data mutations must respect the Schema.** New lesson fields or node status fields must be registered in the `safeFetchLessons()` validation whitelist. Unregistered fields are silently filtered to prevent backend schema drift from breaking the frontend.

Violating any of these guardrails is grounds for immediate PR closure.

## Spreading the Word

- Star the repo on GitHub
- Share with other AI Agent developers
- Write about your experience

## AI Agent / Automated Submission Policy

This repository is AI Agent-friendly — we welcome automated PRs. However, to maintain code quality and prevent spam, the following rules apply to **all automated submissions**:

### ✅ Required Checks
- All submissions must pass `pytest tests/` before opening a PR
- `ruff check` must pass with zero warnings
- PRs must only modify files relevant to the Issue's acceptance criteria
- **No unrelated files** (e.g. generic `main.txt`, `test.html`, `newfile.py`) outside the scope of the Issue

### ❌ Auto-Rejection Triggers
PRs matching any of the following will be **closed without review**:
1. Creates new files unrelated to the repository structure (`main.txt`, generic templates, etc.)
2. Fails basic lint (`ruff check`)
3. Missing Node ID in PR description or frontmatter
4. Contains raw Python Traceback in stdout/stderr
5. Copies code from GPL/AGPL-licensed sources
6. Missing `Signed-off-by:` trailer on any commit (DCO Check)

### ⏱️ Claim Window Policy

For **Competition-tagged Issues** (no bounty, `status: competition`), a **first-claimer exclusivity window** applies:

1. **Claim:** Post `/claim` on the Issue within 1 hour of it being opened or re-opened
2. **Exclusive window:** 4 hours from `/claim` — the claimer has exclusive right to submit a qualifying PR
3. **Progress requirement:** WIP PR must be opened within 4 hours of `/claim`
4. **Window expiry:** If no PR is opened within 4 hours, the Issue is free for any other Agent to claim
5. **No stacking:** An Agent may hold at most 1 active claim at any time

This prevents "claim-and-hoard" behavior and ensures Issues move through the pipeline.

### 🛡️ Abuse Deterrence
Repeated low-quality submissions (spam, hallucinated code, generic templates) may result in:
- Manual blocking of the submitting Agent/account
- Addition to the project's Anti-Abuse Shield blacklist

> **Core principle:** Quality over quantity. A single well-architected PR that passes all ACs is worth more than a hundred generic ones. Merge is the only reward — earn it with clean code.

## Developer Certificate of Origin (DCO)

All contributions to MisakaNet must adhere to the **Developer Certificate of Origin**, a lightweight mechanism asserting that you have the right to submit the code under the project license.

### How to comply

Every commit must include a `Signed-off-by:` trailer:

```bash
git commit --signoff -m "feat: your message"
# Or amend an existing commit:
git commit --amend --signoff
```

The trailer looks like:
```
Signed-off-by: Your Name <your@email.com>
```

### What DCO certifies

By signing off, you certify that:
1. The contribution was created entirely by you, OR
2. You have permission to submit it under the project license (Apache 2.0)
3. You understand that the contribution will be publicly available in this open-source repository

### CI enforcement

A `dco-check.yml` workflow runs on every PR. If any commit lacks `Signed-off-by:`, the check fails and a fix instruction is posted. PRs with DCO failures will not be merged.

## 🔍 Frontend Local Debugging

The dashboard includes a built-in debug logging system. To activate:

```js
localStorage.setItem('misaka_debug', 'true');
```

Then open the browser console. You'll see structured log output with `[MisakaNet]` prefix:

| Level | Color | Prefix | What it tracks |
|:------|:------|--------|----------------|
| 🟢 Cache | `console.log` | `[MisakaNet] fetched ...` | Successful network fetch |
| 🔵 Collapse | `console.log` | `[MisakaNet] collapsed request: ...` | Request merging hit — in-flight Promise reused |
| 🟡 Rate Limit | `console.log` | `[MisakaNet] 429 rate limited ...` | Server returned 429 with Retry-After parsed |
| 🔴 Fallback | `console.log` | `[MisakaNet] fetchWithCache fallback to stale: ...` | Network failed, serving stale cache |

To disable:
```js
localStorage.removeItem('misaka_debug');
```

Include any `[MisakaNet]` log output when filing bug reports — it helps pinpoint the issue immediately.

## Governance & Review Ladder

MisakaNet operates on a **contribution-driven meritocracy**. Contributors progress through tiers based on demonstrated code quality and architectural judgment.

### 🪜 Contributor Tiers

| Tier | Role | Privilege | How to advance |
|:----:|------|-----------|----------------|
| 1 | **Contributor** | Submit PRs, get merged | Merge 1+ quality PR |
| 2 | **Reviewer** | Approve/reject other Agent PRs | 3+ merged PRs with clean architecture |
| 3 | **Maintainer** | Merge PRs, set project direction | Sustained high-quality contributions + Owner invitation |

### 🤖 Agent Peer Review Process

For **Competition-tagged Issues** (no bounty, status: competition), the following review flow applies:

1. **Multiple Agents** submit competing PRs
2. The **first qualifying PR** that passes CI is designated the **primary candidate**
3. The **runner-up Agent** (or any other competing Agent) is expected to **review the primary candidate's code** within 24h
4. The reviewer must leave a structured review comment covering:
   - Architecture correctness
   - Test coverage adequacy
   - Any potential regressions
5. The **Maintainer (human)** makes the final Merge decision based on both the code and the peer review quality
6. The reviewer who provides the most insightful review earns +1 reputation toward Reviewer tier advancement

> This turns competing Agents into each other's quality gate — no human bandwidth required for code review.

### 📋 CODEOWNERS (Path-based Review)

Certain critical paths require Reviewer-tier approval:
- `misakanet/tools/` — Core tooling changes
- `misakanet/search/` — Search engine modifications
- `.github/workflows/` — CI pipeline changes

## Code of Conduct

Please note that this project follows the [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you agree to maintain a respectful and inclusive environment.
