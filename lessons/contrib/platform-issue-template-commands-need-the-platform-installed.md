---
domain: "meta"
title: "Copying a platform's issue template pastes commands the target repo never wired up"
tags: [github, issue-templates, opire, contribution, verification, agent]
status: "published"
evidence_level: "E2"
summary_plain: "A platform's issue template carries slash-commands that only run where that platform is installed."
trigger: "asked to copy a platform's issue template, e.g. Opire /reward /try /claim, into a repo that is not integrated"
verify: "On the fixed body, counts of /reward|/try|/claim|/tip and of reward/tip are 0 while the heading prefix and sections remain; the raw template counts 4 commands."
provenance:
  issue: "#3418"
  source: "MCP intake (claude-code), question"
---

# Copying a platform's issue template pastes commands the target repo never wired up

## Problem

A task said, in effect, "file this issue using the platform's template". The agent copied
the template body verbatim — heading prefix, sections, and the collapsible banner at the
bottom. That banner is not decoration: its text is a set of slash-commands aimed at the
platform's bot.

```text
💵 Everyone can add rewards for this issue commenting `/reward 100` …
🕵️ … they can comment `/try` to let everyone know!
🙌 … they can comment `/claim #3418` …
🪙 Also, everyone can tip any user commenting `/tip 20 @user`
```

Two things went wrong when it was pasted into a repository that had never installed that
platform:

1. **The commands are dead text.** Nothing in the target repo parses `/reward`, `/try`,
   `/claim` or `/tip`. They read like actions and are not actions, so a reader who follows
   them gets no reward, no claim, no tip — the issue promised a mechanism that does not exist
   there. (In this repository they *are* handled, but by the platform's GitHub App, not by
   anything in the checkout: `grep -rn opire .github/workflows/ pyproject.toml package.json`
   is **0 hits** even here.)
2. **The banner's invitation can contradict the task.** The same block says "Everyone can add
   rewards", while the task was explicitly a **zero-bounty** one. Copying "for fidelity to the
   template" imports a promise opposite to the stated intent.

Measured on a scratch target with no platform app, the copied block carries 4 command tokens
and 5 invitation tokens; the target's configuration surfaces carry 0 references to the
platform.

## Root Cause

**A template is the entry point to a mechanism, not a layout.** The commands in it are
executed by something *outside* the repository — an installed GitHub App or bot webhook that
watches comments. The repository's own files contain no wiring for them, which is why the
integration check is a `grep` and not a run: if the platform's name is absent from the config,
workflows and dependency manifests, the commands cannot fire.

Two habits produce the failure:

- treating "use the template" as a typography instruction, so the *skeleton* and the
  *command block* are copied as one unit;
- adopting without checking intent, when a template is written for the platform's users and
  may *invite* the exact behavior the task wants to suppress.

Adoption also skipped the corpus, which had already recorded this platform as a source of
noise. `scripts/question_autopilot.py:178-184` strips the `<details>` banner before clustering
issues because its vocabulary (`reward`, `claim`, `everyone`, `add`) appears in *every*
signature — shared tokens are the definition of noise for a clustering step. And
`CONTRIBUTING.md:8` already states that offers carried by that banner are **unverified** and
that the project administers none of them.

## Solution

Check three things before pasting an external template, then keep only the skeleton.

### Step 1 — Is the platform integrated with the target repo?

Search the surfaces that would have to change for the commands to work:

```bash
grep -rniE '<platform>' .github/workflows/ pyproject.toml package.json .github/*.yml
```

Zero hits means **not integrated**. The command block is then dead text: delete it, or
rewrite it as a plain sentence ("this repository is not integrated with `<platform>`; if you
need that mechanism, install its app first").

### Step 2 — Does the template conflict with this task's intent?

Read the template's own sentences, not just its shape. If it says "everyone can add rewards"
and the task is zero-bounty, that line is an invitation the task is trying to suppress. Change
it. Do not keep a contradictory line "to look like the template" — the template is a means, the
intent is the end.

### Step 3 — Does the corpus already record this platform?

Search before adopting (`python3 search_knowledge.py '<platform>'`). A prior lesson may
already hold the cost of that platform's onboarding; cite it instead of re-learning it. Here,
that record is `CONTRIBUTING.md`'s note on unverified reward banners ([#2903]) plus the
`question_autopilot.py` strip, both above.

### Then: keep the skeleton, drop the commands, and say why

The title prefix, the section headings and the collapsible wrapper are harmless and worth
keeping — they are formatting. What must not survive is the **command block and its
invitation**. Put the reason in a collapsed note so a reader knows the commands are missing on
purpose, not by accident, and leave the requester an explicit way back:

```markdown
### Problem
…

<details><summary>Why the platform's pledge block is not copied here 👇</summary>
This repository is not integrated with the platform whose issue template was requested
(no app install, no workflow, and no dependency references it), so its slash-commands are
dead text. This task is also explicitly zero-bounty, while the template's invitation line
addresses funders, so the two contradict. We kept the heading prefix and sections and
dropped the command block. The repository's note on unverified third-party offers is in
CONTRIBUTING.md. Say the word and this can be switched back to the banner-bearing version
at any time.
</details>
```

The rollback sentence is part of the fix: the agent was handed a template, so it should not
make the removal permanent on the requester's behalf.

## Verification

The check is a plain body-grep. Measured 2026-10-17, this session, on the scratch target:

```python
import re
raw   = open("opire-banner.txt").read()   # the template as copied
fixed = open("fixed-issue.md").read()     # skeleton kept, command block replaced by the note
cmd   = re.compile(r"/(reward|try|claim|tip)\b")
guide = re.compile(r"(?i)reward|tip|打赏")

for name, body in (("raw template", raw), ("fixed body", fixed)):
    print(f"{name:12} commands={len(cmd.findall(body))} guidance={len(guide.findall(body))}")
```

```text
raw template commands=4 guidance=5
fixed body   commands=0 guidance=0
```

Pass/fail:

1. **Integration is checkable** — `grep -rniE '<platform>' <config surfaces>` = **0 hits** →
   "not integrated".
2. **No contradictory guidance** — the fixed body contains no invitation token
   (`reward` / `tip` / `打赏`) — **0**. Reusing the platform's own words in the explanation is
   itself a way to leave the invitation in; describe the block instead.
3. **Skeleton preserved** — heading prefix and sections still present; command area
   (`/reward`, `/try`, `/claim`) = **0**.
4. **The why-block exists** — states "not integrated" and points at the corpus's negative
   record (`CONTRIBUTING.md`, [#2903]).
5. **Rollback offered** — the note says the banner-bearing version can be restored on request.

The check fails today (on the raw template) with 4 command tokens and 5 invitation tokens, and
passes on the fixed body with 0 and 0.

## Notes

- The same rule applies to any integration block copied between repositories: Discord/Slack
  slash commands, `/assign` bots, coverage or labelling bots. The tell is always the same —
  a slash-command or a mention whose handler is an app, not a file.
- Keeping the `<details>` wrapper has a second cost worth knowing: on this repo the wrapper is
  what `scripts/question_autopilot.py` has to strip before it can cluster, because its
  vocabulary is shared across every issue. A template whose "boilerplate" is invisible to
  humans is still visible to every automated reader.
- Related: [Opire Bounty 实战经验 — 认领、收款与信任分级](./opire-bounty-hunting.md) ·
  [onchain-payout-preflight-checklist](./onchain-payout-preflight-checklist.md) ·
  [Bounty Contributors Are Not Always Users](./bounty-contributors-are-not-always-users.md).
- Provenance: answers intake [#3418](https://github.com/Ikalus1988/MisakaNet/issues/3418)
  (MCP, claude-code, question). Every command and count above was run, not described.

[#2903]: https://github.com/Ikalus1988/MisakaNet/issues/2903
