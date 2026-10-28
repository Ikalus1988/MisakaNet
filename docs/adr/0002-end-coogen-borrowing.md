# ADR: End the Coogen borrowing programme, keep two mechanisms

**Status**: Accepted (2026-10-27) · **Issue**: [#3935](https://github.com/Ikalus1988/MisakaNet/issues/3935) ·
**Supersedes**: the 2026-08-29 Coogen borrowing evaluation (10 recommendations, never tracked)

## Context

On 2026-08-29 a review proposed ten mechanisms to borrow from Coogen, a comparable
agent-capability platform. On 2026-10-27 the review was re-run against both systems, with
reproduction commands for every claim. Three findings decided this ADR:

1. **Five of the ten landed, and nobody can prove it from the repository.** The work shipped in two
   direct pushes to `main` (`dda8fce`, `c6a419f`) with no issue and no PR. "The repository never
   followed up" is false; "the repository has no auditable trail for it" is true. That is a process
   defect, and it is the reason this ADR exists rather than another comment thread.
2. **Coogen itself has not moved where it mattered.** It does have real supply (488 public
   solutions, 251 agents), but after six months of operation its verification layer is still zero
   (`capabilities/directory.total = 0`, agents with `karma > 0`: 0), and its protocol `skill.md` has
   not changed in 70 days (byte-identical to the old snapshot). Borrowing further from a frozen
   protocol with no verification layer buys design, not evidence.
3. **The two products hit the same wall, which is the useful part.** Coogen proves that shipping the
   supply side before the verification side strands a platform at `E0`. MisakaNet's version of the
   same symptom is `E4 = 0` (of 650 lessons: E0 321 / E1 208 / E2 94 / E3 27 / **E4 0**). Both need
   *observed reuse*; neither has any.

Coogen's supply-side mechanisms (capability directory, solve consumption surface, cost-per-success,
claim binding) belong to `ROADMAP.md` item **B** — a public network of other agents — which is
explicitly **not on the roadmap** and is evidence-gated by the owner's decision. Adopting them here
would be planning B by accident.

## Decision

**End the borrowing programme.** No further mechanisms are imported from Coogen as a batch.

Two mechanisms are kept, because each serves a roadmap item that is already committed:

| Kept | Why | Cost |
|---|---|---|
| **L3 collection-boundary page + a copy-pasteable self-check** (#9 never landed) → [#3964](https://github.com/Ikalus1988/MisakaNet/issues/3964) | Turns a promise into a command a reader can run. The repository already leads Coogen on half of it (a real `robots.txt`, a pointer-based `llms.txt` with a CI gate) — the missing half is the self-check | low |
| **Hard constraint: exclude, don't downweight** (#7 never landed) → [#3963](https://github.com/Ikalus1988/MisakaNet/issues/3963) | Serves milestone 2. A constraint that degrades into a ranking weight is not a constraint | low |

**Not kept: GitHub-side reuse notification (#8).** It depends on #2939: the only producer of `E4`
reads an unauthenticated counter, so a notification built on it would announce reuse that was never
observed — the exact failure this project keeps writing lessons about. It returns only after #2939 is
fixed, and then as its own decision, not as part of this programme.

**Not kept, and not rejected either:** *Promote scope selection* and *visitor perspective* (new
candidates from the 2026-10-27 review). Neither serves milestone 1; they are evaluated on their own
merits if they ever do.

## Consequences

- The two kept items become **tracked issues**, not paragraphs in a review. An untracked
  recommendation is how five of the previous ten disappeared into direct pushes.
- The `product-design` / `decision` queue stops being a reading list for one person: this ADR is the
  template for closing one, and its first section is "what evidence decided it".
- **The E4 problem is now named as the shared wall** and is not solved by this ADR. It is the thing
  to measure next.

## Related

- #3935 — the review that produced this decision, with `file:line` for every claim
- #3963 / #3964 — the two kept items, now tracked
- #2939 — the unauthenticated counter behind `E4`, which blocks #8
- `ROADMAP.md` — item B (evidence-gated, not committed)
- `docs/trust-semantics.md` — the evidence ladder and the current distribution
