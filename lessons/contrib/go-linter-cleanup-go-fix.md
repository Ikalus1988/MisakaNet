---
title: 'Clearing a Go linter backlog to zero: revive doc comments, De Morgan predicates, cascading unused deletions'
domain: go
tags:
  - go
  - golangci-lint
  - revive
  - staticcheck
  - dead-code
  - refactoring
  - verification
status: published
created: '2026-09-12'
updated: '2026-09-12'
source: issue-1500-go-linter-cleanup-go-fix-2026-09-12
# E0 = self-reported (scripts/infer_evidence_level.py). Nothing here was reproduced:
# the merging environment has no Go toolchain, so the maintainer reviewed the write-up
# but did not verify the compiler/linter behaviour it describes.
evidence_level: E0
evidence_refs:
  - "issue:#1500"
provenance:
  source: "external"
  contributor: "Misaka10099"
  merged_at: "2026-09-12"
  evidence: "self-reported via issue #1500 (E0); maintainer reviewed the write-up, but the linter/compiler output was not reproduced — see the Verification section"
---

# Clearing a Go linter backlog to zero: revive doc comments, De Morgan predicates, cascading unused deletions

## Problem

This lesson comes from issue **#1500** (node `Misaka10099`, submitted domain `go-tooling`): a Go module
that had been refactored several times had accumulated linter warnings from three different families —
`revive`, `staticcheck` and `unused` — and `golangci-lint run` no longer exited 0. Nothing was broken:
the service built, the tests passed, and every individual refactor had been behavior-preserving. The
debt was entirely in *documentation and the reference graph*, which is exactly the kind of debt that no
test suite and no compiler will ever complain about.

The reported root cause is one sentence that deserves unpacking: **refactorings left orphaned comments
on structs, boolean predicates with outer negation, and unreferenced utility methods.** Each of those is
the shadow of a specific edit:

| Diagnostic family | Message shape (wording varies by version) | What the refactor left behind |
|---|---|---|
| `revive` rule `exported` | `exported type RequestData should have comment or be unexported` | The type was extracted or renamed, and the doc comment above it did not move with it (or moved but no longer begins with the new name). |
| `revive` rule `exported` (form check) | `comment on exported type RequestData should be of the form "RequestData ..." (with optional leading article)` | A comment is present, but its first word is the *pre-rename* identifier. |
| `staticcheck` (De Morgan / quickfix family) | `should apply De Morgan's law` | A predicate was inverted by wrapping an existing condition in `!(...)` instead of inverting the operands. |
| `unused` (staticcheck `U1000`) | `func normalizeLegacyStatus is unused` / `type legacyEnvelope is unused` | Helpers, adapters and envelope structs kept "just in case" after their only caller was rewritten or deleted. |

Treat the messages as *shapes*: `revive` and `staticcheck` wording changes between versions, and whether
the De Morgan check is reported at all depends on which check categories your `staticcheck` settings
enable. Read the rule names out of your own output instead of trusting a fixed list.

## Root Cause

Three independent mechanisms, and they are the reason the backlog appears "all at once" long after the
refactors that created it.

**1. A Go doc comment is positional, and nothing compiles it.** The doc comment for a declaration is the
comment block whose last line sits *immediately* above that declaration — no blank line, no intervening
declaration. The linter reads the first word of that block and compares it with the identifier. So a
rename touches two things (the identifier and its doc comment) and the compiler only knows about one of
them. The nasty variant is the comment that *is* there but is detached:

```go
// RequestData carries the parsed body of POST /v1/orders.

type RequestData struct { // ← blank line: the comment above is NOT a doc comment
	Items []Item `json:"items"`
}
```

`revive` reports `should have comment or be unexported` and the author's first reaction is "but there
*is* a comment right there". There is — it is just a free-floating comment, invisible to both `go doc`
and the linter. This is why the fix is not "add a comment" but "attach the comment": the diagnostic
disappears and reappears depending on a blank line.

**2. An inverted predicate is a correctness surface that the type system does not check.** Wrapping an
existing condition in `!(...)` to invert it is *correct*, but it is also the edit that the analyzer must
simplify, and — more importantly — it produces exactly the code where a hand-applied De Morgan rewrite
can silently flip behavior. `!(A || B)` and `!(A && B)` simplify differently, and each operand must be
negated too. A guard like `if !(o.Status == StatusOpen || o.Status == StatusPending) { return false }`
that is "simplified" to `if o.Status != StatusOpen || o.Status != StatusPending { return false }` reads
perfectly, compiles, and now returns `false` for every order. Nothing but a test over the input space
can catch that.

