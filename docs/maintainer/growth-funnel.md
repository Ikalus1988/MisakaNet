# Growth Funnel Dashboard

This document tracks weekly growth metrics for the project across discovery (Glama), GitHub, and distribution channels (PyPI, GHCR). It gives maintainers a lightweight, at-a-glance view of where users are dropping off in the funnel — from seeing the profile, to clicking through, to actually using the tool.

## How to update this weekly

1. Copy the **Weekly Template** section below.
2. Paste it at the top of the **Update Log**, filling in this week's date and numbers.
3. Pull numbers from:
   - **Glama**: project dashboard → Analytics tab (views, impressions, clicks, CTR, tool calls)
   - **GitHub**: repo → Insights → Traffic (unique visitors)
   - **PyPI**: [pypistats.org](https://pypistats.org) or `pip download` stats for the package name
   - **GHCR**: package page → Insights (pulls), if published
4. Commit the update — no code changes or release needed, this is doc-only.

---

## Baseline (established this week)

| Metric                 | Current |
| ---------------------- | ------- |
| Glama profile views    | 1,433   |
| Glama impressions      | 80      |
| Glama clicks           | 8       |
| Glama CTR              | 10%     |
| Glama tool calls       | 0       |
| GitHub unique visitors | ~176    |
| PyPI downloads         | TBD     |
| GHCR pulls             | TBD     |

**Notes on baseline:**

- Glama CTR (10%) is healthy relative to impressions, but _tool calls = 0_ is the key funnel gap right now — people are viewing and clicking but not invoking the tool. Worth flagging as the metric to watch closest.
- PyPI downloads and GHCR pulls are not yet instrumented/tracked — first priority for next update is filling these in so the full funnel (view → click → install → use) is visible.

---

## Weekly Template

Copy this block for each new entry in the Update Log below.

```markdown
### Week of YYYY-MM-DD

| Metric                 | This Week | Last Week | Δ   |
| ---------------------- | --------- | --------- | --- |
| Glama profile views    |           |           |     |
| Glama impressions      |           |           |     |
| Glama clicks           |           |           |     |
| Glama CTR              |           |           |     |
| Glama tool calls       |           |           |     |
| GitHub unique visitors |           |           |     |
| PyPI downloads         |           |           |     |
| GHCR pulls             |           |           |     |

## **Observations:**

## **Actions for next week:**
```

---

## Update Log

_(Add new weekly entries above this line, most recent first.)_
