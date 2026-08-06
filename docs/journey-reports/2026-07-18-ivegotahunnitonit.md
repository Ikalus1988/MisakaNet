# MisakaNet Journey Report

## Environment
- Date: 2026-07-18
- Browser / OS: Chrome / Windows 10 (GCP VM: Debian Linux 11)
- GitHub username: ivegotahunnitonit
- Optional: MCP client / agent used: Antigravity AI Coding Assistant (pair programming)

## Steps Completed
- [x] README understanding
- [x] Website / node registration
- [x] Lesson search and use
- [x] Guard / test bug investigation
- [ ] Bot email feedback path
- [ ] Optional human feedback

## Findings

### What worked
- **Documentation & Onboarding clarity**: The `README.md` does a fantastic job of separating the concept of a **Lesson** (failure-memory) from a **Skill** (executable capability), preventing the common pitfall of treating MisakaNet as another tool directory.
- **CLI Search speed**: Running `python3 search_knowledge.py` on the VM with zero dependencies works instantly and outputs readable TAP-compatible results.
- **Node registration UI**: The website at `https://misakanet.org/` loaded quickly and provided a seamless form for node onboarding.

### What was confusing
- **Obsolete repository references**: Some guides (specifically `docs/agents/node-injection.md`) were referencing a home folder named `~/Agent-Medici` instead of `~/MisakaNet` for synchronization command blocks, which could lead to copy-paste errors for new operators.
- **Glossary broken links**: The `docs/glossary.md` file linked to `../scripts/score_lesson.py` for quality scoring, but this script is no longer present in the root `scripts/` folder (the feature appears to be unified into `search_knowledge.py --score`).

### Bugs or edge cases found
- **Gmail-style forwarding gap**: The email registration worker had a marked "known gap" in its tests where Gmail-style forwarded message headers (`---------- Forwarded message ----------`) were not stripped from incoming text, leaving redundant headers in the extracted lesson body.

### Suggested improvements
- We have addressed the `~/Agent-Medici` obsolete path references by replacing them with `~/MisakaNet` in `docs/agents/node-injection.md`.
- We resolved the "known gap" in the email intake pipeline by adding forwarding header patterns to the parser in `workers/email-register/src/email-utils.mjs` and updated the test assertions to ensure these headers are cleanly stripped.

## Evidence

### Test Run Verification
After applying the email forwarding header parser changes, all 20 tests pass successfully:
```
# Subtest: strips Gmail-style forwarded message headers
ok 15 - strips Gmail-style forwarded message headers
  ---
  duration_ms: 0.280527
  type: 'test'
  ...
1..20
# tests 20
# suites 0
# pass 20
# fail 0
# cancelled 0
# skipped 0
# todo 0
# duration_ms 149.434383
```

## Privacy
- [x] I confirm that this report does not contain private secrets, personal API tokens, or sensitive environment configurations.