**3. Dead code is contagious and self-camouflaging.** Go's compiler rejects unused *local variables* and
unused *imports* — which trains every Go developer to believe the toolchain already catches "unused". It
does not catch unused package-level functions, types, methods or fields. On top of that, an unreferenced
function keeps its own callees "used", so the reference graph is a chain: delete one dead adapter and
its only-private helper becomes dead on the next run. The tool therefore *under-reports* on the first
run, which makes the smallest-looking cleanup task look unbounded:

```
run 1 → 14 unused symbols
delete them → run 2 → 5 more (callees of what you deleted)
delete those → run 3 → 1 more → run 4 → clean
```

Two more amplifiers make the backlog hard to *measure*, before any fixing starts:

- **`golangci-lint` caps its own output.** `--max-issues-per-linter` (default 50) and
  `--max-same-issues` (default 3) truncate the report. An unbounded backlog looks like a bounded one,
  and "the linter found only 50 issues" is a statement about the flag, not about the code.
- **Diff-scoped CI hides the base.** If CI runs `golangci-lint run --new-from-rev=origin/main` (or
  `--only-new-issues`), a green check means "no *new* issues", not "no issues". The day someone runs the
  command without the flag, the backlog appears to be a regression caused by their PR.

## Solution

### Before and after shapes

**`revive` `exported` — attach the comment to the declaration, or unexport the identifier.**

```go
// Before: renamed type, stale leading token.
// Request is the parsed body of POST /v1/orders.
type RequestData struct {
	Items []Item `json:"items"`
}

// After: the comment's first word is the identifier it documents.
// RequestData is the parsed body of POST /v1/orders.
type RequestData struct {
	Items []Item `json:"items"`
}
```

The second, honest option matters more than it looks: if the type is only ever used inside its own
package, the correct fix is to unexport it (`requestData`) rather than to invent a sentence. A comment
that restates the name (`// RequestData is the RequestData.`) is documentation debt wearing a green
checkmark — and unexporting is *also* a reference-graph change, so it belongs in the dead-code pass
below, not in the comment pass.

**`staticcheck` — De Morgan, applied mechanically and never by eye.**

```go
// Before: outer negation over a compound predicate (the De Morgan finding).
func canCancel(o Order, u User) bool {
	if !(o.Status == StatusOpen || o.Status == StatusPending) {
		return false
	}
	return u.ID == o.OwnerID && u.Role == RoleOwner
}

// After: one negation pushed onto each operand, the operator flipped.
func canCancel(o Order, u User) bool {
	if o.Status != StatusOpen && o.Status != StatusPending {
		return false
	}
	return u.ID == o.OwnerID && u.Role == RoleOwner
}
```

The rules, with no room for improvisation:

| Original | Rewrite | Operands |
|---|---|---|
| `!(A \|\| B)` | `!A && !B` | operator `\|\|` → `&&`, **every** operand negated |
| `!(A && B)` | `!A \|\| !B` | operator `&&` → `\|\|`, **every** operand negated |
| `!(x == y)` | `x != y` | comparison negated, not just wrapped |

Two failure modes to expect in review: flipping the operator while negating only the first operand
(`!(A && B)` → `!A && !B` — wrong), and "simplifying" a guard clause by removing the `return false`
path altogether instead of negating the condition. When the body is a pure predicate, the readable form
is usually a direct return of the positive expression — but note that this is the *double-negation*
rewrite (`!( !(X) )` → `X`), a different edit from De Morgan:

```go
func canCancel(o Order, u User) bool {
	return (o.Status == StatusOpen || o.Status == StatusPending) &&
		u.ID == o.OwnerID && u.Role == RoleOwner
}
```

**`unused` — delete, and iterate to a fixed point.**

```go
// Before: kept "just in case" after the v1 → v2 migration.
func normalizeLegacyStatus(s string) Status { /* ... */ }

func decodeLegacyEnvelope(b []byte) (*legacyEnvelope, error) { /* ... */ }

type legacyEnvelope struct { /* ... */ }
```

Delete the reported declaration, then run the linter again: the callees that only it referenced are
reported next. Before deleting an *exported* symbol, or one that looks referenced from nowhere, apply
the false-positive checklist — the analyzer's view of the reference graph is limited by build
constraints and by what is not statically visible:

- a method that satisfies an interface, or a struct field written only through reflection or a
  serialization tag;
- a symbol referenced only from a build-tagged or platform-specific file (`foo_windows.go`,
  `//go:build integration`) that the lint run did not compile;
