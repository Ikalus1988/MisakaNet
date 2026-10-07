#!/usr/bin/env python3
"""A comment on an issue must not be able to spend a model call or borrow the bot's token.

`pr-agent-review.yml` answers four slash commands — `/review`, `/describe`, `/improve`, `/ask` — and
matches them with `contains(body, …)` on **any** `issue_comment`. Until 2026-10-07 the `issue_comment`
branch carried no `author_association` check, so any GitHub account could post `/review` on any issue
in the repository and the job would run `Codium-ai/pr-agent` against `OPENAI_KEY` while holding
`pull-requests: write` and `issues: write` (workflow lines 9-11). Its two sibling commands already
carried the gate — `fix-dco.yml:22` and `adopt-pr.yml:35` — which is what made the omission a
one-line diff rather than a design question.

**Why this file evaluates the expression instead of grepping for `author_association`.**

The substring version of this rule passes whenever the text appears *anywhere* in the `if:`, which is
the same weakness that made three earlier workflow rules in this repository unbreakable rather than
unbreakable-in-theory. `tests/test_automated_prs_skip_llm_review.py` records each one: a decoy step
carrying the guard while the real model step ran unguarded, a second unguarded model step in an
already-guarded job, and a marker that exists only inside a comment `yaml.safe_load` throws away. In
each case the text was present and the guard was dead. A security gate is exactly the assertion that
must answer "does the condition still refuse the input?", so this file parses and runs the `if:`.

A recursive-descent parser is used rather than translating GitHub's operators into Python with
`str.replace`. The first attempt at that translation turned `!startsWith(github.head_ref, 'bot/')`
into ` not startsWith(github.head_ref, 'bot/')`, which then failed to parse — a `SyntaxError` in the
simulator that says nothing about the workflow, and an easy thing to misread as "the YAML is broken".

The evaluator is itself checked against two workflows that are **already running in production** and
use this exact idiom at opposite polarity: `adopt-pr.yml` fires for maintainers only, while
`newbie-welcome.yml` fires for everyone *except* maintainers. If both come out right, `!`, `fromJSON`
and the `labels.*.name` splat are being handled, not just the happy path.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml", reason="PyYAML parses the workflow")

REPO = Path(__file__).resolve().parent.parent
WORKFLOWS = REPO / ".github" / "workflows"
PR_AGENT_REVIEW = WORKFLOWS / "pr-agent-review.yml"

#: The same list, in the same spelling, as `fix-dco.yml:22` and `adopt-pr.yml:35`. Held as a constant
#: so a future edit that switches to a different association set has to change it here too.
PRIVILEGED = ("MEMBER", "OWNER", "COLLABORATOR")
PRIVILEGED_JSON = json.dumps(list(PRIVILEGED))

#: `pull_request` events have no comment author — `github.event.comment` is absent, and GitHub
#: documents that dereferencing a missing property yields an empty string rather than an error. So a
#: rule that insists on an association check *everywhere* would either be wrong or force the gate onto
#: a branch that cannot evaluate it. The association belongs on the `issue_comment` branch only.
ASSOCIATION_CONTEXT = "github.event.comment.author_association"


# ── A recursive-descent evaluator for the GitHub Actions expression subset ─────────────────────────
#
# Operators, lowest precedence first, per GitHub's documented table: `||`, then `&&`, then the
# comparisons, then the unary `!`, then `.`/`[]`, then calls. Anything outside the subset raises rather
# than guessing — a silent fallback here would make a rule that cannot fail, which is the very thing
# this file exists to prevent.

_TOKEN = re.compile(
    r"""
      \s+
    | (?P<op>\|\||&&|==|!=|>=|<=|!|[<>])
    | (?P<str>'(?:[^']|'')*'|"(?:[^"]|"")*")
    | (?P<num>\d+)
    | (?P<name>[A-Za-z_][A-Za-z0-9_\-]*)
    | (?P<punct>[(),.\[\]*])
    """,
    re.VERBOSE,
)


def _tokenize(source: str) -> list[tuple[str, str | None]]:
    tokens: list[tuple[str, str | None]] = []
    index = 0
    while index < len(source):
        match = _TOKEN.match(source, index)
        if match is None:
            raise SyntaxError(f"cannot tokenize at offset {index}: {source[index:index + 30]!r}")
        index = match.end()
        if match.lastgroup is None:          # the \s+ alternative
            continue
        tokens.append((match.lastgroup, match.group()))
    tokens.append(("eof", None))
    return tokens


class _Evaluator:
    def __init__(self, source: str, context: dict):
        self._tokens = _tokenize(source)
        self._at = 0
        self._context = context

    # -- token plumbing -----------------------------------------------------------------------
    def _peek(self) -> tuple[str, str | None]:
        return self._tokens[self._at]

    def _take(self) -> tuple[str, str | None]:
        token = self._tokens[self._at]
        self._at += 1
        return token

    def _expect(self, literal: str) -> None:
        _, value = self._take()
        if value != literal:
            raise SyntaxError(f"expected {literal!r}, found {value!r}")

    # -- grammar ------------------------------------------------------------------------------
    def evaluate(self):
        return self._or()

    def _or(self):
        value = self._and()
        while self._peek() == ("op", "||"):
            self._take()
            # The right side is parsed **before** the two are combined. Writing this as
            # `value = value or self._and()` short-circuits, and a short-circuited parse does not
            # consume its tokens — the enclosing `)` then lands on whatever followed, which surfaces
            # as a SyntaxError pointing at a token three lines away from the actual mistake.
            right = self._and()
            value = bool(value) or bool(right)
        return value

    def _and(self):
        value = self._comparison()
        while self._peek() == ("op", "&&"):
            self._take()
            right = self._comparison()      # parsed first, for the reason given in `_or`
            value = bool(value) and bool(right)
        return value

    def _comparison(self):
        value = self._unary()
        while self._peek()[0] == "op" and self._peek()[1] in ("==", "!=", ">", "<", ">=", "<="):
            operator = self._take()[1]
            value = self._compare(operator, value, self._unary())
        return value

    @staticmethod
    def _compare(operator: str, left, right):
        if operator == "==":
            return left == right
        if operator == "!=":
            return left != right
        if isinstance(left, (int, float)) or isinstance(right, (int, float)):
            left, right = float(left), float(right)
        return {"<": left < right, "<=": left <= right,
                ">": left > right, ">=": left >= right}[operator]

    def _unary(self):
        if self._peek() == ("op", "!"):
            self._take()
            return not self._unary()
        return self._postfix()

    def _postfix(self):
        value = self._primary()
        while self._peek()[0] == "punct" and self._peek()[1] in (".", "["):
            # The delimiter is captured from the token that was **consumed**, not looked up
            # afterwards. The first version discarded it and then asked whether the *next* token
            # was `[` — which it never is, since `[` is followed by an index and `.` by a name, so
            # the bracket branch was dead and `labels[0].name` raised. PR-Agent's review of #2953
            # found it; `test_bracket_indexing_works` now keeps it honest.
            _, delimiter = self._take()
            if delimiter == "[":
                _, index = self._take()
                self._expect("]")
                if isinstance(value, list):
                    value = value[int(index)]
                elif isinstance(value, dict):
                    value = value.get(index)
                else:
                    value = None
            else:
                _, segment = self._take()
                if segment == "*":
                    # `labels.*.name` — the array splat. `pr-agent-review.yml` reads it on the
                    # `pull_request` branch, so a parser that does not understand it would raise
                    # rather than quietly returning False for every pull request.
                    member = None
                    if self._peek() == ("punct", "."):
                        self._take()
                        _, member = self._take()
                    if isinstance(value, dict):
                        value = list(value.values())
                    if not isinstance(value, list):
                        value = None
                        continue
                    value = [v.get(member) if member and isinstance(v, dict) else v for v in value]
                else:
                    value = value.get(segment) if isinstance(value, dict) else None
        return value

    def _primary(self):
        kind, value = self._take()
        if kind == "punct" and value == "(":
            inner = self._or()
            self._expect(")")
            return inner
        if kind == "str":
            return value[1:-1].replace("''", "'").replace('""', '"')
        if kind == "num":
            return int(value)
        if kind == "name":
            if self._peek() == ("punct", "("):
                self._take()
                arguments = []
                if self._peek() != ("punct", ")"):
                    arguments.append(self._or())
                    while self._peek() == ("punct", ","):
                        self._take()
                        arguments.append(self._or())
                self._expect(")")
                return self._call(value, arguments)
            cursor = self._context
            for part in value.split("."):
                if not isinstance(cursor, dict):
                    return None
                cursor = cursor.get(part)
            return cursor
        raise SyntaxError(f"unexpected token {value!r}")

    def _call(self, name: str, arguments: list):
        if name == "contains":
            haystack, needle = arguments
            if not isinstance(haystack, (str, list)):
                return False        # absent property: empty string, never contains anything
            return needle in haystack
        if name == "startsWith":
            text, prefix = arguments
            return isinstance(text, str) and text.startswith(prefix)
        if name == "endsWith":
            text, suffix = arguments
            return isinstance(text, str) and text.endswith(suffix)
        if name == "fromJSON":
            return json.loads(arguments[0])
        if name in ("always", "success"):
            return True
        raise NameError(f"unsupported function {name}() in this expression")


def evaluate(expression: str, context: dict):
    """Run one workflow `if:` against a context. `context` is a plain `github:` dict."""
    return _Evaluator(expression, context).evaluate()


def workflow_jobs(path: Path) -> dict[str, dict]:
    document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    jobs = document.get("jobs")
    return jobs if isinstance(jobs, dict) else {}


def triggers(path: Path) -> dict:
    document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    # YAML 1.1 parses a bare `on:` as the boolean True, so both spellings have to be tried.
    return document.get("on") or document.get(True) or {}


def write_scopes(path: Path) -> set[str]:
    """The permissions this workflow asks for, workflow level and job level together.

    A job-level `permissions:` **replaces** the workflow-level block rather than merging with it, so
    a workflow that is read-only at the top and write-capable in one job is still privileged. Both
    are collected, and a bare `write-all` counts as everything.
    """
    document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    scopes: set[str] = set()
    for block in [document.get("permissions")] + [job.get("permissions") for job in
                                                 (document.get("jobs") or {}).values()]:
        if isinstance(block, str):                    # `write-all` / `read-all`
            if block == "write-all":
                scopes.add("write-all")
            continue
        if isinstance(block, dict):
            for name, level in block.items():
                if level == "write":
                    scopes.add(name)
    return scopes


# ── The contexts under test ────────────────────────────────────────────────────────────────────────

def comment_context(body: str, association: str) -> dict:
    return {"github": {"event_name": "issue_comment", "head_ref": "",
                       "event": {"comment": {"body": body, "author_association": association}}}}


def pull_request_context(*, draft=False, labels=(), head_ref="fix/dsh-panel",
                         title="fix(dsh): repair the capture panel") -> dict:
    return {"github": {"event_name": "pull_request", "head_ref": head_ref,
                       "event": {"pull_request": {"draft": draft,
                                                  "labels": [{"name": n} for n in labels],
                                                  "title": title}}}}


def pr_agent_review_condition() -> str:
    jobs = workflow_jobs(PR_AGENT_REVIEW)
    assert "pr-agent" in jobs, "the pr-agent job disappeared from pr-agent-review.yml"
    condition = jobs["pr-agent"].get("if")
    assert condition, "the pr-agent job lost its `if:` — every event would run a paid model call"
    return condition.strip()


# ── 1. The gate is in place, and it is on the right branch ─────────────────────────────────────────

def test_the_slash_commands_are_closed_to_unprivileged_commenters():
    """The reported defect: `author_association` appeared 0 times in this file.

    Reproduced rather than asserted by text: evaluate the real `if:` with a `/review` comment from an
    account with no association, which is the cheapest way to spend `OPENAI_KEY` in the repository.
    """
    condition = pr_agent_review_condition()
    for association in ("NONE", "CONTRIBUTOR", "FIRST_TIME_CONTRIBUTOR", "FIRST_TIMER"):
        for command in ("/review", "/describe", "/improve", "/ask"):
            assert evaluate(condition, comment_context(f"{command} please", association)) is False, (
                f"a `{command}` comment from a `{association}` account runs the paid model call and "
                "posts with `pull-requests: write`. Either the job needs a `runs-on`-time "
                f"`github.event.comment.author_association` check, or the command must be documented "
                "as maintainer-only — right now it is neither.")


def test_maintainers_keep_the_commands_they_had():
    """The gate must not be the "switch it off for everyone" fix.

    `contributor-points.json` records outside contributors shipping merged work, and the reason the
    association lists exist at all is to keep a *known* person in; cutting the three roles above
    would have been an equally green way to make the previous test pass.
    """
    condition = pr_agent_review_condition()
    for association in PRIVILEGED:
        for command in ("/review", "/describe", "/improve", "/ask"):
            assert evaluate(condition, comment_context(command, association)) is True, (
                f"a `{command}` comment from a `{association}` account is now refused — the gate is "
                "suppressing the roles it is meant to keep")


def test_the_gate_sits_on_the_comment_branch_and_not_on_the_pull_request_branch():
    """`pull_request` has no `comment.author_association` to read.

    Conjoining the check to the whole expression would either skip every pull request (the `&&`
    binding to the wrong branch) or evaluate against a property that does not exist. Both directions
    are asserted: the five `pull_request` guards still hold, and the comment gate still holds.
    """
    condition = pr_agent_review_condition()
    kept = (
        (pull_request_context(), True, "a normal pull request"),
        (pull_request_context(draft=True), False, "a draft"),
        (pull_request_context(labels=["docs-only"]), False, "a docs-only pull request"),
        (pull_request_context(labels=["bug"]), True, "a pull request with an unrelated label"),
        (pull_request_context(head_ref="bot/leaderboard-watch"), False, "an automation branch"),
        (pull_request_context(title="chore(main): release 2.46.0"), False, "a release pull request"),
    )
    for context, expected, label in kept:
        assert evaluate(condition, context) is expected, (
            f"the association gate changed the `pull_request` branch: {label} now evaluates to "
            f"{evaluate(condition, context)!r}, expected {expected!r}")


def test_a_comment_with_no_command_is_refused_even_for_an_owner():
    """`contains` is a substring test, so the trigger side is loose on purpose — pre-existing, and
    the reason the association gate matters. This pins that it is only the *author* that is checked,
    not the body, so the file is not quietly claiming the commands are exact-matched."""
    condition = pr_agent_review_condition()
    assert evaluate(condition, comment_context("looks good to me", "OWNER")) is False
    # …and the pre-existing substring behaviour, recorded so a future exact-match change is a
    # deliberate act rather than an accident someone reads as a security fix.
    assert evaluate(condition, comment_context("could you /review this?", "OWNER")) is True


# ── 2. The rule generalises, so the next workflow added is caught too ───────────────────────────────

def privileged_comment_workflows(directory: Path) -> list[tuple[Path, bool, set[str]]]:
    """The `(path, spends_a_model, write_scopes)` triples in `directory` the rule applies to.

    Split out from the test so a fixture can be pointed at this rule directly. The first version
    inlined the whole walk, which meant the only way to check the rule fired on a given shape was
    to commit a workflow with that shape — and PR-Agent's review of #2953 found a hole
    (`permissions: write-all`) that a committed fixture would not have surfaced either.
    """
    found = []
    for path in sorted(set(directory.glob("*.yml")) | set(directory.glob("*.yaml"))):
        if "issue_comment" not in triggers(path):
            continue
        document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        spends = any(marker in json.dumps(document) for marker in
                     ("Codium-ai/pr-agent", "OPENAI_KEY", "ANTHROPIC", "@cf/", "AI_GATEWAY"))
        scopes = write_scopes(path)
        # `write_scopes` only ever collects write-granting scopes, and `write-all` is itself one
        # of them. The first version subtracted `{"write-all"}` before this test, which exempted the
        # broadest permission a workflow can ask for — the one case where the gate matters most.
        if not spends and not scopes:
            continue
        found.append((path, spends, scopes))
    return found


def test_every_privileged_issue_comment_workflow_gates_on_association():
    """A workflow that acts on a comment and holds write scope or a model key must check who commented.

    Scoped to both conditions deliberately. An `issue_comment` workflow with no write scope and no
    model call is doing nothing worth stealing, and a rule that flagged it anyway would be the kind
    of rule that gets deleted instead of fixed. Measured on this repository before the fix: four
    workflows trigger on `issue_comment`, all four hold write scope, and `pr-agent-review.yml` was
    the only one of the four without the check.
    """
    privileged: list[str] = []
    for path, spends, scopes in privileged_comment_workflows(WORKFLOWS):
        privileged.append(path.name)
        for name, job in workflow_jobs(path).items():
            condition = str(job.get("if", ""))
            assert ASSOCIATION_CONTEXT in condition, (
                f"{path.name}:{name} acts on an `issue_comment` while holding {sorted(scopes)}"
                f"{' and spending a model call' if spends else ''}, and its `if:` never reads "
                f"`{ASSOCIATION_CONTEXT}`. Any GitHub account can reach it by commenting. Copy the "
                f"gate from `fix-dco.yml:22`.")
    assert "pr-agent-review.yml" in privileged, (
        "the rule stopped seeing the workflow it exists for — the file was renamed or its trigger "
        "changed, and this test would otherwise pass on an empty set")


@pytest.mark.parametrize(
    ("label", "trigger", "permissions", "expected_privileged"),
    [
        ("write-all, no model", "issue_comment", "permissions: write-all\n", True),
        ("read-all, no model", "issue_comment", "permissions: read-all\n", False),
        ("an explicit write scope", "issue_comment", "permissions:\n  contents: write\n", True),
        ("an explicit read scope", "issue_comment", "permissions:\n  contents: read\n", False),
        ("no permissions block at all", "issue_comment", "", False),
        ("write scope, no model, no comment trigger", "push",
         "permissions:\n  contents: write\n", False),
    ],
)
def test_the_rule_covers_the_permission_shapes_that_grant_write(
        tmp_path, label, trigger, permissions, expected_privileged):
    """`permissions: write-all` must be *more* covered, not exempt.

    PR-Agent's review of #2953 found that the first version subtracted `{"write-all"}` before
    deciding a workflow was unprivileged, so the broadest permission a workflow can ask for was the
    one shape the rule skipped.

    `trigger` is a parameter rather than something read out of `label`. The first version inferred
    it from a substring of the label text, so rewording a label silently changed which workflow
    shape was under test — a fixture that stops testing what it says, which is the same failure this
    file exists to rule out, one level up.
    """
    on_block = ("on:\n  issue_comment:\n    types: [created]\n" if trigger == "issue_comment"
                else "on:\n  push:\n    branches: [main]\n")
    path = tmp_path / "probe.yml"
    path.write_text(
        f"name: probe\n{on_block}{permissions}\njobs:\n  j:\n    runs-on: ubuntu-latest\n"
        "    steps:\n      - run: echo hi\n",
        encoding="utf-8")
    found = privileged_comment_workflows(tmp_path)
    assert bool(found) is expected_privileged, (
        f"{label}: the rule {'required' if found else 'skipped'} a gate on this workflow")


# ── 3. The runner must not be held open by a job nobody is waiting on ───────────────────────────────

def test_the_pr_agent_job_has_a_timeout():
    """No `timeout-minutes` means the platform default: six hours of runner time.

    That is the same note `fix-dco.yml:24` and `adopt-pr.yml:37` carry. The model call is minutes,
    so a 15-minute bound loses no legitimate run and stops a hung one from occupying a runner.
    """
    job = workflow_jobs(PR_AGENT_REVIEW)["pr-agent"]
    timeout = job.get("timeout-minutes")
    assert timeout is not None, (
        "the pr-agent job has no `timeout-minutes`, so a hung model call holds its runner for the "
        "six-hour platform default")
    assert 1 <= timeout <= 30, (
        f"timeout-minutes is {timeout}; the call takes minutes, and a bound this loose is the same "
        "as no bound")


# ── 4. The evaluator is checked against two workflows already running in production ─────────────────

@pytest.mark.parametrize(
    ("filename", "job", "association", "expected"),
    [
        ("adopt-pr.yml", "adopt", "OWNER", True),
        ("adopt-pr.yml", "adopt", "MEMBER", True),
        ("adopt-pr.yml", "adopt", "CONTRIBUTOR", False),
        ("adopt-pr.yml", "adopt", "NONE", False),
        ("newbie-welcome.yml", "welcome", "OWNER", False),
        ("newbie-welcome.yml", "welcome", "CONTRIBUTOR", True),
        ("newbie-welcome.yml", "welcome", "NONE", True),
    ],
)
def test_the_evaluator_agrees_with_workflows_already_in_production(filename, job, association, expected):
    """Same `contains(fromJSON(…), author_association)` idiom, opposite polarity.

    If both of these are right, the evaluator handles `!`, `fromJSON` and the `.*.name` splat, and
    the rules above are reading the condition rather than restating it.
    """
    condition = workflow_jobs(WORKFLOWS / filename)[job]["if"].strip()
    if filename == "adopt-pr.yml":
        context = {"github": {"event_name": "issue_comment", "head_ref": "",
                              "event": {"issue": {"pull_request": {"url": "x"}},
                                        "comment": {"body": "/adopt --apply",
                                                    "author_association": association}}}}
    else:
        # newbie-welcome fires on a plain issue, never a pull request.
        context = {"github": {"event_name": "issue_comment", "head_ref": "",
                              "event": {"issue": {"labels": [{"name": "good first issue"}]},
                                        "comment": {"body": "hello",
                                                    "author_association": association}}}}
    assert evaluate(condition, context) is expected


def test_the_evaluator_tells_true_from_false():
    """Without this, a parser bug that made every expression `False` would turn
    `test_the_slash_commands_are_closed_to_unprivileged_commenters` green forever."""
    context = comment_context("/review", "OWNER")
    assert evaluate("github.event_name == 'issue_comment'", context) is True
    assert evaluate("github.event_name == 'pull_request'", context) is False
    assert evaluate("!(github.event_name == 'pull_request')", context) is True
    assert evaluate("contains(fromJSON('[\"A\"]'), 'A')", context) is True
    assert evaluate("startsWith('bot/x', 'bot/')", context) is True
    assert evaluate("contains(github.event.missing, 'anything')", context) is False


def test_unary_not_binds_tighter_than_a_comparison():
    """`!a == b` means `(!a) == b`, so it is *not* the negation of `a == b`.

    Recorded because it is the one precedence rule a reader is likely to get wrong in either
    direction, and because getting it wrong in the parser would silently change which conditions a
    rule believes are satisfied. The workflow itself never relies on it — its `!` sits on a property
    (`!github.event.pull_request.draft`) or on a call (`!contains(...)`), never on a bare comparison.
    """
    context = comment_context("/review", "OWNER")
    assert evaluate("!github.event_name == 'pull_request'", context) is False
    assert evaluate("!(github.event_name == 'pull_request')", context) is True
    assert evaluate("!github.event_name == 'issue_comment'", context) is False


def test_bracket_indexing_works():
    """`labels[0].name` has to resolve. It did not, and nothing noticed.

    The first version of `_postfix` consumed the `.`/`[` delimiter without keeping it and then
    asked whether the *next* token was `[`. It never is — `[` is followed by an index and `.` by a
    name — so the bracket branch was dead code and `labels[0].name` raised `SyntaxError`. PR-Agent's
    review of #2953 found it; nothing in the suite did, because no workflow in the repository uses
    bracket indexing. The same reasoning that hid the three dead guards in
    `test_automated_prs_skip_llm_review.py` applies to a parser nobody exercises.
    """
    context = pull_request_context(labels=["docs-only", "bug"])
    assert evaluate("contains(github.event.pull_request.labels[0].name, 'docs-only')", context) is True
    assert evaluate("contains(github.event.pull_request.labels[1].name, 'docs-only')", context) is False
    assert evaluate("contains(github.event.pull_request.labels[1].name, 'bug')", context) is True
    # The splat over the same list has to keep working; it is what `pr-agent-review.yml` uses.
    assert evaluate("contains(github.event.pull_request.labels.*.name, 'docs-only')", context) is True
    assert evaluate("contains(github.event.pull_request.labels.*.name, 'nope')", context) is False
