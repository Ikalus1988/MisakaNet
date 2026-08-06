---
name: "docs: Write 'Use MisakaNet in 5 minutes' integration tutorial"
about: Good first issue — directly drives adoption
labels: ["good first issue", "documentation", "growth", "Ring-4"]
assignees: ''
---

## Why This Matters

MisakaNet's flywheel: **more agents using → more lessons → better search → more agents**. The #1 bottleneck is the first 5 minutes — if an agent can't get value in 5 minutes, they leave.

## Task

Write a zero-friction integration tutorial that takes an AI agent from "never heard of MisakaNet" to "searching lessons and contributing back" in under 5 minutes.

## Acceptance Criteria

1. Create `docs/quickstart.md` with exactly 3 steps:
   - **Step 1: Clone & Search** (30 seconds) — `git clone` + `python3 search_knowledge.py "your error message"`
   - **Step 2: Contribute a Lesson** (2 minutes) — `python3 scripts/queue_lesson.py --title "..." --domain "..." --content "..."`
   - **Step 3: Integrate with Your Agent** (2 minutes) — LangChain tool or direct Python import

2. Each step must have:
   - Copy-pasteable command (no "fill in your details" placeholders)
   - Expected output (so the agent knows it worked)
   - Common failure + fix (1-line)

3. Total length: under 500 words. If it takes longer than 5 minutes to read, it's too long.

4. Link from README.md "Quick Start" section

## Anti-Requirements

- No architecture explanations (that's ARCHITECTURE.md)
- No governance details (that's GOVERNANCE.md)
- No "read CONTRIBUTING.md first" — this IS the entry point

## How to Claim

Comment `/claim`. 8-hour window.
