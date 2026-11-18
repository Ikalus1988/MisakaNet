# Intake policy: company-internal platforms are not public knowledge gaps

> Owner decision, 2026-11-18. Written because the first batch to apply it was 19 issues about one
> internal platform, and a rule that lives only in a closing comment gets re-derived every month.

## The rule

An intake about a **platform that is not publicly available** (no public docs, no public source, and
the only people who could answer are inside the company) is **not a corpus item**, whichever label it
arrived with. Its generality is close to zero: a reader outside the company cannot act on it, and a
reader *inside* it is not who this corpus serves.

Such an item is handled by one test only:

| the item … | what happens |
|---|---|
| **carries a root cause** — the body states *why* it failed, and that reason can be restated without naming the platform | convert to a lesson, written at the pattern level; the internal product appears as the instance it was observed on, never as the subject |
| **carries only an observation** — "it reported SUCCESS but the endpoint served the old version", with no cause | **close it**, with the reason recorded on the issue |

The test is one question, asked once: *can this lesson be re-told without the internal name?* If no,
it is not a lesson, and leaving it in `needs-answer` / `needs-human-review` claims that someone can
answer it. Nobody can — that is what "internal" means.

## What this is not

- **Not "ignore failures on that platform".** The failures are often the most transferable material
  we have (a success flag that only means "build handled", an ingress that binds at start, two files
  that both hold a version). Those become lessons *because* the mechanism generalises — the platform
  name is stripped, not the failure.
- **Not "close everything unusual".** A public tool nobody here has used yet is *not* covered by this
  policy: it is a normal knowledge gap, answerable by anyone who reads its docs.
- **Not retroactive by default.** Applied to the open queue; closed items stay closed.

## How to apply it to one issue

```console
# 1. does the body state a cause, or only an observation?
$ env -u GITHUB_TOKEN gh api repos/Ikalus1988/MisakaNet/issues/<n> --jq '.body' | head -60

# 2. if there is a cause: does it survive being restated without the product name?
#    -> yes: it becomes a lesson (kind=missing_lesson, pattern-level title)
#    -> no : it is a platform detail, close it

# 3. close with the reason and a pointer to whatever did become a lesson
$ env -u GITHUB_TOKEN gh issue close <n> --reason "not planned"
```

Closing comment, in one paragraph: **what the item observed**, **why it cannot become public
knowledge** (internal platform, no public docs), and — when a sibling item from the same family did
carry the cause — **where that cause was turned into a lesson**. Never "insufficient information":
the information was sufficient, it was just not general.

## Why the queue cares

`needs-answer` is a promise that answering is possible. An unanswerable item is not a backlog entry,
it is a **wrong label**, and it costs the same attention as a real one while making every count that
reads the label wrong. The queue's health is "every item has an owner", not "the number is small" —
and an owner cannot be assigned to a question only the internal team could answer.
