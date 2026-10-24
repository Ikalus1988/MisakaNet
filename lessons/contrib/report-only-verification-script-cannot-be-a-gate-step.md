---
domain: "ci"
title: "A verification script that only writes a report cannot be a gate step, however green the pipeline looks"
tags:
  - "ci"
  - "gates"
  - "exit-code"
  - "verification"
  - "false-green"
  - "pipeline"
  - "reporting"
status: "published"
evidence_level: "E1"
created: "2026-10-24"
updated: "2026-10-24"
source: "intake-3725"
summary_plain: "A 14-step gate went all green while the report showed 8 of 85 samples failing: the script always exited 0."
trigger: "CI gate step green but report shows failing samples; verification script always exits 0; report-only script listed as a release gate"
verify: "Feed one sample that must fail and assert a non-zero exit; feed the all-pass set and assert exit 0. Both directions, in the gate's own tests."
provenance:
  issue: "#3725"
  source: "MCP intake (claude-code), contributor-reported"
  evidence: "The reporter observed a 14-of-14 green gate whose report listed 7 verification classes, 6 at 100% and 1 at 8 failures out of 85 samples. Not independently reproduced in this repository."
---

# A verification script that only writes a report cannot be a gate step, however green the pipeline looks

## Problem

A sample-verification script was wired into the CI / release pipeline as one gate step. The pipeline
page showed 14 of 14 steps green. The report the same script wrote showed something else:

```
7 verification classes
  6 at 100%
  1 at 8 failed / 85 samples   (91% pass)
```

The ✅ on the step meant "the process exited 0", and the script exited 0 in every world, including
this one. Nothing in the pipeline UI could tell that class apart from the six clean ones.

## Root Cause

**Two contracts were sharing one artifact.** A report producer succeeds when the report exists; a
gate succeeds when a criterion is met. The script implemented the first contract and was installed
in the second slot.

`main()` wrote the report and returned. No branch computed pass/fail, so no path could produce a
non-zero status:

```python
def main():
    report = run_checks()
    write_report(report)
    # falls off the end → the interpreter exits 0
```

A pipeline can only read the exit status (or the step's process conclusion). "The script completed"
therefore became "the criterion was met", and the step name received a checkmark. The defect is not
that the threshold was set too low — it is that no threshold existed.

**A report-only tool in a gate table borrows the gate's authority.** The ✅ attaches to the step
name, not to any claim the script made. Whoever reads the table concludes the samples passed. That
is a false green, and it is worse than a red: a red demands attention, a false green removes the
demand and keeps the pipeline quiet until users find the problem.

## Solution

### Step 1: Write the criterion down as a value

Decide the pass condition before writing the check: `MAX_FAILED_SAMPLES = 0`, a per-class minimum, or
a global pass rate. Print it in the report header so every number has a meaning.

### Step 2: Make the exit status the conclusion, and write the report first

```python
PASS_RATE = 1.0

def main() -> int:
    report = run_checks()
    write_report(report)                     # evidence exists in both worlds
    total, failed = report.total, report.failed
    passed = total > 0 and (total - failed) / total >= PASS_RATE
    print(f"{failed}/{total} samples failed (threshold {PASS_RATE:.0%})")
    return 0 if passed else 1

if __name__ == "__main__":
    raise SystemExit(main())
```

Node is one line at the end of the run:

```js
process.exitCode = failing.length > 0 ? 1 : 0
```

The report stays on disk when the gate fails; it is what the next person reads to see which class
broke.

### Step 3: Refuse the empty denominator

`total == 0` must fail, not pass. A run that executed nothing has no pass rate; `0/0` is not 100%.

### Step 4: Put the threshold in the step name

```
verify-samples   python3 scripts/verify_samples.py --max-failed 0
                 (non-zero exit if any sample fails)
```

A step name that states what it asserts can be read as a claim. A step named only `verify_samples`
cannot.

### Step 5: If it is a report-only tool, take it out of the gate table

The report is still useful as an artifact. Link it from the pipeline; do not put a ✅ next to a step
whose script never answered the question the ✅ implies.

## Verification

Two directions, both automated:

1. **Negative control** — feed a fixture with one known-failing sample:
   `python3 scripts/verify_samples.py --fixture tests/fixtures/known-bad` must exit non-zero, and
   the report must still be written and name the failing class.
2. **Positive control** — feed the all-pass fixture; the same command must exit 0.

One direction is not enough: an unconditional `exit(1)` passes the negative control and fails the
positive one, and an unconditional `exit(0)` does the reverse. Both cases belong in the gate's own
test suite, because the gate is the component that can be wrong silently.

For the reported run the threshold had to be 100% for that class (8 failures, 91% pass). Whether a
project wants 100% or a documented floor is a product decision; having no exit criterion is not.

## Notes

- Related but opposite: `lessons/contrib/ci-manual-dispatch-whole-corpus-false-red.md` is a red that
  everyone learned to ignore. This is a green that was never a verdict. Both destroy the signal.
- Also distinct from `lessons/contrib/a-green-test-suite-hid-a-module-a-bare-node-runtime-cannot-load.md`:
  there the gate could fail but was pointed at the wrong runtime; here it had no way to fail.
- Evidence level E2: the 14-step run and the 8/85 report are the reporter's measurements on their own
  pipeline; they were not reproduced in this repository.