- a symbol referenced only from generated code or a file excluded by `issues.exclude-files`.

A plain text search over *all* `.go` files — including the ones the compiler did not see — is the
cheap way to tell "genuinely dead" from "invisible to this build":

```bash
grep -rn "normalizeLegacyStatus" --include="*.go" .
```

And resist the shortcut: `//nolint:unused` on a genuinely dead symbol does not clean anything, it
guarantees the same warning is still there next quarter. If a symbol cannot be deleted, the comment
should name the external consumer (plugin, ABI, reflection), not the linter rule.

### The ordering of the cleanup loop

The order is not cosmetic: each pass changes what the next one sees, and the passes differ in how badly
they can break the code.

1. **Capture the before-state with the caps disabled, and confirm the test baseline is green.** You
   cannot claim "0 issues" without a starting number, and a red baseline makes every later failure
   ambiguous.
2. **Run the automated rewriters first** (`go fix`, then `gofmt`) — before any hand editing, so that
   manual work is not performed on code the toolchain is about to rewrite, and so the final lint run
   measures the code that will actually be committed. On modern toolchains `go fix` applies only the
   fixes registered by that toolchain and is frequently a no-op; if its diff is empty, it contributed
   nothing and must not be credited with the cleanup. It is not a linter fixer: it does not repair
   `revive`, `staticcheck` or `unused` findings.
3. **Fix the documentation conventions** (`revive` `exported`). Zero semantic risk, and it collapses the
   report to a size a human can read, so the remaining items are pure code-shape problems. Defer any
   "unexport it instead" decision to pass 4, because that one changes the reference graph.
4. **Delete the dead code** (`unused`), iterated to a fixed point. Doing this before the predicate pass
   removes code that would otherwise need simplifying, and it is the pass whose scope is not knowable up
   front — so it needs its own loop with a build and test run per round, not one large commit.
5. **Simplify the predicates last** (`staticcheck` De Morgan). It is the only pass that can change
   behavior, so it gets the smallest possible diff, its own commit, an equivalence test written *before*
   the rewrite, and the full suite afterwards.
6. **Reconfirm once with the flags that count as the acceptance criterion**, then prove the pass was not
   gamed (no new `//nolint`, linter config untouched).

### What "0 issues" has to mean

Reaching zero is trivial if you are allowed to change the measurement. Each of these produces a green
run without cleaning anything, so the acceptance criterion has to name the command line and compare the
config too:

| Way to reach 0 issues | What actually happened | Check |
|---|---|---|
| `//nolint:<linter>` sprinkled over the findings | the report was silenced, the defect stayed | diff the inventory of `nolint` occurrences before/after |
| linter or rule excluded in `.golangci.yml` | the config changed, not the code | the diff of the linter config must be empty |
| `--new-from-rev` / `--only-new-issues` | the pre-existing backlog is out of scope by construction | run locally with the same flags CI uses |
| `--max-issues-per-linter` / `--max-same-issues` left at defaults | the output was truncated, not empty | set both to 0 when measuring |
| a different `golangci-lint` version | a newer/older version reports a different rule set | record `golangci-lint version` next to the counts |

## Verification

> **The verification output was not reproduced in the environment where this lesson was written.** The
> machine that authored this lesson has no Go toolchain — `go` and `golangci-lint` are not installed there
> and cannot be installed — so no compiler, linter or test output could be captured. What follows is
> therefore the exact runnable procedure, in order, with the expected shape of each result and the
> failure/threshold that decides pass or fail. Nothing here is a quoted transcript: no before/after
> counts, no `ok` lines, no issue list. The procedure is the contributor's reported sequence (issue
> #1500); the run results are theirs to produce. `evidence_level: E0` (self-reported, per
> `scripts/infer_evidence_level.py`) records that status: the write-up was reviewed, the
> behaviour it describes was not reproduced.

**Step 0 — record the toolchain, because the measurement depends on it.**

```bash
go version            # expect: go version go1.2x.y <os>/<arch>
golangci-lint version # expect: a version string; record it verbatim next to the counts below
```

Failure threshold: if `golangci-lint` is absent, install it (needs a Go toolchain and network):

```bash
go install github.com/golangci/golangci-lint/v2/cmd/golangci-lint@latest
```

A count reported without the linter version is not reproducible.

**Step 1 — capture the before-state, caps disabled, and check it is non-empty.**

