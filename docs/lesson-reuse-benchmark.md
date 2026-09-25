# LessonReuseBench

> **Status (measured 2026-09-25): the harness is a stub, so these are instructions for a design, not a
> runnable benchmark.** `python3 scripts/lesson_reuse_bench.py --dry-run` fails at import —
> `ModuleNotFoundError: No module named 'agents'` (`:4` imports `agents.YourAgent`, which does not exist) — its
> scoring is a placeholder (`calculate_score`: *"Placeholder for actual score calculation"*, `return 1.0 if
> result == "success" else 0.0`), and the three pairs are hardcoded in the script while the real pair files in
> [`tasks/reuse/`](../tasks/reuse) are never read (the documented `--tasks` flag does not exist). No agent has
> ever been scored by it, so any number below is an illustration. Implementing it is tracked in
> [#2221](https://github.com/Ikalus1988/MisakaNet/issues/2221); until then, treat this page as the design.

Evaluate whether AI agents can learn from past failures and reuse lessons when encountering similar problems.

## Why this benchmark exists

Traditional coding benchmarks test: *Can the agent fix this bug?*

LessonReuseBench tests something more important: **Can the agent fix this bug using prior experience, or does it re-debug from scratch?**

An agent that forgets past failures will:
- Re-discover the same fix repeatedly
- Waste tokens on known dead ends
- Never accumulate organizational knowledge

An agent that reuses lessons will:
- Retrieve the right fix faster
- Avoid known-bad approaches
- Build on prior debugging sessions

## How it works

Each benchmark **pair** consists of two tasks:

1. **Task A** — Agent encounters a failure, fixes it, and generates a lesson
2. **Task B** — Agent encounters a similar (but different) failure in a new context

The agent must retrieve and apply the lesson from Task A to solve Task B efficiently.

### With vs Without

Each pair is run twice:
- **With lesson pool**: Agent has access to MisakaNet search
- **Without lesson pool**: Agent must debug from scratch

The score delta measures the value of experience reuse.

## Task Pairs

| Pair | Task A | Task B | Domain |
|------|--------|--------|--------|
| DCO | PR fails DCO check (missing sign-off) | Different repo, wrong email in sign-off | devops |
| Secret Scan | Token leaked in commit, push blocked | GitHub Actions secret exposure variant | devops |
| DB Lock | SQLite locked during agent operation | Agent state DB locked with different trigger | development |

## Scoring

```
total = 40% × task_b_pass
      + 20% × correct_lesson_retrieved
      + 15% × avoided_known_bad_path
      + 15% × generated_reusable_lesson
      + 10% × ci/pr_compliance
```

### Score definitions

| Dimension | What it measures | How to check |
|-----------|-----------------|--------------|
| task_b_pass | Did agent solve Task B? | Exit code, test result |
| correct_lesson_retrieved | Did agent find the right lesson? | Search query logs |
| avoided_known_bad_path | Did agent skip the failed approach? | Command/trace analysis |
| generated_reusable_lesson | Did agent write a lesson after Task A? | Lesson file exists, passes schema |
| ci/pr_compliance | DCO, format, frontmatter valid | CI checks pass |

## Running

Not runnable yet — see the status note at the top. The intended commands are:

```bash
# Intended: validate the task files (no API keys needed). Today this exits on `ModuleNotFoundError: agents`.
python3 scripts/lesson_reuse_bench.py --dry-run

# Intended: run one agent over tasks/reuse/ (the flag does not exist yet; the pairs are hardcoded today)
python3 scripts/lesson_reuse_bench.py --agent <your-agent> --tasks tasks/reuse/

# Intended: compare with/without the lesson pool
python3 scripts/lesson_reuse_bench.py --agent <your-agent> --compare
```

## Output

The shape is fixed; **the example below is an illustration, not a measurement** — nothing has
produced one yet:

```json
{
  "agent": "openai",
  "timestamp": "2026-07-14T10:00:00Z",
  "pairs": [
    {
      "name": "dco",
      "task_a_pass": true,
      "task_b_pass": true,
      "lesson_retrieved": true,
      "bad_path_avoided": true,
      "lesson_generated": true,
      "ci_compliant": true,
      "score": 0.95
    }
  ],
  "total_score": 0.92,
  "delta_vs_no_lesson": 0.35
}
```

## How to participate

1. **Run the benchmark** — *blocked on [#2221](https://github.com/Ikalus1988/MisakaNet/issues/2221)*:
   the harness cannot execute yet (see the status note at the top). What is genuinely useful today is a
   [new A/B pair](https://github.com/Ikalus1988/MisakaNet/tree/main/tasks/reuse) — the design below says what
   a pair needs, and the files are read by nothing until the harness exists.

2. **Share your results:** Open an issue titled `[Benchmark] <agent-name> LessonReuseBench results` with:
   - Agent name and version
   - Score with lessons vs without lessons
   - Delta (difference)
   - Observations

3. **Submit new task pairs:** PR with `tasks/reuse/<name>-a.json` and `tasks/reuse/<name>-b.json`

## Adding new task pairs

1. Create `tasks/reuse/<name>-a.json` (Task A)
2. Create `tasks/reuse/<name>-b.json` (Task B)
3. Each task file needs: `name`, `description`, `setup`, `expected_outcome`, `validation`

## Related

- [Benchmark Challenge](benchmark-challenge.md)
- [Technical Article](articles/can-agents-learn-from-failures.md)
- [Regression queries](../data/regression_queries.json)
- [Troubleshooting](troubleshooting.md)
- [Debug Pain Index](debug-pain-index.md)
- Tracking issue: [#457](https://github.com/Ikalus1988/MisakaNet/issues/457)
