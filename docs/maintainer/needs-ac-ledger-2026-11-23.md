# `needs-ac`: what "done" looks like, population by population (2026-11-23)

The label was carried by **46** open issues on the day this was written, and the question it was
supposed to answer — *"what does done look like?"* — cannot have one answer for all 46, because the
46 are not one population. Measured, by title shape, on 2026-11-23:

| Population | Count | What closes it |
|---|---|---|
| `[Intake]` / `[Lesson` | 12 | the intake pipeline's own gate: a lesson exists, or the submitter supplies the missing section. `needs-ac` adds nothing here — see below |
| owner questions (`question:` / `decision:`) | 4 | **a ruling, and only a ruling.** #4640 is the shape: D1–D4, D2 landed (#4697), three still open |
| bounties (`[Bounty]`) | 4 | the claim's deliverable exists. Same criterion the bounty machinery already applies |
| reviews / audits / heartbeat | 6 | the report exists **and** its findings are either fixed or filed as their own issue. A periodic report that repeats is not done, it is running |
| bugs and tasks (`bug(`, `[hook]`, `[Flake]`, CI, deps) | 20 | a merged commit that cites the issue **and** the observable it names changed |

Two consequences worth stating out loud:

1. **A merged commit citing the issue is evidence, not proof.** Two of the 46 are cited by one
   (#5245 by `#5421`, #4640 by `#4684`), and #4640's own thread says D2 of four landed — i.e. the
   signal is right about *work happening* and wrong about *done*. Read before closing; the mechanical
   pass is a shortlist, not a sweep.
2. **`needs-ac` on an `[Intake]` is a label about the wrong pipeline.** Twelve of the 46 are intake
   submissions; their acceptance criterion already exists in code (`scripts/lesson_gate.py` plus
   `scripts/convert_intake_batch.py` decide, mechanically, whether a submission is a lesson). Marking
   one `needs-ac` records "a maintainer wanted a human criterion here", which is a real statement —
   but it is not the same object as the 20 tasks, and reading the two as one queue is why the number
   never moved.

## The three that need one click today

- **#5245** — cited by `#5421` (`feat(ci): witness the body that arrives, not just when it starts`).
  The commit is about *witnessing* truncation in CI; the issue is about truncation in production.
  Decide whether the witness is the answer or only the next measurement.
- **#4640** — four decisions, one landed. Not done; the remaining three are the owner's.
- **#5117** — an audit of intakes-as-of-2026-11-16. Reports age: either its findings are filed
  separately (then this one closes) or they live here (then it does not).

## What this file is not

It is not a plan to close 46 issues. Closing an owner question without the ruling is how a queue
looks cleaner while getting less true, and #4640 shows exactly why: the label was right, the shape was
"partially landed", and a sweep would have called it finished.
