# Can Coding Agents Learn from Previous Failures?

*A practical approach to evaluating whether AI agents accumulate debugging knowledge.*

## The Problem

AI coding agents are getting better at fixing bugs. But there's a question nobody's measuring:

**When an agent encounters a failure it's seen before, does it remember the fix? Or does it re-debug from scratch?**

Most benchmarks test: *Can the agent solve this problem?*

We need to also test: *Can the agent solve this problem faster because it's solved a similar one before?*

## The "Forgetful Agent" Problem

Consider this scenario:

1. Agent encounters a DCO sign-off failure in Repo A
2. Agent spends 5 minutes debugging, eventually learns `git commit --amend --signoff`
3. Agent documents the fix as a lesson
4. Next week, agent encounters a DCO sign-off failure in Repo B (different email)

A forgetful agent will:
- Re-discover the same fix from scratch
- Waste tokens on known dead ends
- Never accumulate organizational knowledge

A learning agent will:
- Search for prior DCO lessons
- Adapt the known fix to the new context
- Solve in 30 seconds instead of 5 minutes

## Introducing LessonReuseBench

LessonReuseBench is a benchmark that measures this exact capability.

### How it works

Each benchmark **pair** consists of two tasks:

1. **Task A** — Agent encounters a failure, fixes it, and generates a lesson
2. **Task B** — Agent encounters a similar (but different) failure in a new context

The agent must retrieve and apply the lesson from Task A to solve Task B efficiently.

### The 3 Task Pairs

| Pair | Task A | Task B |
|------|--------|--------|
| **DCO** | PR fails DCO check (missing sign-off) | Different repo, wrong email in sign-off |
| **Secret Scan** | Token leaked in commit, push blocked | GitHub Actions secret exposure variant |
| **DB Lock** | SQLite locked during agent operation | Agent state DB locked with different trigger |

### Scoring

```
total = 40% × task_b_pass          # Did agent solve Task B?
      + 20% × lesson_retrieved     # Did agent find the right lesson?
      + 15% × bad_path_avoided     # Did agent skip the failed approach?
      + 15% × lesson_generated     # Did agent write a lesson after Task A?
      + 10% × ci_compliance        # DCO, format, validation
```

The key metric is the **delta**: how much better does the agent perform *with* access to prior lessons vs *without*?

## Why This Matters

### For Agent Developers

If your agent can't reuse lessons, it's stuck in an infinite loop of re-discovery. Every debugging session starts from zero.

LessonReuseBench gives you a concrete number: *how much value does experience reuse add?*

### For Engineering Teams

Organizations accumulate debugging knowledge in wikis, Slack threads, and senior engineers' heads. When that knowledge isn't captured or isn't accessible to agents, every new team member (human or AI) repeats the same mistakes.

### For the AI Ecosystem

We need benchmarks that measure *learning*, not just *solving*. A model that can fix 100 bugs but forgets the first 99 when fixing the 100th isn't as valuable as one that builds on prior experience.

## How to Try It

```bash
git clone https://github.com/Ikalus1988/MisakaNet.git
cd MisakaNet

# Validate task structure (no API keys needed)
python3 scripts/lesson_reuse_bench.py --dry-run

# Run with your agent
python3 scripts/lesson_reuse_bench.py --agent your-agent --compare
```

## What We've Learned So Far

From our initial dry-run validation:

- All 3 task pairs are structurally valid
- Task B always has a relevant lesson available in the pool
- The scoring correctly rewards agents that retrieve and adapt lessons
- The biggest differentiator is whether the agent *searches* before *debugging*

## Next Steps

1. **More task pairs**: CI failures, dependency conflicts, encoding issues
2. **Real agent runs**: OpenAI, Claude, Cursor, Continue
3. **Community contributions**: Submit your own A/B task pairs
4. **Leaderboard**: Compare agents on lesson reuse, not just task completion

## Links

- [Benchmark Design Doc](../lesson-reuse-benchmark.md)
- [Task Files](https://github.com/Ikalus1988/MisakaNet/tree/main/tasks/reuse)
- [MisakaNet](https://misakanet.org)
- [MCP Quickstart](../mcp-quickstart.md)

---

*MisakaNet is a Git-backed failure lesson network for AI agents. It stores verified debugging experiences as searchable Markdown lessons, accessible via MCP, CLI, and static HTML.*
