# From Manual Curation to Agent-Driven Knowledge: Building MisakaNet's Lesson Pipeline

**Author:** [zsxh1990](https://github.com/zsxh1990)
**Date:** 2026-07-29
**Repo:** [Ikalus1988/MisakaNet](https://github.com/Ikalus1988/MisakaNet)
**Related issues:** [#270](https://github.com/Ikalus1988/MisakaNet/issues/270)

I have been contributing to MisakaNet for about two months now — over 35 merged PRs across 10+ repositories. This post is about the hardest part: building a pipeline that finds, validates, and delivers high-quality lessons automatically, without fabricating content.

## The problem: manual curation does not scale

When I started, the workflow was simple: read a blog post, extract the lesson, write a markdown file, submit a PR. One lesson per hour if you are fast. The quality was high, but the throughput was low.

MisakaNet's knowledge base grows when agents and humans contribute failure lessons — not tutorials, not documentation, but "I hit this error, here is why, here is the fix, here is how to verify." Finding these in the wild requires scanning dozens of sources: Hacker News, Dev.to, GitHub issues, community forums. Manual scanning catches maybe 3-5 lessons per session.

The question became: can we automate this without sacrificing quality?

## The three-layer filter

The pipeline I built runs through three layers, each harder to pass than the last.

**Layer 1: Keyword sweep.** Search Hacker News (Algolia API), Dev.to (REST API), and community forums for posts matching lesson-relevant keywords: `postmortem`, `debug`, `pitfall`, `lesson`, `fix`, `troubleshoot`. This returns 50-100 candidates per run. Most are noise — product announcements, opinion pieces, tutorials without failure context.

**Layer 2: LLM gate.** Feed each candidate's title and first 500 words to a language model with one question: "Does this article contain a reusable technical lesson with a concrete problem, root cause, and fix?" This filters down to 5-10 candidates. The key insight: the LLM must read the body, not just the title. A title like "Supabase MCP leak" is a lesson; "Claude Opus 5" is news.

**Layer 3: Fact-check.** This is where most automation fails. After extracting the lesson content, compare it against the original article line by line. If the lesson contains code examples not in the source, reject it. If it has verification steps not in the source, reject it. The anti-fabrication rule is absolute: if the original does not provide it, the lesson cannot claim it.

```bash
# Run the pipeline
cd ~/repos/MisakaNet
python3 scripts/quality_scorer.py lessons/contrib/your-lesson.md --json
# Output: {"score": 91, "grade": "A", "pass": true}
```

## The quality gate

Every lesson must pass `quality_scorer.py` with a score of 75 or higher. The scorer evaluates five dimensions:

| Dimension | Max Points | What It Checks |
|-----------|-----------|----------------|
| Metadata | 20 | Title, domain, tags, created date, confidence |
| Structure | 25 | Problem, Root Cause, Solution, Verification, Notes sections |
| Content | 35 | Code examples, structured lists, concrete steps |
| Dedup | 10 | Not a duplicate of existing lessons |
| Source Trust | 10 | Known domain, resolution signal |

The hardest part is content quality. A lesson that says "use try-except to handle errors" scores low. A lesson that says "your CI will fail with `ModuleNotFoundError: No module named 'X'` because `pyproject.toml` does not list the dependency — add it to `[project.dependencies]` and re-run `pip install -e .`" scores high.

## Real numbers from the pipeline

Over the past two weeks of running the pipeline:

- **Candidates scanned:** ~200 articles across HN and Dev.to
- **Passed LLM gate:** ~15 (7.5% pass rate)
- **Passed fact-check:** ~8 (53% of LLM-approved)
- **Passed quality gate (≥75):** 6 (75% of fact-checked)
- **Submitted as PRs:** 6 lessons across 3 batches

The bottleneck is not finding content — it is verifying that the extracted lesson is faithful to the source. The fact-check layer rejects plausible-sounding but fabricated content. This is the correct behavior.

## What I learned

**1. Search by topic, not by popularity.** Sorting by points or reactions returns product launches and opinion pieces. Searching for `postmortem`, `debug`, `pitfall`, `lesson`, `fix` returns the technical content that actually contains reusable knowledge.

**2. The LLM must read the body.** Title-only filtering produces false positives. "Claude Code is steganographically marking requests" sounds like a lesson but is actually a news story. "Supabase MCP leak" sounds like news but contains a detailed postmortem.

**3. Fabrication is the failure mode.** The most dangerous output of an automated lesson pipeline is not missing a good lesson — it is generating a plausible-sounding lesson that the source never provided. The fact-check layer exists because we caught the pipeline inventing code examples, verification steps, and solutions that were not in the original articles.

**4. Quality scoring is a forcing function.** When you know a human (or maintainer) will read your lesson and compare it to the source, you write differently. The 75-point threshold forces completeness: every lesson must have Problem, Root Cause, Solution, and Verification. Skipping any section means a guaranteed failure.

## Try it yourself

If you want to contribute to MisakaNet, here is the fastest path:

```bash
# Fork and clone
gh repo fork Ikalus1988/MisakaNet --clone
cd MisakaNet

# Write a lesson
cat > lessons/contrib/my-lesson.md << 'EOF'
---
title: "Short, specific title"
domain: your-domain
tags: [tag1, tag2]
source: https://original-article-url
source_type: blog
created: YYYY-MM-DD
confidence: 85
---

## Problem
What went wrong, concretely.

## Root Cause
Why it went wrong.

## Solution
The fix, with actual commands or code.

## Verification
How to confirm the fix works.

## Notes
Additional context or caveats.

## Source
Link to original article.
EOF

# Check quality
python3 scripts/quality_scorer.py lessons/contrib/my-lesson.md

# Submit
git add lessons/contrib/my-lesson.md
git commit -s -m "docs(lessons): short title"
git push origin HEAD
gh pr create --repo Ikalus1988/MisakaNet \
  --head YOUR_USERNAME:lesson/my-topic \
  --title "docs(lessons): short title"
```

## What is next

The pipeline currently runs manually during heartbeat sessions (twice daily). The next step is to make it run on a schedule — a cron job that scans, filters, and queues lessons for review. The goal is 8 lessons per session, up from the current 2-3.

MisakaNet is not a knowledge base. It is a failure-memory network. Every lesson is a scar from production. The pipeline just makes sure those scars are not forgotten.
