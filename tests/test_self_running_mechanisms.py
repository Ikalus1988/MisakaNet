#!/usr/bin/env python3
"""A mechanism that runs by itself must not be able to finish green having produced nothing.

The rule this file enforces: **every mechanism that can run on its own must be able to fail when
its production fails** — that is the cheapest possible form of the gate "it can produce something",
because it needs no new machinery: the workflow simply may not end green while the thing it was
built to deliver did not happen.

Measured 2026-10-26, the reason this file exists. `ci-lesson-search.yml` is the repository's
"our CI failed, so surface the lessons that match" mechanism, and it is triggered by
`Cross-Platform Tests` — the cross-platform matrix, where platform drift shows up. It fired on a
genuinely failing matrix and produced **nothing**: `Get failure context` reported success, both
downstream steps were skipped, the pull request got no note, and the workflow reported green. Two
independent breaks sat on that path: the token had no `actions` scope, so the log read was refused
and the refusal was swallowed by an empty `catch`; and `context.repo.full_name` does not exist, so
`is_same_repo` was always false and the note could not be posted even once a decision was reached.

The shape is the one this repository already knows, twice: a crash that became a *constant payload*
so the run stayed green with nothing posted (#1825), and a step whose `$ERROR_SIG` was undefined so
the search had nothing to search and stayed green (#1984: **a green run is not evidence unless
something in it can differ**).

So the check is over the workflows that run without a pull request attached to them — `schedule`,
`workflow_run`, `issues`, `issue_comment` — and that can write to the repository. For each of them,
nothing on the path to the delivery may swallow a failure quietly:

* **the producer** — the command that posts the comment or opens the issue — must be load-bearing:
  if it fails, the step fails and the workflow ends red;
* **the producer's feeders** — the steps whose outputs gate that producer — must be load-bearing
  too, and so must *their* feeders. This is the half that catches the `ci-lesson-search` shape:
  the producing step was perfectly sound, and the step that fed it was the one that could not do its
  job and said nothing. A feeder that swallows its failure leaves the producer *skipped*, and a
  skipped producer is a mechanism that produced nothing and reported success.

What this file deliberately does not do:

* it does not judge *whether* a mechanism's output is useful — only whether its failure can be
  seen. "It produced something" and "it produced the right thing" are two questions, and only the
  first one is decidable from the workflow's text;
* it does not require every workflow to have a test of its own. That is a registry, and a registry
  of sixty-odd workflows is not a gate — it is a list of intentions. The check below is derived
  from the workflows themselves, so a new mechanism is covered the day it is written.

And what it cannot see, stated plainly rather than left to be discovered:

* a production that happens *inside a script* (`python3 scripts/register_issue.py`) — the workflow
  text says only "run a script", and whether that script posts a comment is not decidable here;
* a production performed by a *third-party action* (`actions/stale` labels issues; the workflow text
  does not say what it did);
* a production that goes to *another system* rather than to the repository (`lesson-notify.yml`
  posts to a Feishu webhook) — the `permissions:` block says nothing about it, and the webhook's
  own failure modes live in the webhook;
* a *semantic* silence — the producer runs, the run is green, and the thing it produced is empty
  because the decision it was reading was always "no". `context.repo.full_name` was exactly that:
  the path read the logs, reached a decision, and still posted nothing. No rule over workflow text
  can see it; it needs a probe that exercises the path (`tests/test_ci_failure_lesson_path.py`).
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
WORKFLOWS = REPO / ".github" / "workflows"

# The triggers under which a workflow runs *by itself* — nobody is waiting on it, so a failure that
# nobody sees is a failure that nobody will ever fix.
SELF_TRIGGERS = {"schedule", "workflow_run", "issues", "issue_comment"}

# A command that produces something a human (or a downstream job) reads. `gh api` is only a
# producer when it writes; a plain GET is a read, and reads are allowed to fail quietly.
#
# `curl -X POST` is here because a webhook delivery is a production too, and because the rule it
# encodes was learned the hard way in `lesson-notify.yml`: `curl -s` exits 0 on an HTTP 4xx/5xx,
# so a payload the receiver rejected looked exactly like a delivery that worked.
PRODUCERS = re.compile(
    r"""^\s*(?:
          gh\s+pr\s+comment
        | gh\s+issue\s+(?:create|comment)
        | gh\s+release\s+create
        | git\s+push
        | gh\s+api\b[^\n]*(?:-X|--method)\s*(?:POST|PATCH|PUT)
        | curl\b[^\n]*-X\s*POST
    )""",
    re.X | re.I,
)
# The same, inside a `github-script` step: the API call is what produces the comment.
API_WRITE = re.compile(
    r"createComment|createIssue|createReview|createDispatchEvent|createCommitStatus"
)

# A failure that cannot reach the exit code.
#
# `|| true` and `|| echo …` swallow it outright. `|| { … }` *handles* it, and a handler that ends in
# `exit 1` re-raises it — that is load-bearing, not silent: `update-smithery-badge.yml` pushes with
# `|| { echo "push conflict, retrying..."; …; git push … || { echo "::error::push to data failed";
# exit 1; }; }`, and the failure does reach the exit code.
SILENT_LINE = re.compile(r"\|\|\s*(?:true|echo\b[^\n]*)\s*$")
HANDLED = re.compile(r"\|\|\s*\{")
RE_RAISED = re.compile(r"\bexit\s+(?:1|\$\?)")
SET_PLUS_E = re.compile(r"^\s*set\s+\+e\s*$")
SET_MINUS_E = re.compile(r"^\s*set\s+-e\s*$")

# `curl` without `--fail` cannot tell a rejected payload from a delivered one.
CURL = re.compile(r"^\s*curl\b")
CURL_FAIL = re.compile(r"(?:^|\s)(?:--fail|-f)(?:\s|$)")

CATCH_HEAD = re.compile(r"catch\s*\(([^)]*)\)\s*\{")
CATCH_RETHROWS = re.compile(r"throw\b|core\.setFailed")

# A second delivery channel that needs no `pull-requests: write`: the job summary. GitHub renders
# it for anyone who can open the run, fork PRs included, and it is written by the job itself.
#
# This exists because of #3977: `provenance-gate.yml` published its verdict *only* as a PR comment,
# and a `pull_request`-triggered workflow on a **fork** PR gets a read-only token whatever
# `permissions:` declares. The comment 403'd, the check went red, and the verdict reached nobody.
# The fix moved the verdict to `$GITHUB_STEP_SUMMARY` and demoted the comment to a bonus — which
# this gate flagged, correctly, because a silent producer is what it is built to find. The missing
# piece is the distinction the fix introduced: a silent *bonus* channel is fine when the verdict
# has a load-bearing channel of its own.
#
# Both halves are required, and deliberately:
#   * a load-bearing step-summary writer — the channel has to exist and be able to fail;
#   * the `# verdict-channel: step-summary` marker — so the exception is a declared decision a
#     reviewer can see, not a shape the gate happens to accept. Workflows write summaries for all
#     sorts of reasons (tables, counts, links) and none of those carry the verdict.
STEP_SUMMARY = re.compile(r"\$\{?GITHUB_STEP_SUMMARY\}?")
VERDICT_CHANNEL_MARKER = re.compile(r"#\s*verdict-channel:\s*step-summary\b")


def _workflows() -> list[Path]:
    return sorted(WORKFLOWS.glob("*.yml"))



def _triggers(doc: dict) -> set[str]:
    on = doc.get(True) or doc.get("on") or {}
    return set(on.keys()) if isinstance(on, dict) else set()


def _writes(doc: dict) -> bool:
    """Can this workflow write to the repository?"""
    scopes: dict = {}
    if isinstance(doc.get("permissions"), dict):
        scopes.update(doc["permissions"])
    for job in (doc.get("jobs") or {}).values():
        if isinstance(job.get("permissions"), dict):
            scopes.update(job["permissions"])
    return any(v == "write" for v in scopes.values())


def _step_shell(step: dict) -> str:
    """The shell text of a step.

    A composite action takes its command as an *input* (`with: run:`), so a step that calls one
    carries its body in `with:` rather than in `run:` — `lesson-notify.yml` posts its webhook
    through `.github/actions/retry/`, and a check that only ever looked at `run:` would not see the
    delivery at all.
    """
    return step.get("run") or (step.get("with") or {}).get("run") or ""


def _shell_units(run: str) -> list[tuple[str, bool]]:
    """The shell body as logical units: (command plus the `{ … }` handler that follows it, whether
    errexit was off at that point).

    A handler can be on the next line — `fix-dco.yml` pushes with `|| {` and re-raises with `exit 1`
    two lines later — so judging one line at a time calls that silent when it is not. And `set +e`
    is *scoped*: `adopt-pr.yml` turns errexit off for one command, reads its exit code, turns it
    back on, and only then posts the comment — so a step that mentions `set +e` is not a step
    whose every command is soft.
    """
    units: list[tuple[str, bool]] = []
    current: list[str] = []
    depth = 0
    soft = False
    unit_soft = False
    for line in run.splitlines():
        if SET_PLUS_E.match(line):
            soft = True
            continue
        if SET_MINUS_E.match(line):
            soft = False
            continue
        if not current:
            unit_soft = soft
        current.append(line)
        depth += line.count("{") - line.count("}")
        if depth <= 0:
            units.append(("\n".join(current), unit_soft))
            current, depth = [], 0
    if current:
        units.append(("\n".join(current), unit_soft))
    return units


def _catch_bodies(script: str) -> list[tuple[str, str]]:
    """(caught parameter, body) for every `catch (…) { … }` in a script.

    The body is found by balancing braces, not by a regular expression. A body can contain braces —
    a template literal, an object literal, a nested call — and a regex that stops at the first `}`
    reads such a body as empty and calls a load-bearing catch a silent one. A gate that is wrong
    about the code it judges is worse than no gate: it teaches people to ignore it.
    """
    out: list[tuple[str, str]] = []
    for match in CATCH_HEAD.finditer(script):
        body, _end = _balanced_body(script, match.end())
        out.append((match.group(1), body))
    return out


def _balanced_body(text: str, start: int) -> tuple[str, int]:
    """The text of the brace group that opened at `start`, and the index after it.

    Strings and comments are skipped: a `}` inside a string is a character, not a closing brace.
    A template literal is skipped whole — its `${…}` is balanced inside it, so skipping it leaves
    the depth the same.
    """
    depth = 1
    i = start
    n = len(text)
    while i < n:
        ch = text[i]
        if ch in ("'", '"', "`"):
            quote = ch
            i += 1
            while i < n and text[i] != quote:
                i += 2 if text[i] == "\\" else 1
            i += 1
            continue
        if text.startswith("//", i):
            nl = text.find("\n", i)
            i = n if nl < 0 else nl + 1
            continue
        if text.startswith("/*", i):
            end = text.find("*/", i)
            i = n if end < 0 else end + 2
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i], i + 1
        i += 1
    return text[start:], n


def _is_producer(step: dict) -> bool:
    script = (step.get("with") or {}).get("script") or ""
    if script and API_WRITE.search(script):
        return True
    return any(PRODUCERS.match(line) for line in _step_shell(step).splitlines())


def _shell_producer_is_silent(step: dict) -> bool:
    """Does the producing command's failure stop the step?"""
    run = _step_shell(step)
    soft = step.get("continue-on-error") is True
    for unit, unit_soft in _shell_units(run):
        producer_lines = [ln for ln in unit.splitlines() if PRODUCERS.match(ln)]
        if not producer_lines:
            continue
        if soft or unit_soft:
            return True
        if any(SILENT_LINE.search(ln) for ln in producer_lines):
            return True
        if any(CURL.match(ln) and not CURL_FAIL.search(ln) for ln in producer_lines):
            # A webhook that rejected the payload looks exactly like a webhook that worked.
            return True
        if HANDLED.search(unit) and not RE_RAISED.search(unit):
            return True
    return False


