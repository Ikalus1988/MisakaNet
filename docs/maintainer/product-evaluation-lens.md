# Product evaluation lens: who acts, who benefits, where they are

A short standard for deciding whether a feature is worth building — and for noticing when a feature
that already exists cannot work, however well it is implemented. It exists because on 2026-10-16 three
surfaces were reviewed whose *premise* did not survive contact with who the actors actually are, while
their implementation was fine. The defects were not in the code.

This is a checklist, not an essay. Use it before scoping, and again when reviewing something that
already shipped.

## The standing decision rule (set by the owner — do not re-litigate)

**Development is the hard requirement, and reducing user friction is the second one.** They are parallel,
not ranked: an element that advances the project while adding friction to its user is not a win, and an
element that removes friction without advancing anything is decoration.

For **any** element — a badge, a document, a gate, a script, a workflow, a roadmap item, a sentence —
ask this first: **whose trust, or whose capability, does this build, and how?**

1. **It does that → keep it** (or add something of the same kind that does it better).
2. **It does not → see whether it can be changed so that it does.**
3. **It cannot → delete it.**

Two failure modes this rule exists to stop, both observed in this repository on 2026-10-16/17: keeping
something because it has always been there — a README badge rendering `failing` while the real CI passes,
another asserting a weekly benchmark that had stopped — and deleting something that still carries weight
in order to look tidy. The test is never "is it old" or "does it look professional"; it is the two
sentences above. The three questions in the next section are how you answer them for a feature.

## The three questions, in this order

**1. Who performs the action, and who receives the benefit?**
If those are different people, the feature is *a request for labour from someone who does not benefit*.
That is not automatically wrong, but it is only justified when the person asked has both a **reason**
and the **ability** to act. Write both sentences down before designing; if you cannot write them, the
feature is not ready to be scoped.

*Worked example — the human vote.* The agent retrieves a lesson; the person is shown a "did this help?"
button. The person did not ask the question and usually cannot evaluate the answer, so the ability is
present only in the minority of cases where the person is the questioner. Measured 2026-10-16: the 24
most-retrieved lessons carry **3 votes, 6 in total**, and the corpus-wide count at the top rung (`E4`) is
**0 of 483**. The design asked a bystander to be a witness.

**2. Can this signal be observed instead of asked for?**
A survey is for a fact you cannot see. If the fact is visible in the system — who fetched what, what
happened next, whether the failure recurred — then observe it. Asking for an observable fact produces an
artefact of the asking (politeness, or the Hawthorne effect, or silence), not evidence. Rule of thumb:
**if the answer is already in a log, do not put a button on it.**

*Worked example — the same vote.* "Was this lesson actually reused, and did it work?" is observable at
the transport layer: which node retrieved it, whether that path failed again, whether a benchmark cites
it. The ladder's top rung now rests on those, and the vote is a hint that never gates anything.

**3. Where is the person when the need arises?**
A feature is used *in a situation* as much as for a purpose. DSH runs on a desktop; the moment "I need
this answer now" usually happens somewhere else — which is why a human-initiated search from DSH is an
**edge case**, not the main path. Design the main path around the actor who is present at the moment of
need; here that actor is the agent, not the person.

*Worked example — the composer overlay.* `/misakanet <question>` lets a person search the corpus without
the agent. It is worth keeping for the case where a person *is* the questioner and *does* read the
answer. It is not worth treating as the way people use this system, because most of the time they are
not there.

## What follows

- **Separate capability from perception.** "Makes the agent better" and "makes the agent's work visible
  to a human" are both real product values — and different products. Perception work (observability,
  retrospective, trust) is honest when it is labelled as perception; it is over-claimed the moment it
  promises capability.
- **A dead signal is evidence about the design, not a promotion problem.** When the volume is near zero,
  the first hypothesis is the instrument. Promoting a channel that nobody uses turns a useless instrument
  into a nagging one.
- **The beneficiary's absence is an input, not an objection.** If the beneficiary never opens the surface,
  that surface's job is to be *true* when someone does open it — not to recruit.

## How to use it

Before writing code, put these three lines in the issue or PR: **actor**, **beneficiary**, **situation**.
If the actor is not the beneficiary, add the reason-and-ability sentence. If the signal is observable, say
where it is observed. When reviewing something that shipped, ask the same three and then **check the
instrument** — this is cheap, and 0 usage is a finding:

```bash
# Vote volume, the measurement behind the 2026-10-16 decision (24 most-retrieved lessons):
python3 - <<'PY'
import json, subprocess, pathlib
snap = json.loads(pathlib.Path("tests/fixtures/ranking-snapshot.json").read_text(encoding="utf-8"))
seen, paths = set(), []
for q in snap["queries"]:
    for r in q["results"]:
        if r["path"] not in seen:
            seen.add(r["path"]); paths.append(r["path"])
total, hit = 0, []
for p in paths[:24]:
    lid = p.rsplit("/", 1)[-1][:-3]
    out = subprocess.run(["curl", "-sS", "-m", "15",
                          f"https://misakanet.org/api/helpful?lesson_id={lid}"],
                         capture_output=True, text=True).stdout
    n = json.loads(out).get("count", 0)
    total += n
    if n: hit.append((lid, n))
print(f"{len(hit)} of {len(paths[:24])} lessons carry votes; {total} votes in total", hit)
PY
```

## Dated record

- **2026-10-16** — written after a review of the DSH panel's vote affordance (6 votes across 24 lessons;
  `E4` = 0/483), the `/misakanet` composer overlay (agent-side retrieval is the main path; human-side
  search is an edge case), and the panel's session-report framing (a perception surface, not a
  capability one). The parallel change is `fix/e4-is-observable-not-voted`; the panel's hottest-lessons
  read (`feat/panel-top-lessons`) is the first feature scoped through this lens.