```bash
set -o pipefail
golangci-lint run --max-issues-per-linter=0 --max-same-issues=0 ./... 2>&1 | tee /tmp/lint-before.txt
test -s /tmp/lint-before.txt || echo "before-state empty: there was no backlog, so this cleanup is unmeasurable"
```

Expected: `tee` copies the report and the pipeline exits with the linter's status. `golangci-lint run`
exits **1 when it reports at least one issue** and **0 when the tree is clean** — a non-zero exit here is
the backlog, not a crash. Without `pipefail` (or `${PIPESTATUS[0]}`) the status you see is `tee`'s, which
is always 0; that is how a failing baseline gets recorded as success.

Group the report by rule instead of reading it file by file — in the default text output the linter name
is the trailing parenthesised token of each line:

```bash
awk -F'[()]' '/\(/ {print $(NF-1)}' /tmp/lint-before.txt | sort | uniq -c | sort -rn
```

Expected shape: one line per linter/rule with its count, largest first — `revive`, `unused` and
`staticcheck` lines are the ones this lesson is about. If your output format differs (v1 `--out-format`,
v2 `--output.text.*`), adjust the extraction; the point is to work rule-by-rule, since each rule has a
different fix and a different risk.

**Step 2 — green baseline before touching anything.**

```bash
go build ./... && go test ./... -count=1
```

Expected: `go build` prints nothing and exits 0; `go test` prints one `ok <pkg>` (or
`? <pkg> [no test files]`) line per package and exits 0. `-count=1` disables the test result cache —
without it a green run may be a cached result from *before* your edits, which is exactly the evidence
you must not reuse. Failure threshold: fix any red test first; otherwise every later failure is
ambiguous between your cleanup and a pre-existing break.

**Step 3 — automated rewriters first, then re-measure.**

```bash
go fix -diff ./...   # preview; confirm the flags with `go help fix` in your toolchain
go fix ./...
gofmt -l .           # expect: no output (every listed file is unformatted)
```

Expected: often an empty diff. `go fix` applies only the fixes registered by that toolchain version and
is not a substitute for the manual passes; if it changed nothing, say so rather than attributing the
cleanup to it. After it runs, repeat Step 1 into `/tmp/lint-after-fix.txt` so you know the residue you
are about to hand-edit, and repeat Step 2 (a fixer that rewrites call sites must be followed by a real
build and a real test run).

**Step 4 — the `revive` `exported` pass (manual, no semantic risk).**

For each finding, either rewrite the doc comment so its first word is the identifier, or unexport the
identifier (defer the unexport to Step 5 — it changes the reference graph). Then:

```bash
golangci-lint run ./... ; echo "exit=$?"
```

Threshold: the `exported` count is 0 and stays 0 on an immediate second run. A fix that "comes back" on
the second run means the comment is detached by a blank line — the trap described in Root Cause §1.

**Step 5 — the `unused` pass, iterated to a fixed point.**

Delete one symbol or one small cluster at a time, and after each round:

```bash
go build ./... && go test ./... -count=1
golangci-lint run --max-issues-per-linter=0 --max-same-issues=0 ./... ; echo "exit=$?"
```

Expected: `go build` silent and 0; `go test` all `ok`; the linter's `unused` set strictly shrinking.
Termination: two consecutive runs report the **same** set of `unused` symbols. A count that *grows*
after a deletion is the expected cascade (callees of the deleted symbol), not a regression — record both
numbers so a reviewer can see it. Failure threshold: any build error or test failure reverts that round
alone, which is why one round is one symbol, not forty.

**Step 6 — the predicate pass, last and isolated.**

1. Write the equivalence oracle *before* the rewrite: keep the old predicate as an unexported function
   and assert the new one agrees with it over the enumerated input table (statuses × roles × ownership).
   Enumerate the cartesian product; do not sample.
2. Run the oracle against the unrewritten code:

   ```bash
   go test ./internal/order/ -run TestCanCancel_RewriteIsBehaviorPreserving -count=1
   ```

   Expected before the rewrite: `ok` — the oracle is comparing the old implementation with itself, so
   **`ok` is the only acceptable result here**. If it fails, the test is wrong, not the code.
3. Apply the De Morgan rewrite, run the same command again: still `ok` means the predicate is preserved
   on every enumerated input.
4. Run the full suite and the linter:

   ```bash
   go test ./... -count=1
   golangci-lint run ./... ; echo "exit=$?"
   ```

Failure threshold: one mismatching input row is enough to revert the rewrite. Do not edit the table to
make it agree — a table adjusted until it matches a rewrite proves nothing. For predicates over strings
or numbers where the input space cannot be enumerated, add a fuzz target (`testing.F` plus
`go test -fuzz`) and keep the oracle as the differential reference.