def _script_producer_is_silent(step: dict) -> bool:
    """A `github-script` step fails on an uncaught throw — unless it catches and swallows."""
    script = (step.get("with") or {}).get("script") or ""
    for _caught, body in _catch_bodies(script):
        statements = [
            ln.strip()
            for ln in body.splitlines()
            if ln.strip() and not ln.strip().startswith("//")
        ]
        if not statements:
            # An empty catch: the failure was seen and dropped, and nothing says so.
            return True
        if not CATCH_RETHROWS.search(body):
            # It caught something and did not re-raise it: the failure cannot reach the exit code.
            return True
    if step.get("continue-on-error") is True:
        return True
    return False


def _producer_is_silent(step: dict) -> bool:
    if (step.get("with") or {}).get("script"):
        return _script_producer_is_silent(step)
    return _shell_producer_is_silent(step)


def _feeder_swallows(step: dict) -> str:
    """How (if at all) this step swallows its own failure. `''` means it does not."""
    script = (step.get("with") or {}).get("script") or ""
    for caught, body in _catch_bodies(script):
        statements = [
            ln.strip()
            for ln in body.splitlines()
            if ln.strip() and not ln.strip().startswith("//")
        ]
        if not statements:
            # A catch whose body is only a comment: the refusal was seen and then dropped.
            return "a catch that says nothing"
        if CATCH_RETHROWS.search(body):
            continue
        # A catch that carries the error out of the block — records it, logs it — has not dropped
        # it: the difference between "we were not allowed to look" and "there was nothing to say"
        # is exactly what that record is for.
        param = caught.strip().split()[0] if caught.strip() else ""
        if param and re.search(rf"\b{re.escape(param)}\b", body):
            continue
        return "a catch that does not re-raise"
    if step.get("continue-on-error") is True:
        return "continue-on-error"
    run = _step_shell(step)
    if SET_PLUS_E.search(run) and not RE_RAISED.search(run):
        return "set +e without re-raising"
    return ""


