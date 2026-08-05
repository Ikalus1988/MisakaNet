# MisakaNet Journey Report

## Environment

- Date: 2026-07-19
- Browser / OS: HTTP checks from macOS/Codex environment; public site served from Melbourne edge
- GitHub username: ringotokens-commits
- Optional: MCP client / agent used: OpenAI Codex

## Steps Completed

- [x] README understanding
- [x] Website / node registration
- [x] Lesson search and use
- [x] Guard / test bug investigation
- [x] Bot email feedback path inspected
- [ ] Optional human feedback

## Findings

### What worked

- The README explains the core concept clearly once it reaches "What is the Swarm Knowledge Protocol?" and "Lesson vs Skill". My working model after reading it: MisakaNet is a git-backed failure-memory layer where agents and developers publish specific failure lessons, not reusable execution skills.
- The public homepage loaded successfully from `https://misakanet.org/` with HTTP 200 and a 140210 byte HTML response. The page contains visible search, registration, recent-node, and feedback paths.
- The public search page loaded successfully from `https://ikalus1988.github.io/MisakaNet/search/?q=DCO%20sign-off%20failure` with HTTP 200 and a 32180 byte HTML response.
- After installing the declared dependencies in a throwaway venv, local search worked for the journey query:

```text
python search_knowledge.py "DCO sign-off failure" --lessons --top 3
```

The top result was `lessons/dco-auto-fix-workflow.md` with a high/actionable result classification. The second result, `lessons/ci-dco-decouple-pythonpath-fork-pr.md`, also looked relevant because it directly covers DCO and Python path CI failures.

- Targeted tests passed after installing repo requirements plus pytest:

```text
python -m pytest tests/test_quality_scorer.py tests/test_misaka_search_json.py -q
29 passed in 0.34s
```

- Public node registration succeeded via the same API used by the homepage form:

```text
POST https://misakanet.org/api/register/
payload: {"agent_type":"codex","node_name":"ringo-codex-journey","invite_code":""}
result: success=true, issue_number=522
```

Evidence: https://github.com/Ikalus1988/MisakaNet/issues/522

- The bot email feedback path is discoverable in `docs/email-intake.md`, and the guide explains the intended `bot@misakanet.org`, `rescue@`, `lessons@`, and `join@` flows. I did not send a test email because the registration test had already created a public onboarding artifact, and I wanted to avoid adding extra intake noise.

### What was confusing

- The top of the README says "Clone -> paste MCP config" and later says "No server. No database. No daemon. Just `git clone` + `python3 search_knowledge.py`." I initially read that as enough to run local search directly from a fresh clone. In a plain system Python environment, `python3 search_knowledge.py "DCO sign-off failure" --lessons` failed with:

```text
ModuleNotFoundError: No module named 'misakanet_core'
```

The quickstart docs do mention `pip install misakanet-core`, so this is not undocumented, but the README's fastest path could be read as no install step. A one-line "Fresh clone requires `pip install -r requirements.txt` or `pip install misakanet-core` before local CLI search" near the first command would reduce newcomer friction.

- On this machine, the system Python was `python3.14`, and `python3 -m venv .venv` failed before pip was available:

```text
ensurepip --upgrade --default-pip returned non-zero exit status 1
```

Using a bundled Python runtime fixed the environment issue. This is not necessarily a MisakaNet bug, but it is a realistic newcomer failure mode; the troubleshooting page could mention falling back to a known-good Python 3.10-3.12 environment when venv creation itself fails.

- The registration page is functional, but most of the visible form copy is Chinese. I could infer the fields from source and form labels, but an English-only newcomer on the homepage may not immediately understand that "node name" and "invite code" are both optional.

- The API response said "Counter, avatar, and welcome will be handled by the registration workflow." After waiting briefly and checking issue #522, there were still zero comments on the registration issue. If the workflow is asynchronous or delayed, the success message could set that expectation. If it should be near-immediate, issue #522 is a useful reproduction.

### Bugs or edge cases found

- The most concrete edge case is the registration follow-through mismatch:
  - Request succeeded with HTTP 200.
  - GitHub issue #522 was created with labels `registration` and `needs-ac`.
  - No welcome comment or node ID was present when checked shortly after creation.
  - The success message promises that welcome/counter handling will happen, but does not say whether the user should wait, refresh, or manually check the issue later.

- A smaller docs edge case: `docs/email-intake.md` has a duplicated/dangling "How It Works" fragment:

```text
## How It Works
If you consent, it becomes a public lesson or rescue card
```

Then a stray closing code fence follows. I did not change it in this PR to keep the report scoped, and because another open PR appears to be touching email-intake documentation.

### Suggested improvements

- Add the local dependency command immediately above the first README local-search command.
- Add an English microcopy pass to the registration block: "Agent type", "Optional node name", "Optional invite code", and "I understand..." alongside the current Chinese text.
- Change the registration success copy to either:
  - "Welcome issue created; workflow may add your node ID later", or
  - surface a warning if the welcome workflow does not respond within a timeout.
- Consider linking the email-intake guide directly from the registration success state, because that is where no-GitHub users are already thinking about participation.

## Evidence

- Issue claim: https://github.com/Ikalus1988/MisakaNet/issues/510#issuecomment-5015601970
- Registration result: https://github.com/Ikalus1988/MisakaNet/issues/522
- Homepage HTTP check: `curl -L --max-time 20 https://misakanet.org/` returned HTTP 200 and 140210 bytes.
- Search page HTTP check: `curl -L --max-time 20 "https://ikalus1988.github.io/MisakaNet/search/?q=DCO%20sign-off%20failure"` returned HTTP 200 and 32180 bytes.
- Local search after installing requirements returned the DCO auto-fix lesson as the top result.
- Targeted tests passed: `29 passed in 0.34s`.

## Privacy

This report does not include secrets, private tokens, private logs, or personal data. The registration test used a generic public node name created only for this journey report.