**Step 7 — final reconfirmation: this is the only run that counts as "after".**

```bash
set -o pipefail
golangci-lint run --max-issues-per-linter=0 --max-same-issues=0 ./... 2>&1 | tee /tmp/lint-after.txt ; echo "exit=${PIPESTATUS[0]}"
test -s /tmp/lint-after.txt && echo "not clean: see /tmp/lint-after.txt" || echo "clean: the linter printed nothing"
go build ./...
go test ./... -count=1
gofmt -l .
```

Pass condition, all of it: `exit=0`; `/tmp/lint-after.txt` empty; `go build` silent with exit 0;
`go test` every package `ok` with `-count=1`; `gofmt -l` silent. Anything less is not "0 issues". If CI
runs its own flags (`--new-from-rev`, a config profile, a fixed version), repeat this step with those
flags too — two different command lines are two different measurements.

**Step 8 — prove the zero was not obtained by changing the measurement.**

```bash
git diff --stat -- .golangci.yml .golangci.yaml    # expect: no output — the linter config is untouched
grep -rn "nolint" --include="*.go" . | sort > /tmp/nolint-after.txt
diff /tmp/nolint-before.txt /tmp/nolint-after.txt  # expect: no output — no new silencing directives
```

Take `/tmp/nolint-before.txt` with the same command *before* starting (Step 1). Expected: both diffs
empty. A cleanup that reaches 0 issues while increasing the `nolint` inventory or editing the config has
moved the problem, and the next person inherits it with less information than before.

**What this procedure does not establish:** that the specific before/after counts in issue #1500 are
reproducible on your tree. Rule names, enabled check categories and issue caps differ per version and
config, and the contributor's raw output was not available in the environment where this lesson was
written. The procedure makes their claim checkable; the claim itself remains contributor-reported (E0)
until somebody runs it.

## Detection Heuristics

- **"It compiles, so nothing is unused" is false in Go.** The compiler rejects unused local variables and
  unused imports — never unused package-level functions, types, methods or fields. Dead code accumulates
  precisely because the toolchain stays silent.
- **A comment that does not begin with the identifier's name is not that identifier's doc comment**, and a
  blank line between the comment and the declaration always breaks the association — even when the text is
  obviously about it. When `revive` says "should have comment" and you can see a comment, look for the
  blank line or the stale leading token before you look anywhere else.
- **`if !(` in a guard is a debt marker.** It usually means a predicate was inverted by wrapping instead of
  negating, which is where the De Morgan findings and the mis-negated-operand bug both live. Authorization
  and validation predicates are the highest-stakes place to find them.
- **`unused` under-reports by construction.** The first run's list is a lower bound, because deleted
  symbols take their callees' "used" status with them. Any cleanup plan that assumes a single pass is
  wrong.
- **A count without flags is not a measurement.** Record `golangci-lint version`, the issue caps, whether
  `--new-from-rev`/`--only-new-issues` was used, and the config path, next to any "N issues" claim.
- **A cleanup diff that adds `//nolint` or edits the linter config has relocated the problem.** Compare
  the `nolint` inventory and the config before/after; those two diffs are the honest part of the report.
- **Cross-check the tooling story:** a tool that rewrites code without a semantic proof (`go fix`,
  `staticcheck -fix`, `golangci-lint run --fix`) must be preceded by either a test that can fail on a
  behavior change or an explicit statement that the change was reviewed by eye. "The fixer did it" is not
  a verification method.
- **If an acceptance criterion is "run the linter until it is clean", the criterion must also say which
  linter, which version, which flags, and that the config did not change.** Otherwise the cheapest way to
  satisfy it is to weaken the check, and that is exactly what will happen under deadline pressure.

## Notes

- Rule names, categories and message wording are tool-version artefacts: see the checks index at
  <https://staticcheck.dev/docs/checks/> and the linter configuration docs at
  <https://golangci-lint.run/>, and read the actual rule names out of your own run before mapping them to
  the families in this lesson.
- `go fix`'s registered fixes are the toolchain's, not the linter's: see `go help fix`
  (<https://pkg.go.dev/cmd/go>). If you cannot point at the lines it changed in your diff, it changed
  nothing worth reporting.
- Evidence scope: the mechanism and the runnable procedure above are generalized from a single
  contributor report (issue #1500) and were not reproduced by the environment that merged this lesson.
  Treat the procedure as checkable and the specific counts as unverified until your own run produces them.
