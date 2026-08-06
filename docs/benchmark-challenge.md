# Benchmark Challenge: Can Your Agent Learn from Failures?

We're inviting agent developers and AI engineers to run LessonReuseBench and share results.

## What we're measuring

Traditional benchmarks: *Can the agent fix this bug?*

LessonReuseBench: *Can the agent fix this bug faster because it's solved a similar one before?*

If your agent can't reuse prior debugging experience, it's stuck in an infinite loop of re-discovery.

## How to participate

### 1. Run the benchmark

```bash
git clone https://github.com/Ikalus1988/MisakaNet.git
cd MisakaNet
python3 scripts/lesson_reuse_bench.py --dry-run  # validate structure
python3 scripts/lesson_reuse_bench.py --agent your-agent --compare
```

### 2. Share your results

Open an issue with your results:

```
Title: [Benchmark] <agent-name> LessonReuseBench results

Agent: <name and version>
With lessons: <score>
Without lessons: <score>
Delta: <difference>
Notes: <observations>
```

### 3. Submit new task pairs

If you have real-world A/B debugging scenarios, submit them as PRs:

- `tasks/reuse/<name>-a.json` — Task A (first encounter)
- `tasks/reuse/<name>-b.json` — Task B (similar but different)

See [existing task pairs](https://github.com/Ikalus1988/MisakaNet/tree/main/tasks/reuse) for format.

## What we've learned so far

From our initial validation:
- All 3 task pairs are structurally valid
- Task B always has a relevant lesson available
- The biggest differentiator: does the agent **search** before **debugging**?
- Agents that retrieve lessons solve variants 3-5x faster

## Why this matters

Organizations accumulate debugging knowledge in wikis, Slack threads, and senior engineers' heads. When that knowledge isn't accessible to agents, every new debugging session starts from zero.

LessonReuseBench gives you a concrete number: *how much value does experience reuse add?*

## Links

- [Benchmark Design Doc](lesson-reuse-benchmark.md)
- [Task Files](https://github.com/Ikalus1988/MisakaNet/tree/main/tasks/reuse)
- [Technical Article](articles/can-agents-learn-from-failures.md)
- [MCP Quickstart](mcp-quickstart.md)
