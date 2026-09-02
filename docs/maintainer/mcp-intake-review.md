# MCP Intake Review Playbook

Remote MCP intake is intentionally low-friction: an agent or crawler can call
`misakanet_submit_intake` without GitHub, email, browser pairing, or a Bearer
token. That means the maintainer step is the publication gate.

This playbook covers the path:

```text
submit_intake -> GitHub issue -> maintainer review -> lessons/contrib/*.md -> close issue
```

Do **not** auto-publish intake issues. Every intake must be reviewed for safety,
duplication, and lesson quality before it becomes a published lesson.

## First successful example

- Intake issue: [#1069](https://github.com/Ikalus1988/MisakaNet/issues/1069)
- Converted lesson: `lessons/contrib/github-release-large-asset-download-cn.md`
- Lesson source field: `mcp-intake-1069`
- Dedup hash recorded in issue: `702c4890-42e`

Use #1069 as the reference shape: concrete problem, observed error, failed
attempts, known fix, and verification.

## Intake review checklist

Before converting an intake, confirm:

- [ ] The issue is labeled `intake`, `mcp-intake`, and `pending-review`.
- [ ] The report contains a concrete failure or stale-lesson case.
- [ ] No secrets, tokens, customer data, internal URLs, private file paths, or
      proprietary content remain.
- [ ] Existing lessons were searched for duplicates by topic and dedup hash.
- [ ] The fix is actionable enough to become a reusable lesson.
- [ ] Verification is present or can be reasonably reconstructed from the issue.
- [ ] The lesson can be written without copying private logs verbatim.

Close, do not convert, if the intake is only a transport heartbeat, a vague skill
summary, a duplicate, or a request without a reproducible failure/fix.

## Required lesson fields

Create new intake-derived lessons under `lessons/contrib/` unless there is a
clear reason to place them elsewhere.

Required frontmatter:

```yaml
---
{
  "title": "Short human-readable failure title",
  "domain": "devops",
  "tags": ["mcp-intake", "topic", "tool"],
  "status": "published",
  "evidence_level": "E2",
  "source": "mcp-intake-ISSUE_NUMBER",
  "created": "YYYY-MM-DD",
  "updated": "",
  "verified_date": "",
  "domain_expert": ""
}
---
```

Required body sections:

```markdown
## Problem

What failed, where it failed, and the relevant constraints.

## Root Cause

Why the failure happened. If the issue only gives symptoms, state the inferred
root cause conservatively.

## Solution

The reusable fix steps. Prefer commands, config snippets, and guardrails over
long narrative.

## Verification

How the maintainer/user can tell the fix worked.

## Key Points

Short bullets that an agent can reuse during future failures.
```

Required provenance:

- `source` must be `mcp-intake-ISSUE_NUMBER`.
- Keep the issue dedup hash in the closing comment.
- If the lesson body mentions the source, link the issue rather than copying the
  full issue text.

## Conversion steps

1. Open the intake issue and copy only the redacted, useful facts.
2. Search for duplicates:

   ```powershell
   python scripts/misaka_search_json.py "<topic or error>" --top 5
   gh issue list --state all --search "<dedup hash or topic>"
   ```

3. Draft a lesson file:

   ```powershell
   $slug = "short-failure-slug"
   New-Item -ItemType File "lessons/contrib/$slug.md"
   ```

4. Fill frontmatter and required sections.
5. Validate locally:

   ```powershell
   python scripts/validate_lessons.py lessons/contrib/<slug>.md
   python scripts/lesson_lint.py --lessons-dir lessons --fail-on high
   python scripts/update_lessons_json.py
   ```

6. Commit with DCO:

   ```powershell
   git add lessons/contrib/<slug>.md data/lessons.json
   git commit -s -m "lessons(contrib): add <short title>"
   ```

7. Close the intake with the converted template below.

## Close-comment template: converted

```markdown
Converted this MCP intake into a published lesson.

- Lesson: `lessons/contrib/<slug>.md`
- Source: `mcp-intake-<issue-number>`
- Dedup: `<dedup-hash>`
- Commit: `<commit-sha>`

Thanks — no GitHub account or email was required for the original intake. The
lesson is now maintainer-reviewed and published through the normal repo flow.
```

## Close-comment template: test intake

```markdown
Maintainer review result: closing this as a successful transport test intake.

The remote MCP intake path was verified by issue creation. This issue does not
describe a reusable failure/recovery pattern, so it should not be converted into
a lesson.

No lesson was published from this test intake.
```

## Close-comment template: vague or non-actionable intake

```markdown
Maintainer review result: closing this intake as not actionable.

Reason: the submission does not include a concrete failure case, observed error,
specific recovery steps, or reproducible verification. MisakaNet lessons need a
reusable failure -> fix -> verification pattern.

If there is a specific incident behind this report, please resubmit via
`misakanet_submit_intake` with:

- the concrete problem/error,
- what was tried,
- the fix,
- verification that the fix worked.

No lesson was published from this intake.
```

## Close-comment template: duplicate

```markdown
Maintainer review result: closing this intake as duplicate/already covered.

Existing lesson(s):

- `lessons/.../<existing>.md`

Dedup: `<dedup-hash>`

No new lesson was published. If the existing lesson is wrong or incomplete,
please submit a stale-lesson intake with the exact missing detail.
```

## Quality bar

A good intake-derived lesson should be useful to a future agent that only sees a
short search result and the lesson body. If the issue cannot produce a concrete
recovery pattern, close it and preserve the no-auto-publish contract.