def _mechanisms(directory: Path | None = None) -> list[tuple[str, list[dict]]]:
    """(workflow name, its steps) for the workflows that run by themselves."""
    out = []
    for path in sorted((directory or WORKFLOWS).glob("*.yml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(doc, dict):
            continue
        if not (_triggers(doc) & SELF_TRIGGERS) or not _writes(doc):
            continue
        for job in (doc.get("jobs") or {}).values():
            out.append((path.name, job.get("steps") or []))
    return out


def _feeder_ids(producer: dict) -> list[str]:
    """The steps whose outputs this step reads — its feeders, in the order they appear.

    The condition and the environment are both read: a step can be gated by an output in its `if:`
    or receive one through `env:`, and both make the output load-bearing for what happens next.
    """
    text = (producer.get("if") or "") + "\n" + "\n".join(
        f"{k}: {v}" for k, v in (producer.get("env") or {}).items()
    )
    seen: list[str] = []
    for step_id in re.findall(r"steps\.([A-Za-z0-9_-]+)\.outputs", text):
        if step_id not in seen:
            seen.append(step_id)
    return seen


def _step_summary_is_load_bearing(step: dict) -> bool:
    """Does this step write to the job summary in a way that can fail?

    "Can fail" is the same test the rest of this file applies to a producer: the step is not
    `continue-on-error`, the unit that writes the summary does not swallow its exit code, and the
    write is not inside a `set +e` region that never re-raises.
    """
    run = _step_shell(step)
    if not STEP_SUMMARY.search(run) or step.get("continue-on-error") is True:
        return False
    for unit, unit_soft in _shell_units(run):
        if not STEP_SUMMARY.search(unit):
            continue
        if unit_soft or SILENT_LINE.search(unit):
            return False
        if HANDLED.search(unit) and not RE_RAISED.search(unit):
            return False
        return True
    return False


def _declares_summary_verdict(path: Path, steps: list[dict]) -> bool:
    """The declared second channel: the marker **and** a load-bearing writer.

    Either half alone is not a channel. A marker with no writer names a channel that does not exist;
    a writer with no marker is how a workflow writes an unrelated summary, and excusing a silent
    producer on the strength of an unrelated table is exactly the kind of drift this file exists to
    stop.
    """
    if not VERDICT_CHANNEL_MARKER.search(path.read_text(encoding="utf-8")):
        return False
    return any(_step_summary_is_load_bearing(step) for step in steps)


def _silent_only_by_continue_on_error(step: dict) -> bool:
    """Would this producer be loud if the step-level `continue-on-error` flag were removed?

    The flag is the declared "this step is a bonus" spelling. `|| true` inside a multi-command
    script is not the same declaration — it can hide a failure in the middle of the step — so a
    declared second channel excuses only the flag, not every way of swallowing.
    """
    if step.get("continue-on-error") is not True:
        return False
    copy = dict(step)
    copy.pop("continue-on-error", None)
    return not _producer_is_silent(copy)


def _violations(directory: Path | None = None) -> list[str]:
    directory = directory or WORKFLOWS
    out: list[str] = []
    for name, steps in _mechanisms(directory):
        by_id = {st.get("id"): st for st in steps if st.get("id")}
        producers = [st for st in steps if _is_producer(st)]
        if not producers:
            # Nothing here produces anything a human reads — it only reads, or only builds. A
            # mechanism with no producer cannot "produce nothing", so there is nothing to judge.
            continue
        # The declared second channel (see STEP_SUMMARY above): present only when the workflow
        # says so *and* the writer it names is load-bearing. Both halves, or the exception is a
        # shape rather than a decision.
        summary_verdict = _declares_summary_verdict(directory / name, steps)
        for producer in producers:
            label = producer.get("name", "?")
            if _producer_is_silent(producer) and not (
                summary_verdict and _silent_only_by_continue_on_error(producer)
            ):
                out.append(f"{name} — the producer can fail quietly: {label}")
            # The producer's feeders, and their feeders: a step whose outputs gate the producer
            # must be load-bearing too. A feeder that swallows its failure leaves the producer
            # *skipped*, and a skipped producer is a mechanism that produced nothing and reported
            # success.
            for feeder_id in _feeder_ids(producer):
                feeder = by_id.get(feeder_id)
                if feeder is None:
                    continue
                why = _feeder_swallows(feeder)
                if why:
                    out.append(
                        f"{name} — {label} depends on {feeder_id}, "
                        f"which swallows its failure ({why})"
                    )
                # One hop further: a feeder of the feeder. `ci-lesson-search.yml` had the shape
                # producer → intake → context, and `context` was the step that could not do its
                # job; had the producer read only `intake`'s output, the break would still have
                # left the producer skipped.
                for grand_id in _feeder_ids(feeder):
                    grand = by_id.get(grand_id)
                    if grand is None:
                        continue
                    why = _feeder_swallows(grand)
                    if why:
                        out.append(
                            f"{name} — {label} depends on {feeder_id}, "
                            f"which depends on {grand_id}, "
                            f"which swallows its failure ({why})"
                        )
    return out


def test_no_self_running_mechanism_can_finish_green_having_produced_nothing():
    """The rule, applied to the workflows that run by themselves.

    A mechanism whose production can fail quietly is a mechanism that can end green having
    produced nothing — the shape that let `ci-lesson-search.yml` sit broken for months.
    """
    violations = _violations()
    assert not violations, (
        "a mechanism that runs by itself must be able to fail when its production fails, so that "
        "the failure is visible instead of silent:\n  " + "\n  ".join(violations)
    )


def test_the_check_can_see_a_mechanism_whose_production_is_swallowed():
    """The gate has to be able to go red, or it is a decoration (#1984).

    This builds the shape the rule is about — a self-running workflow that writes to the
    repository, whose only producer swallows its own failure — and asserts the check catches it.
    """
    step = {
        "run": "gh issue create --repo x/y --title t --body b || true\n",
    }
    assert _is_producer(step)
    assert _producer_is_silent(step), (
        "the check has to recognise a swallowed producer, or it cannot catch one"
    )


def test_a_load_bearing_producer_is_recognised():
    """The other half: a producer whose failure reaches the exit code is load-bearing."""
    step = {
        "run": "gh issue create --repo x/y --title t --body b\n",
    }
    assert not _producer_is_silent(step), (
        "a producer that is not swallowed must be recognised as load-bearing, or every workflow "
        "would look broken"
    )


def test_errexit_is_scoped_to_the_command_it_covers():
    """`set +e` is not a property of the step, it is a property of the commands it covers.

    `adopt-pr.yml` turns errexit off for one command, reads its exit code, turns it back on, and
    only then posts the comment — so the comment is load-bearing, and a step that merely mentions
    `set +e` is not a step whose every command is soft.
    """
    step = {
        "run": (
            "set +e\n"
            "python3 scripts/adopt_pr.py ...\n"
            "rc=$?\n"
            "set -e\n"
            "gh pr comment 1 --body-file /tmp/c.md\n"
        ),
    }
    assert not _producer_is_silent(step), (
        "a producer that runs after errexit was restored is load-bearing, and calling it silent "
        "would send the rule after the wrong workflows"
    )


def test_a_catch_that_says_nothing_counts_as_swallowing():
    """The `ci-lesson-search` shape: the refusal was seen and then dropped.

    `catch (e) { // Logs may not be available }` is not an empty body to a reader, and it is not an
    empty body to a compiler either — but to the workflow it is exactly as empty as `catch (e) {}`:
    the failure cannot reach the exit code and nothing says it happened.
    """
    step = {
        "with": {
            "script": """
            try {
              await github.rest.actions.listJobsForWorkflowRun({});
            } catch (e) {
              // Logs may not be available
            }
            """
        }
    }
    assert _feeder_swallows(step) == "a catch that says nothing", (
        "a catch whose body is only a comment drops the failure exactly as an empty catch does"
    )


def test_a_catch_that_records_the_failure_is_not_swallowing():
    """Recording the failure is the point: it tells 'could not look' from 'nothing to say'."""
    step = {
        "with": {
            "script": """
            try {
              await github.rest.actions.listJobsForWorkflowRun({});
            } catch (e) {
              readFailures.push(e.message);
            }
            """
        }
    }
    assert _feeder_swallows(step) == "", (
        "a catch that records the failure is not swallowing it — the recording is what makes the "
        "difference visible"
    )


def test_a_catch_whose_body_contains_braces_is_still_read():
    """The blind spot a regular expression would have left open.

    A catch body that builds a message with a template literal holds braces of its own. A check
    that reads the body by matching up to the first `}` sees an empty body and calls a
    load-bearing catch a silent one — and then a workflow that is *correct* gets reported as
    broken, which is how a gate teaches people to ignore it.
    """
    step = {
        "with": {
            "script": """
            try {
              await github.rest.issues.createComment({});
            } catch (e) {
              core.setFailed(`the comment did not land: ${e.message}`);
            }
            """
        }
    }
    assert _feeder_swallows(step) == "", (
        "a catch that fails the step is load-bearing, and its body must be read whole"
    )
    assert not _producer_is_silent(step), (
        "the same catch, on a producing step, must not be called silent either"
    )


def test_a_webhook_without_fail_is_a_silent_production():
    """`curl -s` exits 0 on an HTTP 4xx/5xx, so a rejected payload looks like a delivery.

    `lesson-notify.yml` learned this the hard way — its own comment records it: a title carrying
    a quote made Feishu answer 400, `curl -s` still exited 0, the notification was dropped and the
    job reported success. `--fail` is what makes the loss visible.
    """
    silent = {"run": 'curl -s -X POST "$WEBHOOK" -d "$PAYLOAD"\n'}
    loud = {"run": 'curl -s --fail -X POST "$WEBHOOK" -d "$PAYLOAD"\n'}
    assert _is_producer(silent)
    assert _producer_is_silent(silent), (
        "a webhook delivery that cannot tell a rejection from a success cannot fail"
    )
    assert not _producer_is_silent(loud), (
        "`--fail` makes the delivery load-bearing, and the check must recognise that"
    )


def test_the_rule_sees_the_producer_behind_a_composite_action():
    """A composite action takes its command as an input, so the body is in `with:`, not `run:`.

    `lesson-notify.yml` posts through `.github/actions/retry/`. A check that only read `run:` would
    not see the delivery at all, and would pass a workflow whose whole purpose is to deliver.
    """
    step = {
        "uses": "./.github/actions/retry/",
        "with": {"run": 'curl -s -X POST "$WEBHOOK" -d "$PAYLOAD"'},
    }
    assert _is_producer(step), (
        "the production is in `with: run:` — the check has to look there too"
    )
    assert _producer_is_silent(step)


def test_the_write_method_spelling_is_a_producer():
    """`gh api --method POST` is the same production as `gh api -X POST`."""
    step = {"run": 'gh api repos/o/r/git/refs --method POST --input f.json\n'}
    assert _is_producer(step), (
        "the long spelling of the method flag writes just as the short one does"
    )


# ── the declared second channel (#3977) ──
#
# `provenance-gate.yml` published its verdict only as a PR comment. A `pull_request`-triggered
# workflow on a fork PR gets a read-only token, so the comment 403'd and the verdict reached
# nobody; the fix writes the verdict to `$GITHUB_STEP_SUMMARY` first and marks the comment as a
# bonus with `continue-on-error: true`. This gate has to be able to tell that shape — a silent
# *bonus* beside a load-bearing verdict channel — from the shape it was built to catch.

BASE_WORKFLOW = """\
name: verifier
on:
  workflow_run:
    workflows: ["x"]
    types: [completed]
permissions:
  contents: read
  pull-requests: write
jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
"""

SUMMARY_STEP = """\
      - name: Publish the verdict to the step summary
        run: |
          {
            echo "## Provenance gate"
            cat report.txt
          } >> "$GITHUB_STEP_SUMMARY"
"""

COMMENT_STEP = """\
      - name: Comment the result on the PR
        continue-on-error: true
        run: gh pr comment "$PR" --body-file body.md
"""


def _gate(tmp_path, *steps: str, marker: bool = True) -> list[str]:
    text = BASE_WORKFLOW + "".join(steps)
    if marker:
        text = text.replace("    steps:\n", "    steps:\n      # verdict-channel: step-summary\n")
    (tmp_path / "verifier.yml").write_text(text, encoding="utf-8")
    return _violations(tmp_path)


def test_a_declared_step_summary_channel_excuses_a_bonus_comment(tmp_path):
    """The #3977 shape: the verdict has a load-bearing channel, the comment is a bonus."""
    assert _gate(tmp_path, SUMMARY_STEP, COMMENT_STEP) == [], (
        "a comment step declared as a bonus, beside a load-bearing step-summary verdict, is not a "
        "mechanism that can produce nothing"
    )


def test_without_the_marker_the_bonus_comment_is_still_a_violation(tmp_path):
    """A summary is not a verdict channel unless the workflow says it is.

    Many workflows write tables and counts to the summary; none of those carry the verdict, and
    excusing a silent producer on the strength of one would open the gate for every workflow that
    prints anything.
    """
    assert _gate(tmp_path, SUMMARY_STEP, COMMENT_STEP, marker=False), (
        "the same shape without the declaration must stay a violation"
    )


def test_a_marker_without_a_writer_is_not_a_channel(tmp_path):
    """The declaration cannot conjure a channel that does not exist."""
    assert _gate(tmp_path, COMMENT_STEP), (
        "a marker with no step-summary writer names a channel nothing writes to"
    )


def test_a_summary_writer_that_swallows_its_own_failure_is_not_a_channel(tmp_path):
    """The substitute channel has to be able to fail, or it is the original defect moved."""
    swallowed = SUMMARY_STEP.replace(
        "      - name:", "      - continue-on-error: true\n        name:"
    )
    assert _gate(tmp_path, swallowed, COMMENT_STEP), (
        "a step-summary writer that cannot fail is not a verdict channel"
    )


def test_the_declared_channel_only_excuses_the_step_level_flag(tmp_path):
    """`|| true` inside the script is not the "this step is a bonus" declaration.

    The step-level flag is visible in the workflow and scoped to the whole step; a `|| true` in a
    multi-command script can hide one failure among commands that were meant to be load-bearing.
    """
    hidden = COMMENT_STEP.replace("continue-on-error: true\n        ", "").replace(
        'run: gh pr comment "$PR" --body-file body.md',
        'run: gh pr comment "$PR" --body-file body.md || true',
    )
    assert _gate(tmp_path, SUMMARY_STEP, hidden), (
        "a producer whose failure is swallowed inside its own script is not excused by a summary"
    )
