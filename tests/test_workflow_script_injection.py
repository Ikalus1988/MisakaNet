#!/usr/bin/env python3
"""No workflow may interpolate a value into a `run:` block, and a `| tee` may not decide a verdict.

Two defects in the lesson workflows, found by an external audit on 2026-10-07 and
reproduced here before being fixed. Both are silent: the workflow reports success.

## 1. Script injection through a step output

`.github/workflows/lesson-gate.yml` and `.github/workflows/provenance-gate.yml` both had:

```yaml
run: |
  FILES="${{ steps.classify.outputs.added }}"
```

GitHub substitutes `${{ }}` **textually, before bash parses the script**, and bash
performs command substitution **inside double quotes**. The value came from
`git diff --name-only`, and a git filename may contain `$`, `(` and `)` — GitHub
accepts all three. So a pull request adding a file named

    lessons/core/$(id).md

made the runner execute `id`. Measured 2026-10-07, the whole chain:

```
$ git diff --name-only --diff-filter=A BASE HEAD -- 'lessons/**/*.md'
lessons/core/$(id).md                      <- enters the variable
$ echo "added=$ADDED" >> "$GITHUB_OUTPUT"  <- carried verbatim, no sanitising
$ FILES="lessons/core/$(id).md"            <- GitHub renders this into the next step
$ bash  ->  FILES = [lessons/core/uid=1000(eric_jia) gid=1000(eric_jia) ...]
```

Both workflows trigger on `pull_request`, so a fork's pull request gets a read-only
token and no repository secrets; the escalation is for anyone who can push a branch
to the repository itself, where the same injection runs with a write-capable token.
Either way it is arbitrary command execution on a runner, on a workflow that runs on
**every** pull request because it has no `paths:` filter.

The fix is the one GitHub documents: hand the value over through `env:` so the shell
receives a value rather than script text. Both files now read
`FILES=("${ADDED[@]}" ...)` out of an environment variable.

## 2. A `| tee` pipeline that cannot fail

`provenance-gate.yml`'s tier 2 step was one line:

```yaml
run: python3 scripts/check_provenance.py --strict-new ${{ ... }} | tee -a provenance_report.txt
```

A bash pipeline without `pipefail` returns the status of its **last** command, so
`tee` decided the outcome. Measured 2026-10-07 with a new lesson citing a URL that
returns 404: the script printed `❌ source does not resolve` and exited `1`, and the
step still reported success.

Tier 1, twenty lines above in the same file, gets this right — `set +e`,
`RC=${PIPESTATUS[0]}`, `exit 1`. Two steps in one file, the same check, opposite
behaviour, and the difference is three lines of shell.

This is the repository's own recorded lesson, from
`scripts/gate_mutation_audit.py`: *a check that cannot fail is worse than no check,
because it reports success on broken input and retires the suspicion that would have
found the bug*.

## What this gate checks

Not "these two files are fixed" — that goes stale the moment a third workflow is
written. Two properties of **every** workflow in `.github/workflows/`:

1. No `${{ … }}` from a `steps.*.outputs` / `github.event.*` context appears inside a
   `run:` body. Data crosses the boundary through `env:` or an input, never as script text.
2. A step that pipes a checker into `tee` (or anything else) still fails when the
   checker fails — via `set -o pipefail` or an explicit `PIPESTATUS` check.

The exceptions list exists because a rule with no exceptions tends to get disabled
rather than satisfied. Each entry names the file and the reason.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
WORKFLOWS = REPO / ".github/workflows"

# The rule is not "any `${{ }}` in a run: body" — that fires on `base.sha`, on
# `pull_request.number`, on `head_sha` and on `changed_files`, all of which GitHub
# generates and none of which an outside party can choose. The first draft of this gate
# flagged eleven of those and buried the two real hits.
#
# What matters is **free-form text a pull-request author supplies**: the branch name, the
# title, the body, a commit message, and whatever a previous step derived from those —
# which includes a list of filenames, because git happily accepts `$`, `(` and `)` in a
# path. Numeric ids and object hashes are not a vector: there is no way to spell
# `$(…)` as a 40-character hex digest.
#
# `inputs.*` is the third source, and it was the one this file originally left out — a
# blind spot rather than a considered exclusion. A `workflow_dispatch` input is free text
# that arrives by API call, and the declared `type` does not constrain it: the dispatch
# endpoint takes `inputs` as `map[string]string` and never checks it against the schema,
# so `days: {type: number}` and `post: {type: boolean}` are documentation, not guarantees.
# Its severity is genuinely lower than the other two, because dispatching requires write
# access and someone with write access can push a workflow file instead — there is no
# privilege to escalate to. It is in the rule anyway because the fix is the same one line
# (`env:`), and a defect class is worth closing once it is found rather than keeping open
# on a severity argument that only holds until the next workflow lowers its bar.
UNTRUSTED = re.compile(
    r"\$\{\{\s*("
    # steps.<id>.outputs, and the property chain that usually follows it —
    # `outputs.added` is the normal spelling and the first version of this pattern
    # required `}}` immediately after `outputs`, so it matched nothing at all. A gate
    # that cannot fail is the thing this file exists to prevent; see the self-test
    # below, which is the only reason that was caught.
    r"steps\.[^.}\s]+\.outputs(?:\.[A-Za-z_][A-Za-z0-9_]*)*"
    r"|[^}\s]*steps\.[^}\s]*outputs(?:\.[A-Za-z_][A-Za-z0-9_]*)*"
    r"|github\.event\.(?:pull_request|issue|comment|head_commit|commits|review|discussion)"
    r"[^}\s]*\.(?:ref|label|title|body|message|login|description|name)"
    r"|inputs\.[^}\s]*"
    r")\s*(\|\|[^}]*)?\s*\}\}"
)
# The `||` fallback may itself contain spaces — `${{ github.event.pull_request.head.ref ||
# github.event.repository.default_branch }}` is the shape Actions documents — so the
# tail is `[^}]*` and not `[^}\s]*`. The self-test below is what caught that: the
# repository already uses `${{ … || '' }}` in four workflows.

# Sinks that essentially always succeed, so a checker piped into one loses its verdict.
# `| head`, `| wc -l` and friends are deliberately absent: a truncated report is a
# different bug and mixing it in here would make the rule harder to satisfy than useful.
SILENT_SINK = re.compile(r"\|\s*(?:tee|tee\s+-a|cat)\b")

# Every remaining site where a step output is interpolated into a `run:` body, and why
# the value cannot carry text an outside party chose. This is a list of *decisions*, not a
# suppression list: each entry is a claim that has to stay true, and a reviewer can check
# any of them by reading the producing step.
#
# Adding to it is easy; that is the point. The alternative — deleting the rule, or
# narrowing it until it stops firing — is what produced a gate that matched nothing at all
# (see the self-test below). An allowlist with reasons can be reviewed; a rule that has
# been talked out of existence cannot.
SAFE_OUTPUTS: dict[str, tuple[tuple[str, str], ...]] = {
    # (workflow filename, the exact `${{ … }}` expression) -> why it is inert.
    "bounty-claim-guard.yml": (
        ("${{ steps.guard.outputs.exit }}", "an integer exit status from the guard script"),
    ),
    "ci-cross-platform.yml": (
        ("${{ steps.test.outputs.pytest_exit }}", "an integer pytest exit code"),
    ),
    "field-report-schema.yml": (
        ("${{ steps.base.outputs.base }}", "a 40-char git sha, which cannot spell `$(…)`"),
    ),
    "intake-auto-review.yml": (
        (
            "${{ steps.review.outputs.decision }}",
            "a closed vocabulary — the producing step writes `decision=question` / "
            "`=lesson` / `=archive` as literal constants, not as model output",
        ),
    ),
    "misakanet-setup-publish.yml": (
        ("${{ steps.pack.outputs.version }}", "a semver string read from package.json"),
        (
            "${{ steps.pack.outputs.tgz }}",
            "a tarball path built by `npm pack` from the package name; the package name "
            "is `misakanet-setup`, not PR-controlled",
        ),
    ),
    "pr-checks.yml": (
        ("${{ steps.scope.outputs.scope }}", "one of a fixed set of labels the step assigns"),
        ("${{ steps.score.outputs.score }}", "a numeric quality score"),
    ),
    "update-badges.yml": (
        ("${{ steps.count.outputs.lessons }}", "a lesson count"),
    ),
    "auto-draft.yml": (
        (
            "${{ steps.draft.outputs.draft_file }}",
            "the producing step does `ls -t lessons/drafts/draft-*.md | head -1`, so the "
            "value is a path on disk rather than raw input; and the workflow only runs on "
            "`workflow_dispatch` and `repository_dispatch`, both of which need a token "
            "with `contents: write`. Anyone able to trigger it can already push a "
            "workflow file, so a crafted filename is not an escalation.",
        ),
    ),
    # Note what is *not* on this list, because the two differ in exactly that privilege:
    # `lesson-gate.yml`, `provenance-gate.yml` and `lesson-quality.yml` all run on
    # `pull_request`, which a fork can trigger, and all three interpolate a list of
    # filenames. Those are fixed — the value crosses through `env:`.
}


def _workflows() -> list[Path]:
    files = sorted(WORKFLOWS.glob("*.yml")) + sorted(WORKFLOWS.glob("*.yaml"))
    assert files, f"no workflow files under {WORKFLOWS}; this gate is now vacuous"
    return files


def _steps() -> list[tuple[Path, str, str, str]]:
    """(path, job, step name, run body) for every step that has one."""
    out = []
    for path in _workflows():
        text = path.read_text(encoding="utf-8")
        doc = yaml.safe_load(text)
        if not isinstance(doc, dict) or "jobs" not in doc:
            continue
        for job_name, job in (doc.get("jobs") or {}).items():
            if not isinstance(job, dict):
                continue
            for step in job.get("steps") or []:
                if isinstance(step, dict) and "run" in step:
                    out.append(
                        (path, job_name, str(step.get("name", "<unnamed>")), str(step["run"]))
                    )
    return out


def test_the_gate_sees_any_steps() -> None:
    """Otherwise both checks below pass on an empty list."""
    steps = _steps()
    assert len(steps) > 50, (
        f"only {len(steps)} run-steps found across {len(_workflows())} workflows. If the "
        "directory or the parsing changed, this gate is checking a fraction of the "
        "surface it was written for."
    )


def test_the_injection_pattern_actually_matches_the_spellings_in_use() -> None:
    """The self-test, and the reason this file exists.

    The first version of `UNTRUSTED` ended at `\\.outputs` and required `}}` next, so it
    matched **nothing** — including the two live injections it was written for. All three
    mutations passed it. The regex was never exercised against a real expression until
    a mutation was run, which is the same mistake the file is about.

    So: the pattern is checked against the exact strings the repository used, plus the
    near-misses that must *not* fire. If this test is ever deleted, the gate below it
    is no longer evidence of anything.
    """
    must_match = [
        # The two that shipped, verbatim from lesson-gate.yml before the fix.
        'FILES="${{ steps.classify.outputs.added }}"',
        'FILES="${{ steps.classify.outputs.modified }}"',
        # provenance-gate tier 1's combined form.
        'FILES="${{ steps.classify.outputs.added }} ${{ steps.classify.outputs.modified }}"',
        # A step id containing a dot or a dash, and a property chain on the output.
        '${{ steps.my-step.outputs.value }}',
        '${{ steps.a.b.outputs.count }}',
        # The free-text contexts: a branch name, a title, a commit message.
        '${{ github.event.pull_request.head.ref }}',
        '${{ github.event.pull_request.title }}',
        '${{ github.event.issue.body }}',
        '${{ github.event.head_commit.message }}',
        # With a fallback, as Actions allows.
        '${{ github.event.pull_request.head.ref || github.event.repository.default_branch }}',
        # Dispatch inputs, copied from the three sites that were live until this rule was
        # added. All three were reachable only by someone holding write access, and all
        # three are gone; these entries are here so that "gone" has a definition that does
        # not depend on remembering which files they were in.
        'if [ "${{ inputs.post }}" = "false" ]; then',
        'echo "== last ${{ inputs.days }} day(s) by scope =="',
        "date('now', '-${{ inputs.days }} day')",
        '${{ inputs.mode || \'suggest-only\' }}',
    ]
    for expr in must_match:
        assert UNTRUSTED.search(expr), (
            f"UNTRUSTED does not match {expr!r}. The gate would pass a workflow "
            "carrying exactly that expression, which is the defect it exists to catch."
        )

    must_not_match = [
        # GitHub-generated, and not expressible as `$(…)`:
        '${{ github.event.pull_request.base.sha }}',
        '${{ github.event.pull_request.number }}',
        '${{ github.event.issue.number }}',
        '${{ github.event.workflow_run.head_sha }}',
        '${{ github.event.pull_request.changed_files || 0 }}',
        '${{ github.event.pull_request.head.repo.full_name }}',
        # Not an event or a step at all:
        '${{ secrets.GITHUB_TOKEN }}',
        '${{ matrix.python }}',
        '${{ runner.temp }}',
    ]
    for expr in must_not_match:
        assert not UNTRUSTED.search(expr), (
            f"UNTRUSTED matches {expr!r}, which an outside party cannot choose. A rule "
            "that fires on GitHub's own hashes and counters trains people to ignore it."
        )


def test_the_safe_list_does_not_go_stale() -> None:
    """An allowlist that keeps entries nobody uses is a list nobody reads.

    Each entry is a claim about a line of code. If the line moves, the claim silently
    stops applying — and the gate goes back to firing on a value whose safety was never
    re-established. So a stale entry is an error here, not a tidy-up.
    """
    live = set()
    for path, _job, _name, run in _steps():
        for match in UNTRUSTED.finditer(run):
            live.add((path.name, match.group(0)))

    listed = {
        (wf, expr) for wf, entries in SAFE_OUTPUTS.items() for expr, _why in entries
    }
    stale = sorted(listed - live)
    assert not stale, (
        f"SAFE_OUTPUTS lists expressions that no longer appear: {stale}. Remove them, or "
        "fix the rule — either way a claim about code that has moved must not outlive it."
    )
    for wf, entries in SAFE_OUTPUTS.items():
        for expr, why in entries:
            assert why.strip(), f"SAFE_OUTPUTS[{wf!r}][{expr!r}] has no reason recorded"


@pytest.mark.parametrize(
    "path,job,name,run",
    _steps(),
    ids=[f"{p.name}:{j}:{n[:40]}" for p, j, n, _r in _steps()],
)
def test_run_bodies_do_not_interpolate_untrusted_text(
    path: Path, job: str, name: str, run: str
) -> None:
    """`${{ }}` in a `run:` is script text, and these contexts are attacker-chosen.

    GitHub substitutes the expression before the shell ever sees it, so the value is
    parsed as part of the program. Combined with bash expanding `$(...)` inside double
    quotes, any of these becomes command execution — demonstrated on 2026-10-07 with a
    file named `lessons/core/$(id).md`.

    Pass the value through `env:` and read it as a variable instead:

        env:
          ADDED_FILES: ${{ steps.classify.outputs.added }}
        run: |
          IFS=' ' read -r -a FILES <<< "$ADDED_FILES"

    Interpolation into `if:`, `env:`, `with:` or `run:` name is fine — only the
    `run:` *body* is parsed by a shell.
    """
    rel = path.relative_to(REPO)
    allowed = {expr for expr, _why in SAFE_OUTPUTS.get(rel.name, ())}

    hit = UNTRUSTED.search(run)
    assert hit is None or hit.group(0) in allowed, (
        f"{rel.name}:{job}:{name} interpolates `{hit.group(0) if hit else ''}` into a run: "
        "body, and it is not on the reviewed list.\n"
        "  GitHub substitutes ${{ }} before bash parses, and bash runs $(...) inside "
        "double quotes and inside an unquoted `for` word, so a pull request that controls "
        "this text gets command execution on the runner — a file named "
        "`lessons/core/$(id).md` is enough.\n"
        "  Either move it to `env:` and read the variable in the script (preferred), or "
        "add it to SAFE_OUTPUTS in this file with the reason the value cannot carry "
        "attacker text. Do not delete the rule."
    )


@pytest.mark.parametrize(
    "path,job,name,run",
    [s for s in _steps() if "|" in s[3]],
    ids=[f"{p.name}:{j}:{n[:40]}" for p, j, n, r in _steps() if "|" in r],
)
def test_a_piped_checker_can_still_fail(path: Path, job: str, name: str, run: str) -> None:
    """`checker | tee` decides nothing: without `pipefail` the step reports `tee`'s status.

    Measured 2026-10-07 on `provenance-gate.yml` tier 2: a new lesson citing a 404 made
    `check_provenance.py` print a failure and exit 1, and the step still reported
    success. The fix is either

        set -o pipefail
        checker | tee report.txt

    or the explicit form tier 1 already uses:

        set +e
        checker | tee report.txt
        RC=${PIPESTATUS[0]}
        set -e
        [ "$RC" -ne 0 ] && exit 1

    A pipeline that only *renders* output (no checker before the pipe) is fine and is
    not the shape this looks for — the check is whether a `python`/`node`/`bash`
    invocation sits to the left of a pipe with no status handling to the right.
    """
    rel = path.relative_to(REPO)

    # Only a checker piped into something that always succeeds loses its verdict. A
    # second checker on the left (`python3 a.py | python3 -c …`) is a different shape,
    # and so is `echo x | bc`; neither is what this rule is about, and folding them in
    # produced four false positives against steps that track their own status
    # (`|| FAILED=1`, `|| echo "0"`).
    risky = [
        ln
        for ln in run.splitlines()
        if not ln.lstrip().startswith("#")
        and re.search(r"\b(python3?|node|npx)\b[^|]*\S[^|]*\|\s*(tee|cat)\b", ln)
    ]
    if not risky:
        return

    handles_status = bool(
        re.search(r"pipefail", run)
        or re.search(r"PIPESTATUS", run)
        # `|| FAILED=1` / `|| echo 0` — the step decides the outcome without the pipe.
        or re.search(r"\|\|\s*\w+=", run)
        or re.search(r"\|\|\s*echo\b", run)
        or re.search(r"if\s+\[\s*\"?\$\{?FAILED", run)
    )
    assert handles_status, (
        f"{rel.name}:{job}:{name} pipes a checker into a command that always succeeds and "
        f"never looks at the checker's status:\n  {risky[0].strip()}\n"
        "  Without `set -o pipefail` (or capturing ${PIPESTATUS[0]}), the step reports the "
        "LAST command's exit status, so a failing check reports success. Measured "
        "2026-10-07 on provenance-gate tier 2: a lesson citing a 404 made the script "
        "print a failure and exit 1, and the step still went green."
    )
