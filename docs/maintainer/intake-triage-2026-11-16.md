# Intake triage — 2026-11-16

The `needs-human-review` queue is **198 open issues**, and the rule that keeps it honest is the one in
`docs/maintainer/handoff-2026-11-14.md`: "promote/retire is a judgement, not a mechanical pass". This
file is what a judgement needs to start — the measured shape of the queue, the batches worth taking
together, and the part of the queue that is not lessons at all.

Written after closing 22 issues (`pending-review` 19 → 3, `needs-salvage` 32 → 26). Reproduce the
counts with:

```console
$ for l in needs-human-review needs-answer needs-info pending-review needs-salvage decision; do
    echo -n "$l "; gh issue list --state open --label "$l" --limit 1000 --json number -q length
  done
```

## 1. What the queue is made of

| shape | count | how it was decided |
|---|---|---|
| lesson-shaped | **80** | has both a `Root Cause` and a `Fix` heading |
| observation-shaped | **110** | prose that reports something without a fix section (many are lesson-shaped in other words — this is a reading order, not a verdict) |
| question-shaped | **8** | ends in a question, or asks several |

Two facts about the shape that matter more than the split:

- **196 of 198 carry no `domain` field.** The intake does not require one, so nothing can group this
  queue mechanically. Everything below that is grouped was grouped by reading titles.
- **Only one intake refers to an existing lesson by path, and seven name a known lesson id.** The
  queue is overwhelmingly *new* failures rather than corrections — except for the four that say so in
  their own title (e.g. `#5072` corrects `#5069`). Corrections must be converted **together with** what
  they correct, or the corpus ends up with two contradictory root causes.

## 2. The batches worth taking together

| batch | n | why together | first thing to read |
|---|---|---|---|
| ROBOGUIDE / FANUC | **20** | one contributor's run through V9.40; the failures chain (boot wedge → KAREL inject → FTP 550 → alarm pair). `#5011` already duplicates an existing lesson — patch it rather than adding a fourth | `roboguide-cold-start-wedge-two-layer-discriminate-robotinit-vs-fanuc-services` |
| Windows 脚本 / 控制台 | **32** | terminal windows, `python -c` quoting, spawn 9009, schtasks — all one root cause family (a shell boundary losing its quoting) | `problem-on-windows-inline-python-c-python-eof-scripts` |
| Feishu doc MCP | **9** | `doc_update` select/replace/insert semantics: heading match, table containers, nested lists | `feishu-doc-update-…` (search the corpus first) |
| 轻舟 / Qingzhou 部署 | ~6 | deployment reports SUCCESS while ingress serves the previous version; five of them are the same observation seen from different angles | — (no lesson yet, and it is not public tooling: `#4904`–`#4908` say the answers must come from someone who lived it) |

The rest is long tail: one or two intakes per subject.

## 3. What was closed today, and the defect behind it

`pending-review` held **16 scanner payloads** dressed as lesson submissions: `[Lesson] ' OR 1=1--`,
`../../../../etc/passwd`, `Scanner Payload`, `security_test_123`, `scan_request`, and prose variants
("Able to traverse directories using payloads like …"). They came through the public intake
(`Source: generated-payload`, `Contributor: security-tester`) and none of them broke anything — the
payload was stored as text and never interpolated, which is the correct behaviour and the reason the
report was a queue item rather than an incident.

The defect is that **nothing at intake asks whether the submission is a lesson**. A lesson needs an
observed symptom, a root cause and a verification step; a payload has the *shape* of one and none of
the evidence. One scanner run pushed the review queue from 3 real items to 19, and the next one will
do it again. Six more were closed from `needs-salvage` for the same reason (`[Intake] test`,
`audit-fixture`, `<short description of the failure>`, `$(echo vulnerable > …)`).

Candidate fix, not implemented here: `scripts/intake_kind_audit.py` already walks kinds weekly —
a payload with no `verify` step and a title that is a SQL/path fragment is a shape it could name, and
closing those on arrival keeps `pending-review` pointing at lessons.

## 4. How to convert one

```console
# WSL, not Windows: the generators write LF and find non-ASCII filenames (see handoff vol 39 §1.2)
$ wsl -e bash -lc "cd '/mnt/c/Users/<user>/MisakaNet' && python3 scripts/intake_lesson_to_file.py <issue>"
$ python3 scripts/lesson_gate.py <the new file>        # frontmatter, sections, TODO placeholders
$ wsl -e bash -lc "… && python3 scripts/build_lesson_pages.py"     # pages, sitemap, redirects
```

`scripts/quality_scorer.py` is the second opinion on whether the result is a lesson or a note: it is
what the corpus's `status` field is supposed to follow.

## 5. What this file does not do

No lesson was converted here — that is the judgement, and a batch of 20 written in one pass is how a
corpus gets its first wrong root cause. No labels were moved in bulk; the queue is ordered by what a
reader can act on, not by recursion of its own labels.
