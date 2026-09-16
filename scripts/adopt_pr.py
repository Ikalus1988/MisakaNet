#!/usr/bin/env python3
"""Adopt a fork PR that is blocked on DCO only (GitHub issue #1778).

Why this exists
---------------
``.github/workflows/fix-dco.yml`` can rebase a *same-repo* PR with ``--signoff`` and
force-push it, but it cannot touch a fork PR: the default ``GITHUB_TOKEN`` has no write
access to the contributor's fork, so that workflow stops at a step literally named
"Handle fork PR — manual instructions only". Six PRs were stalled purely on a missing
``Signed-off-by:`` trailer while their content was fine.

``/adopt`` is the maintainer-side short path that needs **no new secret**. The fork's
commits are fetched into a maintainer-owned branch (``adopted/<n>``), rebased with
``--signoff``, and landed through a *new* PR that credits the original author with a
``Co-authored-by:`` trailer. The fork is never written to, ``main`` is never force-pushed,
and the only change the adopter makes to the code is the DCO trailer itself.

Two phases (this is what ``.github/workflows/adopt-pr.yml`` runs)
-----------------------------------------------------------------
Phase 1 — ``/adopt`` — dry run, prints an ordered plan, performs **no writes and no
network** (it only reads the local refs it is told about, or the commit list handed to it)::

    python3 scripts/adopt_pr.py 1656 \\
        --head-repo https://github.com/TaherEzzi/MisakaNet.git \\
        --head-branch fix-issue-1652 --head-sha 3bbc508dff820335552c1889240cd072f4114f0b \\
        --commits-file /tmp/adopt-1656-commits.json \\
        --author 'Taher Ezzi <taherezzi.dev@gmail.com>' --author-login TaherEzzi \\
        --title 'fix: resolve #1652 - ...' --body-file /tmp/adopt-1656-body.md \\
        --comment-out /tmp/adopt-comment.md

Phase 2 — ``/adopt --apply`` — executes the plan (fetch → rebase --signoff → push
``adopted/<n>``) and writes the new PR body for ``gh pr create``::

    python3 scripts/adopt_pr.py 1656 --apply ... \\
        --body-out /tmp/adopt-body.md --comment-out /tmp/adopt-notice.md

The new PR body goes to ``--body-out``. ``--comment-out`` receives the markdown for the
*original* PR: the dry-run plan, the refusal, or — in ``--apply`` mode — a notice carrying
the literal placeholder ``{{NEW_PR_URL}}`` that the workflow substitutes after
``gh pr create``. ``--json`` prints the plan (or the refusal) as JSON on stdout.

Exit codes
----------
* ``0`` — plan printed (dry run) or adoption applied
* ``1`` — runtime failure: rebase conflict, rejected push, moved fork, missing git
* ``2`` — refused precondition, with a one-line reason on stderr (see :class:`Refusal`)

Only the Python standard library plus the ``git`` binary is used.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_REFUSED = 2

DEFAULT_REPO = os.environ.get("GITHUB_REPOSITORY", "Ikalus1988/MisakaNet")
DEFAULT_BASE = "main"
DEFAULT_SIGNOFF_NAME = "misakanet-bot"
DEFAULT_SIGNOFF_EMAIL = "bot@misakanet.dev"

# A DCO trailer is only valid with a real identity in angle brackets: the same shape the DCO
# checker greps for, but strict enough to reject prose that merely mentions the word.
SIGNOFF_RE = re.compile(
    r"^[ \t]*Signed-off-by:[ \t]*[^<\n]+<[^<>\n]+>[ \t]*$", re.IGNORECASE | re.MULTILINE
)

# `adopted/<n>` only. Guarded so no argument combination can make the script push anywhere
# else — in particular never to `main` and never to a fork.
TARGET_BRANCH_RE = re.compile(r"^adopted/[1-9][0-9]*$")

COMMIT_SEP = "\x1e"
FIELD_SEP = "\x1f"
LOG_FORMAT = f"%H{FIELD_SEP}%an{FIELD_SEP}%ae{FIELD_SEP}%B{COMMIT_SEP}"


class Refusal(Exception):
    """A precondition is not met: nothing was executed, exit code 2."""


class Failure(Exception):
    """A runtime step went wrong (conflict, rejected push, moved fork): exit code 1."""


# --------------------------------------------------------------------------------------
# git plumbing
# --------------------------------------------------------------------------------------


def git(
    *args: str,
    cwd: str | Path | None = None,
    check: bool = True,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    """Run one git command, capturing its output as text."""
    run_env = {**os.environ, **env} if env else None
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=run_env,
        )
    except FileNotFoundError as exc:  # pragma: no cover - git is a hard requirement
        raise Failure("the git executable was not found on PATH") from exc
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise Failure(f"git {' '.join(args)} failed (rc={result.returncode}): {detail}")
    return result


def git_out(*args: str, cwd: str | Path | None = None, check: bool = True) -> str:
    return git(*args, cwd=cwd, check=check).stdout.strip()


def rev_parse(rev: str, cwd: str | Path) -> str | None:
    """Resolve ``rev`` to a commit SHA in ``cwd``, or ``None`` when it is unknown there."""
    result = git("rev-parse", "--verify", "--quiet", f"{rev}^{{commit}}", cwd=cwd, check=False)
    return result.stdout.strip() or None


def is_git_checkout(path: str | Path) -> bool:
    return git("rev-parse", "--git-dir", cwd=path, check=False).returncode == 0


def first_existing_ref(candidates, cwd: str | Path) -> str | None:
    for candidate in candidates:
        if rev_parse(candidate, cwd):
            return candidate
    return None


def read_commits(cwd: str | Path, rng: str) -> list["Commit"]:
    """Read non-merge commits from ``rng`` (e.g. ``main..HEAD``) in a local checkout.

    ``--no-merges`` mirrors ``dco-check.yml``: merge commits are exempt from DCO.
    """
    out = git("log", f"--format={LOG_FORMAT}", "--no-merges", rng, cwd=cwd, check=False).stdout
    commits: list[Commit] = []
    for record in out.split(COMMIT_SEP):
        record = record.strip("\n")
        if not record.strip():
            continue
        parts = record.split(FIELD_SEP, 3)
        if len(parts) < 4:
            continue
        sha, name, email, message = parts
        commits.append(
            Commit(sha=sha.strip(), message=message, author_name=name.strip(), author_email=email.strip())
        )
    return commits


# --------------------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------------------


def slugify_repo(value: str | None) -> str:
    """Normalise a GitHub clone URL / ``owner/name`` / local path for comparison.

    Local paths stay paths, so a throwaway fork directory (as used by the tests) never
    compares equal to the base repository slug — it is correctly read as "a fork".
    """
    return display_repo(value).lower()


def display_repo(value: str | None) -> str:
    """The ``owner/name`` (or path) of a clone URL, with its original capitalisation."""
    if not value:
        return ""
    raw = value.strip()
    for pattern in (
        r"^https?://(?:[^@/]+@)?github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$",
        r"^ssh://git@github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$",
        r"^git@github\.com:([^/]+)/([^/]+?)(?:\.git)?$",
    ):
        match = re.match(pattern, raw, re.IGNORECASE)
        if match:
            return f"{match.group(1)}/{match.group(2)}"
    return raw


def has_signoff(message: str) -> bool:
    return bool(SIGNOFF_RE.search(message or ""))


def fence_for(text: str) -> str:
    """A code fence longer than any run of backticks inside ``text``.

    The plan embeds the original PR body verbatim, so a body that itself contains a fenced
    block must not be able to break out of the comment we post.
    """
    longest = max((len(run) for run in re.findall(r"`+", text)), default=0)
    return "`" * max(4, longest + 1)


def parse_author(value: str | None) -> tuple[str, str]:
    """Split ``Name <email>``; a bare value is treated as the name alone."""
    if not value:
        return "", ""
    match = re.match(r"^\s*(.*?)\s*<([^<>]+)>\s*$", value)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return value.strip(), ""


@dataclass
class Commit:
    sha: str
    message: str
    author_name: str = ""
    author_email: str = ""

    @property
    def signed_off(self) -> bool:
        return has_signoff(self.message)

    @property
    def subject(self) -> str:
        stripped = (self.message or "").strip()
        return stripped.splitlines()[0] if stripped else ""

    def identity(self) -> tuple[str, str]:
        return (self.author_name, self.author_email)


def commits_from_json(raw: str) -> list[Commit]:
    """Parse ``[{"sha","message","author":{"name","email"}}]`` or ``["message", ...]``."""
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise Failure(f"--commits-file/--commits-json is not valid JSON: {exc}") from exc
    if isinstance(payload, dict) and "commits" in payload:
        payload = payload["commits"]
    if not isinstance(payload, list):
        raise Failure("--commits-file/--commits-json must be a JSON array of commits")
    commits: list[Commit] = []
    for entry in payload:
        if isinstance(entry, str):
            commits.append(Commit(sha="", message=entry))
            continue
        if not isinstance(entry, dict):
            raise Failure("every entry of the commit list must be an object or a string")
        block = entry.get("commit") if isinstance(entry.get("commit"), dict) else entry
        author = block.get("author") if isinstance(block.get("author"), dict) else {}
        commits.append(
            Commit(
                sha=str(entry.get("sha") or block.get("sha") or ""),
                message=str(block.get("message") or entry.get("message") or ""),
                author_name=str(author.get("name") or entry.get("author_name") or ""),
                author_email=str(author.get("email") or entry.get("author_email") or ""),
            )
        )
    return commits


# --------------------------------------------------------------------------------------
# the plan
# --------------------------------------------------------------------------------------


@dataclass
class Plan:
    pr: int
    repo: str
    base: str
    workdir: str
    head_repo: str | None
    head_repo_slug: str
    head_repo_display: str
    is_fork: bool | None
    head_branch: str | None
    head_sha: str | None
    head_label: str | None
    author_name: str = ""
    author_email: str = ""
    author_login: str | None = None
    co_authors: list[tuple[str, str]] = field(default_factory=list)
    title: str = ""
    original_body: str = ""
    commits: list[Commit] = field(default_factory=list)
    signoff_state_known: bool = True
    signoff_name: str = DEFAULT_SIGNOFF_NAME
    signoff_email: str = DEFAULT_SIGNOFF_EMAIL
    adopter: str | None = None
    base_ref: str | None = None
    base_tip: str | None = None
    fetch_ref: str = ""
    target_branch: str = ""
    warnings: list[str] = field(default_factory=list)

    # -- derived ---------------------------------------------------------------------
    def __post_init__(self) -> None:
        if not self.fetch_ref:
            self.fetch_ref = f"refs/remotes/adopt/{self.pr}-head"
        if not self.target_branch:
            self.target_branch = f"adopted/{self.pr}"

    @property
    def original_url(self) -> str:
        return f"https://github.com/{self.repo}/pull/{self.pr}"

    @property
    def unsigned(self) -> list[Commit]:
        return [c for c in self.commits if not c.signed_off]

    @property
    def fetch_argv(self) -> list[str]:
        if self.head_repo and self.head_branch:
            return [
                "fetch",
                "--no-tags",
                self.head_repo,
                f"+refs/heads/{self.head_branch}:{self.fetch_ref}",
            ]
        if self.head_repo and self.head_sha:
            return ["fetch", "--no-tags", self.head_repo, self.head_sha]
        return ["fetch", "--no-tags", "origin", f"refs/pull/{self.pr}/head"]

    @property
    def fetch_fallback_argv(self) -> list[str]:
        # GitHub exposes refs/pull/<n>/head on the *base* repo for fork PRs too, so this
        # works even when the fork was deleted or made private.
        return ["fetch", "--no-tags", "origin", f"refs/pull/{self.pr}/head"]

    @property
    def rebase_argv(self) -> list[str]:
        return [
            "-c",
            f"user.name={self.signoff_name}",
            "-c",
            f"user.email={self.signoff_email}",
            "rebase",
            "--signoff",
            self.rebase_ref,
        ]

    @property
    def push_argv(self) -> list[str]:
        return ["push", "origin", f"HEAD:refs/heads/{self.target_branch}"]

    @property
    def rebase_ref(self) -> str:
        return self.base_ref or self.base

    @staticmethod
    def _cmd(argv: list[str]) -> str:
        return "git " + " ".join(shlex.quote(a) for a in argv)

    @property
    def fetch_command(self) -> str:
        return self._cmd(self.fetch_argv)

    @property
    def fetch_fallback(self) -> str:
        return self._cmd(self.fetch_fallback_argv)

    @property
    def rebase_command(self) -> str:
        return self._cmd(self.rebase_argv)

    @property
    def push_command(self) -> str:
        return self._cmd(self.push_argv)

    @property
    def pr_create_command(self) -> str:
        title = self.title or f"(title of PR #{self.pr})"
        return (
            f"gh pr create --base {self.base} --head {self.target_branch} "
            f"--title {shlex.quote(title)} --body-file <new PR body>"
        )

    # -- credit / body ---------------------------------------------------------------
    def co_author_pairs(self) -> list[tuple[str, str]]:
        """The `Co-authored-by` trailers: the original author first, plus any --co-author.

        ``--author`` wins when it is given (it comes from the PR payload), otherwise the
        first commit's git author is used. Every pair keeps a real e-mail: the trailer is
        what GitHub uses to attribute the squash commit.
        """
        primary = (
            self.author_name or self.author_login or "unknown",
            self.author_email or "unknown@users.noreply.github.com",
        )
        pairs = [primary]
        for pair in self.co_authors:
            if pair[1] and pair not in pairs:
                pairs.append(pair)
        return pairs

    def build_pr_body(self) -> str:
        login = f"@{self.author_login}" if self.author_login else (self.author_name or "the author")
        head_line = self.head_label or ":".join(
            x for x in (self.head_repo_display or self.head_repo_slug, self.head_branch) if x
        )
        commit_line = f"{len(self.commits)} commit(s)"
        if self.signoff_state_known and self.commits:
            commit_line += (
                f", {len(self.unsigned)} missing `Signed-off-by:`"
                if self.unsigned
                else ", all already signed off"
            )
        lines = [
            f"## Adopted from #{self.pr}",
            "",
            f"This PR is a maintainer-side adoption of #{self.pr} by {login}: its commits were "
            "missing the DCO `Signed-off-by:` trailer, and the bot cannot push to a fork, so the "
            "original PR could not be fixed in place.",
            "",
            "**The only change made by the adopter is the `Signed-off-by:` trailer on each "
            "commit.** The tree is the contributor's work verbatim — a plain "
            f"`git rebase --signoff {self.base}` of the fork head, with no content edits and no "
            "conflict resolution.",
            "",
            f"- Original PR: {self.original_url}",
            f"- Original head: `{head_line}` @ `{(self.head_sha or 'unknown')[:12]}` ({commit_line})",
            f"- Target branch: `{self.target_branch}` (same repository; the fork was never written to)",
            "",
            f"## Original PR description (#{self.pr}, verbatim)",
            "",
            self.original_body.strip() or "_(the original PR had no description)_",
            "",
            "---",
            "",
            "## Credit",
            "",
            f"The rebased commits keep {self.author_name or login} as their git author. If this PR "
            "is squash-merged, keep the trailer below in the squash commit message: GitHub sets the "
            "squash commit's author to the PR author (the adopter), so this line is what keeps the "
            "contribution attributed to the original author (precedent: #1756).",
            "",
        ]
        for name, email in self.co_author_pairs():
            lines.append(f"Co-authored-by: {name} <{email}>")
        lines += [
            "",
            "_Adopted via `/adopt --apply` (`scripts/adopt_pr.py`, issue #1778) by "
            f"{('@' + self.adopter) if self.adopter else 'a maintainer'}; the original PR is closed "
            "in favour of this one._",
            "",
        ]
        return "\n".join(lines)

    # -- rendering -------------------------------------------------------------------
    def preflight_lines(self) -> list[str]:
        checks: list[tuple[str, str]] = []
        if self.is_fork is None:
            checks.append(("head repo not supplied", "fork-ness unverified"))
        elif self.is_fork:
            checks.append(
                (f"head repo is a fork ({self.head_repo_display} != {self.repo})", "ok")
            )
        else:
            checks.append((f"head repo is {self.head_repo_display} == {self.repo}", "NOT a fork"))
        checks.append((f"working tree clean ({self.workdir})", "ok"))
        checks.append(
            (f"target branch {self.target_branch} absent locally (remote re-checked on apply)", "ok")
        )
        if not self.signoff_state_known:
            checks.append(("commit sign-off state", "unknown offline — re-checked after the fetch"))
        elif not self.commits:
            checks.append(("commits on the PR", "none found"))
        elif self.unsigned:
            checks.append(
                (f"{len(self.unsigned)}/{len(self.commits)} commit(s) need Signed-off-by", "ok to adopt")
            )
        else:
            checks.append(("every commit already carries Signed-off-by", "nothing to adopt"))
        return [f"      - {label:<70} [{state}]" for label, state in checks]

    def render(self) -> str:
        title = self.title or f"(title of PR #{self.pr}, unchanged)"
        head_line = self.head_label or self.head_branch or "(unknown)"
        sha_line = f" @ {self.head_sha}" if self.head_sha else ""
        out: list[str] = []
        out.append("=" * 88)
        out.append(f" /adopt plan for PR #{self.pr} — DRY RUN (no writes, no network)")
        out.append("=" * 88)
        out.append("")
        out.append(f"Original PR : #{self.pr} — {title}")
        out.append(
            f"Fork        : {self.head_repo_display or '(unknown)'}  {self.head_repo or ''}".rstrip()
        )
        out.append(f"Head        : {head_line}{sha_line}")
        out.append(
            f"Base        : {self.rebase_ref}"
            + (f" @ {self.base_tip[:12]}" if self.base_tip else " (tip unresolved in this checkout)")
        )
        out.append(f"Author      : {self.author_name} <{self.author_email}>   (Co-authored-by credit)")
        for name, email in self.co_authors:
            out.append(f"Co-author   : {name} <{email}>")
        if self.commits:
            out.append(
                f"Commits     : {len(self.commits)} to replay, {len(self.unsigned)} missing Signed-off-by"
            )
        else:
            out.append("Commits     : unknown offline (re-checked after the fetch)")
        out.append(f"Sign-off as : {self.signoff_name} <{self.signoff_email}>")
        out.append(f"Target      : {self.target_branch}  (same repo; never main, never the fork)")
        out.append("")
        out.append("PREFLIGHT")
        out.extend(self.preflight_lines())
        for warning in self.warnings:
            out.append(f"      ! WARNING: {warning}")
        out.append("")
        out.append("ORDERED PLAN")
        out.append(f"  1. {self.fetch_command}")
        out.append("       read-only: /adopt fetches the fork and never pushes to it")
        out.append(f"       fallback if the fork is gone or private: {self.fetch_fallback}")
        if self.head_sha:
            out.append(f"       verify the fetched commit is {self.head_sha} — a moved fork aborts")
        out.append(f"  2. git checkout -b {self.target_branch} FETCH_HEAD")
        out.append("       (the commit fetched in step 1; the branch is created from it, untouched)")
        out.append(f"  3. {self.rebase_command}")
        out.append(
            f"       adds Signed-off-by: {self.signoff_name} <{self.signoff_email}> to "
            + (f"{len(self.unsigned)} commit(s)" if self.signoff_state_known and self.commits
               else "every commit that lacks it")
        )
        out.append("       a conflict aborts the run with a report — never a silent skip")
        out.append("       commits that become empty are counted and reported, not swallowed")
        out.append(f"  4. {self.push_command}   (a plain push — never forced)")
        out.append(f"  5. {self.pr_create_command}")
        out.append(
            f"  6. gh pr comment {self.pr} --body-file <notice>  ;  "
            f"gh pr close {self.pr} --delete-branch=false"
        )
        out.append("")
        out.append("NEW PR TITLE (unchanged from the original PR)")
        out.append(f"  {title}")
        out.append("")
        out.append("NEW PR BODY")
        out.append("---8<---")
        out.append(self.build_pr_body().rstrip("\n"))
        out.append("---8<---")
        out.append("")
        out.append(
            "Nothing above was executed: re-run with --apply to perform steps 1-6. The fork is "
            "never written to and main is never touched."
        )
        return "\n".join(out)

    def render_comment(self) -> str:
        title = self.title or f"PR #{self.pr}"
        plan = self.render().rstrip("\n")
        fence = fence_for(plan)
        return "\n".join(
            [
                f"### 🔎 `/adopt` dry run — PR #{self.pr}",
                "",
                f"Plan for adopting **{title}** through a same-repo branch. **Nothing was executed "
                "and nothing was written.**",
                "",
                f"{fence}text",
                plan,
                fence,
                "",
                "---",
                "",
                "To execute it, a maintainer (MEMBER / OWNER / COLLABORATOR) comments "
                f"`/adopt --apply` on this PR. The fork (`{self.head_repo_display or 'unknown'}`) is "
                "never written to, `main` is never force-pushed, and the only change this bot makes "
                "is the `Signed-off-by:` trailer: the original author stays the author of the "
                "commits and is credited with a `Co-authored-by:` line in the new PR.",
                "",
            ]
        )

    def to_dict(self) -> dict:
        return {
            "ok": True,
            "mode": "plan",
            "pr": self.pr,
            "repo": self.repo,
            "original_pr_url": self.original_url,
            "is_fork": self.is_fork,
            "head_repo": self.head_repo,
            "head_repo_slug": self.head_repo_slug,
            "head_repo_display": self.head_repo_display,
            "head_branch": self.head_branch,
            "head_sha": self.head_sha,
            "head_label": self.head_label,
            "base": self.base,
            "base_ref": self.base_ref,
            "base_tip": self.base_tip,
            "workdir": self.workdir,
            "author": f"{self.author_name} <{self.author_email}>",
            "author_login": self.author_login,
            "adopter": self.adopter,
            "co_authored_by": [f"{n} <{e}>" for n, e in self.co_author_pairs()],
            "target_branch": self.target_branch,
            "title": self.title,
            "signoff_name": self.signoff_name,
            "signoff_email": self.signoff_email,
            "fetch_command": self.fetch_command,
            "fetch_fallback": self.fetch_fallback,
            "rebase_command": self.rebase_command,
            "push_command": self.push_command,
            "pr_create_command": self.pr_create_command,
            "commits": [
                {
                    "sha": c.sha,
                    "subject": c.subject,
                    "signed_off": c.signed_off,
                    "author": f"{c.author_name} <{c.author_email}>" if c.author_name else "",
                }
                for c in self.commits
            ],
            "commit_count": len(self.commits),
            "unsigned_count": len(self.unsigned),
            "signoff_state_known": self.signoff_state_known,
            "steps": [
                self.fetch_command,
                self.fetch_fallback,
                f"git checkout -b {self.target_branch} FETCH_HEAD",
                self.rebase_command,
                self.push_command,
                self.pr_create_command,
                f"gh pr comment {self.pr} --body-file <notice>",
                f"gh pr close {self.pr} --delete-branch=false",
            ],
            "pr_body": self.build_pr_body(),
            "warnings": list(self.warnings),
        }


def refusal_payload(pr: int, reason: str) -> dict:
    return {"ok": False, "refused": True, "mode": "refused", "pr": pr, "reason": reason}


def render_refusal_comment(pr: int, reason: str) -> str:
    return "\n".join(
        [
            f"### ⛔ `/adopt` refused — PR #{pr}",
            "",
            reason,
            "",
            "Nothing was created, nothing was pushed, and the original PR is untouched.",
            "",
        ]
    )


def render_adopted_notice(plan: Plan) -> str:
    """Comment posted on the *original* PR once the adoption has been pushed."""
    count = len(plan.commits) or "the"
    return "\n".join(
        [
            "### ✅ Adopted — superseded by a new PR",
            "",
            f"A maintainer ran `/adopt --apply`: {count} commit(s) were fetched from "
            f"`{plan.head_repo_display or plan.head_repo_slug or 'the fork'}`, rebased onto "
            f"`{plan.base}` with `--signoff`, and "
            f"pushed unchanged to the same-repo branch `{plan.target_branch}`.",
            "",
            "New PR: {{NEW_PR_URL}}",
            "",
            f"**Credit:** the rebased commits keep {plan.author_name or 'the original author'} as their "
            "git author, and the new PR carries a `Co-authored-by:` trailer for them. The only change "
            "made by the adopter is the `Signed-off-by:` trailer — no code was edited and no conflict "
            "was resolved.",
            "",
            "This PR is closed in favour of the new one. The branch is kept and **nothing was ever "
            "written to your fork**.",
            "",
            f"_Original head: `{plan.head_label or ''}` @ `{(plan.head_sha or '')[:12]}` · "
            "`scripts/adopt_pr.py` · issue #1778_",
            "",
        ]
    )


# --------------------------------------------------------------------------------------
# preconditions
# --------------------------------------------------------------------------------------


def working_tree_dirty(workdir: str | Path) -> bool:
    result = git("status", "--porcelain", cwd=workdir, check=False)
    if result.returncode != 0:
        raise Failure(f"{workdir} is not a checkout this script can use: {(result.stderr or '').strip()}")
    return bool(result.stdout.strip())


def target_branch_exists(target: str, workdir: str | Path) -> bool:
    return any(
        rev_parse(ref, workdir) for ref in (f"refs/heads/{target}", f"refs/remotes/origin/{target}")
    )


def resolve_base(plan: Plan) -> None:
    """Resolve the base branch tip in the working checkout (read-only)."""
    ref = first_existing_ref(
        [f"refs/remotes/origin/{plan.base}", f"refs/heads/{plan.base}", plan.base], plan.workdir
    )
    plan.base_ref = ref
    plan.base_tip = rev_parse(ref, plan.workdir) if ref else None


def build_plan(args: argparse.Namespace, pr: int) -> Plan:
    workdir = str(Path(args.workdir).resolve())
    if not is_git_checkout(workdir):
        raise Failure(f"--workdir {workdir} is not a git checkout")

    head_ref_value = args.head_repo_full_name or args.head_repo
    head_display = display_repo(head_ref_value)
    head_slug = head_display.lower()
    is_fork: bool | None = None if not head_slug else head_slug != slugify_repo(args.repo)

    author_name, author_email = parse_author(args.author)
    commits: list[Commit] = []
    signoff_known = False
    warnings: list[str] = []
    if args.commits_file or args.commits_json:
        raw = args.commits_json
        if args.commits_file:
            raw = (
                sys.stdin.read()
                if args.commits_file == "-"
                else Path(args.commits_file).read_text(encoding="utf-8")
            )
        commits = commits_from_json(raw)
        signoff_known = True
    elif args.head_repo and Path(args.head_repo).exists():
        rev = args.head_sha or args.head_branch or "HEAD"
        if not rev_parse(rev, args.head_repo):
            raise Failure(f"--head-repo {args.head_repo} has no commit {rev!r}")
        base = first_existing_ref(
            [f"refs/heads/{args.base}", args.base, f"refs/remotes/origin/{args.base}"], args.head_repo
        )
        commits = read_commits(args.head_repo, f"{base}..{rev}" if base else rev)
        signoff_known = True
    else:
        warnings.append(
            "no commit list supplied (--commits-file/--commits-json) and --head-repo is not a local "
            "path: the sign-off state is re-checked after the fetch instead"
        )
    if not author_name and commits:
        author_name, author_email = commits[0].identity()
    if not author_email and args.author_login:
        author_email = f"{args.author_login}@users.noreply.github.com"

    co_authors: list[tuple[str, str]] = [
        pair for pair in (parse_author(value) for value in args.co_author or []) if pair[1]
    ]
    distinct: list[tuple[str, str]] = []
    for commit in commits:
        pair = commit.identity()
        if pair[1] and pair not in distinct:
            distinct.append(pair)
    if len(distinct) > 1:
        extras = [f"{n} <{e}>" for n, e in distinct if (n, e) != (author_name, author_email)]
        if extras and not co_authors:
            warnings.append(
                "the PR's commits were authored by more than one identity ("
                + ", ".join(extras)
                + "); only --author is credited as Co-authored-by — pass --co-author for the others"
            )

    title = args.title or ""
    original_body = ""
    if args.body_file:
        original_body = Path(args.body_file).read_text(encoding="utf-8")
    elif args.body:
        original_body = args.body
    if not title or (args.body_file is None and args.body is None):
        warnings.append(
            "no --title/--body given: the new PR body cannot embed the original description "
            "verbatim, so pass them from the GitHub API payload (the workflow does)"
        )

    if args.signoff_name or args.signoff_email:
        signoff_name = args.signoff_name or DEFAULT_SIGNOFF_NAME
        signoff_email = args.signoff_email or DEFAULT_SIGNOFF_EMAIL
    elif args.adopter:
        signoff_name = args.adopter
        signoff_email = f"{args.adopter}@users.noreply.github.com"
    else:
        signoff_name, signoff_email = DEFAULT_SIGNOFF_NAME, DEFAULT_SIGNOFF_EMAIL

    plan = Plan(
        pr=pr,
        repo=args.repo,
        base=args.base,
        workdir=workdir,
        head_repo=args.head_repo,
        head_repo_slug=head_slug,
        head_repo_display=head_display,
        is_fork=is_fork,
        head_branch=args.head_branch,
        head_sha=args.head_sha,
        head_label=args.head_label,
        author_name=author_name,
        author_email=author_email,
        author_login=args.author_login,
        co_authors=co_authors,
        title=title,
        original_body=original_body,
        commits=commits,
        signoff_state_known=signoff_known,
        signoff_name=signoff_name,
        signoff_email=signoff_email,
        adopter=args.adopter,
        warnings=warnings,
    )
    if not TARGET_BRANCH_RE.match(plan.target_branch):  # pragma: no cover - defensive
        raise Failure(f"refusing to use target branch {plan.target_branch!r}")
    resolve_base(plan)
    return plan


def preflight(plan: Plan, apply: bool) -> None:
    """Raise :class:`Refusal` (exit 2) when the adoption must not start."""
    if plan.is_fork is None and apply:
        raise Refusal(
            "cannot verify that this PR comes from a fork: pass --head-repo (the fork's clone URL) "
            "or --head-repo-full-name. Adoption only exists for fork PRs — a same-repo PR should use "
            "/fix-dco (.github/workflows/fix-dco.yml), which can push to its own branch."
        )
    if plan.is_fork is False:
        raise Refusal(
            f"PR #{plan.pr} is not from a fork: its head repo {plan.head_repo_display} is this very "
            "repository. Use the same-repo DCO auto-fix instead — comment `/fix-dco` (see "
            ".github/workflows/fix-dco.yml)."
        )
    if working_tree_dirty(plan.workdir):
        raise Refusal(
            f"the working tree at {plan.workdir} is dirty. /adopt needs a clean checkout so the "
            "rebase cannot pick up unrelated local changes: commit, stash or discard them, then re-run."
        )
    if target_branch_exists(plan.target_branch, plan.workdir):
        raise Refusal(
            f"the target branch {plan.target_branch} already exists, so an adoption for PR "
            f"#{plan.pr} is probably already in flight. Review or land it first — or abandon it with "
            f"`git push origin --delete {plan.target_branch}` — and re-run."
        )
    if plan.signoff_state_known:
        if not plan.commits:
            raise Refusal(
                f"no commits were found for PR #{plan.pr} (empty head branch, or already merged) — "
                "there is nothing to adopt."
            )
        if not plan.unsigned:
            raise Refusal(
                f"every commit of PR #{plan.pr} already carries a valid `Signed-off-by:` trailer, so "
                "there is nothing to adopt: the PR satisfies the DCO gate on its own. Re-run the DCO "
                "check if CI still disagrees."
            )
    if apply and not (plan.author_email or plan.author_login):
        raise Refusal(
            "cannot build the `Co-authored-by:` trailer without an e-mail: pass --author "
            "'Name <email>' or --author-login <login> (which yields <login>@users.noreply.github.com)."
        )


# --------------------------------------------------------------------------------------
# apply
# --------------------------------------------------------------------------------------


def verify_signed_off(plan: Plan, cwd: str | Path, rng: str) -> list[Commit]:
    commits = read_commits(cwd, rng)
    unsigned = [c for c in commits if not c.signed_off]
    if unsigned:
        listing = ", ".join(c.sha[:12] for c in unsigned)
        raise Failure(
            f"{len(unsigned)} commit(s) still lack a `Signed-off-by:` trailer after the rebase "
            f"({listing}) — refusing to push. Inspect the branch and re-run."
        )
    return commits


def check_authors_preserved(before: list[Commit], after: list[Commit], branch: str) -> bool:
    """The contributor must stay the author: only the trailer may change.

    Compares the *sets* of git-author identities, so commits the rebase legitimately dropped
    (they became empty) do not look like a rewrite. An identity that was not there before is
    a real problem and is reported loudly.
    """
    known = {c.identity() for c in before if c.author_email}
    unexpected = {c.identity() for c in after if c.author_email and c.identity() not in known}
    if unexpected:
        listing = ", ".join(f"{n} <{e}>" for n, e in sorted(unexpected))
        print(
            f"      NOTICE: the rebased commits contain an author identity that was not on the "
            f"fork head ({listing}). Attribution changed — inspect `git log` on {branch} before "
            "opening the PR."
        )
        return False
    return True


def assert_push_target_is_not_the_fork(plan: Plan, cwd: str | Path) -> str:
    """The only remote /adopt ever pushes to is ``origin``, and ``origin`` must not be the fork.

    The fork is fetched anonymously and read-only; a checkout whose ``origin`` *is* the fork
    (or which has no ``origin`` at all) would push the adopted branch into the contributor's
    repository, so this refuses before anything is written anywhere.
    """
    url = git_out("remote", "get-url", "origin", cwd=cwd, check=False)
    if not url:
        raise Failure(
            "the checkout has no 'origin' remote. /adopt pushes adopted/<n> to the *base* "
            "repository, so origin must point at it (actions/checkout sets that up)."
        )
    if plan.head_repo and slugify_repo(url) == slugify_repo(plan.head_repo):
        raise Failure(
            f"'origin' points at the contributor's fork ({plan.head_repo_display or url}); refusing "
            "to run. The fork is read-only for /adopt — origin must be the base repository."
        )
    return display_repo(url)


def apply_plan(plan: Plan) -> dict:
    workdir = plan.workdir
    # Used only to put the checkout back where it was if the rebase conflicts; a detached or
    # unborn HEAD is fine, so this never fails the run.
    original_ref = (
        git_out("rev-parse", "--abbrev-ref", "HEAD", cwd=workdir, check=False)
        or git_out("rev-parse", "HEAD", cwd=workdir, check=False)
        or plan.rebase_ref
    )

    push_target = assert_push_target_is_not_the_fork(plan, workdir)
    print(f"[1/6] Push target origin = {push_target} (the fork is fetched read-only) ...")
    ls_remote = git("ls-remote", "--heads", "origin", plan.target_branch, cwd=workdir, check=False)
    if ls_remote.returncode != 0:
        raise Failure(f"git ls-remote origin failed: {(ls_remote.stderr or '').strip()}")
    if ls_remote.stdout.strip():
        raise Refusal(
            f"the target branch {plan.target_branch} already exists on origin. Abandon or land the "
            f"existing adoption first (`git push origin --delete {plan.target_branch}`), then re-run."
        )

    print(f"[2/6] Fetching the fork (read-only, anonymous): {plan.fetch_command}")
    fetched = git(*plan.fetch_argv, cwd=workdir, check=False)
    if fetched.returncode != 0:
        first_line = next(iter((fetched.stderr or "").strip().splitlines()), "")
        print(f"      fork fetch failed ({first_line}) — falling back to {plan.fetch_fallback}")
        fallback = git(*plan.fetch_fallback_argv, cwd=workdir, check=False)
        if fallback.returncode != 0:
            raise Failure(
                f"could not fetch PR #{plan.pr} from the fork nor from origin: "
                f"{(fallback.stderr or '').strip()}"
            )
    # FETCH_HEAD can list several entries when a refspec pulls more than one ref: the PR head
    # is always the first line here (one ref is fetched either way).
    fetched_sha = git_out("rev-parse", "FETCH_HEAD", cwd=workdir).splitlines()[0].strip()
    if plan.head_sha and fetched_sha != plan.head_sha:
        raise Failure(
            f"the fork moved: fetched {fetched_sha[:12]} but the PR head is {plan.head_sha[:12]} — "
            "re-run `/adopt` so the plan matches the new head."
        )

    # When the sign-off state could not be known offline (no --commits-file), it is resolved
    # here — before any branch is created — and the "already signed" precondition still holds.
    if not plan.signoff_state_known:
        plan.commits = read_commits(workdir, f"{plan.rebase_ref}..{fetched_sha}")
        plan.signoff_state_known = True
        if not plan.commits:
            raise Refusal(f"no commits found for PR #{plan.pr} — nothing to adopt.")
        if not plan.unsigned:
            raise Refusal(
                f"every commit of PR #{plan.pr} already carries a valid `Signed-off-by:` trailer — "
                "nothing to adopt."
            )
        print(f"      resolved sign-off state: {len(plan.unsigned)}/{len(plan.commits)} need the trailer")

    print(f"[3/6] Creating {plan.target_branch} at {fetched_sha[:12]} ...")
    git("checkout", "-b", plan.target_branch, fetched_sha, cwd=workdir)

    before = int(git_out("rev-list", "--count", f"{plan.rebase_ref}..HEAD", cwd=workdir) or "0")
    authors_before = read_commits(workdir, f"{plan.rebase_ref}..HEAD")
    print(f"[4/6] {plan.rebase_command}   ({before} commit(s) to replay)")
    # GIT_COMMITTER_* is pinned for this one call: the DCO trailer must name the *adopter*,
    # not whatever identity the CI runner's environment happens to export (environment
    # variables beat `-c user.name=...`). The authors themselves are re-set by the rebase,
    # so the contributor keeps their authorship.
    rebased = git(
        *plan.rebase_argv,
        cwd=workdir,
        check=False,
        env={
            "GIT_COMMITTER_NAME": plan.signoff_name,
            "GIT_COMMITTER_EMAIL": plan.signoff_email,
        },
    )
    if rebased.returncode != 0:
        conflicted = git_out("diff", "--name-only", "--diff-filter=U", cwd=workdir, check=False)
        git("rebase", "--abort", cwd=workdir, check=False)
        git("checkout", original_ref, cwd=workdir, check=False)
        git("branch", "-D", plan.target_branch, cwd=workdir, check=False)
        if rebased.stdout.strip():
            print(rebased.stdout.strip(), file=sys.stderr)
        if rebased.stderr.strip():
            print(rebased.stderr.strip(), file=sys.stderr)
        raise Failure(
            f"`git rebase --signoff {plan.rebase_ref}` hit a conflict. The rebase was aborted and "
            f"{plan.target_branch} was deleted, so nothing was pushed. Conflicted path(s): "
            f"{conflicted or '(reported above)'}. Resolve it by hand, or ask the author to rebase "
            "onto the base branch — adoption never resolves conflicts on the contributor's behalf."
        )

    after = int(git_out("rev-list", "--count", f"{plan.rebase_ref}..HEAD", cwd=workdir) or "0")
    dropped = before - after
    if dropped > 0:
        print(
            f"      NOTICE: {dropped} commit(s) became empty against {plan.rebase_ref} and were "
            f"dropped by the rebase. Inspect `git log {plan.rebase_ref}..HEAD` on "
            f"{plan.target_branch} before opening the PR."
        )
    signed = verify_signed_off(plan, workdir, f"{plan.rebase_ref}..HEAD")
    authors_preserved = check_authors_preserved(authors_before, signed, plan.target_branch)

    print(f"[5/6] Pushing: {plan.push_command}")
    pushed = git(*plan.push_argv, cwd=workdir, check=False)
    if pushed.returncode != 0:
        raise Failure(
            f"the push to {plan.target_branch} was rejected (the branch may have appeared in the "
            f"meantime): {(pushed.stderr or '').strip()}. Delete it with `git push origin --delete "
            f"{plan.target_branch}` and re-run."
        )
    pushed_sha = git_out("rev-parse", "HEAD", cwd=workdir)

    print("[6/6] Pushed. Open the PR from --body-out, then comment on and close the original.")
    return {
        "ok": True,
        "applied": True,
        "mode": "applied",
        "pr": plan.pr,
        "target_branch": plan.target_branch,
        "pushed_sha": pushed_sha,
        "commits_replayed": before,
        "commit_count": len(signed),
        "dropped_empty": dropped,
        "unsigned_before": len(plan.unsigned),
        "authors_preserved": authors_preserved,
        "title": plan.title,
        "original_pr_url": plan.original_url,
        "pr_body": plan.build_pr_body(),
    }


# --------------------------------------------------------------------------------------
# cli
# --------------------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="adopt_pr.py",
        description=(
            "Adopt a fork PR that is blocked on DCO only: fetch the fork's commits, rebase them with "
            "--signoff, push a same-repo branch adopted/<n>, and hand back the body of a new PR that "
            "credits the original author. Dry run by default."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  python3 scripts/adopt_pr.py 1656 --head-repo https://github.com/you/fork.git \\\n"
            "      --head-branch my-branch --author 'You <you@example.com>'   # dry run\n"
            "  python3 scripts/adopt_pr.py 1656 --apply ... --body-out body.md  # execute\n"
        ),
    )
    parser.add_argument("pr", type=int, help="the pull request number to adopt")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--apply", action="store_true", help="execute the plan (fetch, rebase, push); the default is a dry run"
    )
    mode.add_argument("--dry-run", action="store_true", help="print the plan (the default) — performs no writes")
    parser.add_argument("--json", action="store_true", help="print the plan (or the refusal) as JSON on stdout")
    parser.add_argument("--head-repo", help="the fork's clone URL (or a local path, for tests)")
    parser.add_argument(
        "--head-repo-full-name", help="the fork's owner/name when it is known apart from --head-repo"
    )
    parser.add_argument("--head-branch", help="the PR's head branch name")
    parser.add_argument("--head-sha", help="the PR's head commit SHA: pins the fetch and detects a moved fork")
    parser.add_argument("--head-label", help="the PR's head label, e.g. owner:branch (used in messages)")
    parser.add_argument("--author", help="the original author for the Co-authored-by trailer: 'Name <email>'")
    parser.add_argument(
        "--co-author",
        action="append",
        default=[],
        metavar="'NAME <EMAIL>'",
        help="an extra author to credit with an additional Co-authored-by trailer (repeatable)",
    )
    parser.add_argument("--author-login", help="the original author's GitHub login (email fallback + credit)")
    parser.add_argument("--title", help="the original PR title, reused unchanged for the new PR")
    parser.add_argument("--body", help="the original PR body, verbatim")
    parser.add_argument("--body-file", help="a file holding the original PR body, verbatim")
    parser.add_argument(
        "--commits-file",
        help=(
            "JSON file with the PR's commits ([{sha,message,author:{name,email}}] or [message]); "
            "'-' reads stdin"
        ),
    )
    parser.add_argument("--commits-json", help="the same commit list, inline")
    parser.add_argument("--repo", default=DEFAULT_REPO, help=f"the base repository slug (default {DEFAULT_REPO})")
    parser.add_argument("--base", default=DEFAULT_BASE, help=f"the base branch (default {DEFAULT_BASE})")
    parser.add_argument("--workdir", default=".", help="the checkout to work in (default: the current directory)")
    parser.add_argument(
        "--adopter",
        help=(
            "the maintainer login running the adoption: sets the Signed-off-by identity to "
            "<login>@users.noreply.github.com and the credit footer"
        ),
    )
    parser.add_argument("--signoff-name", help=f"the identity used for Signed-off-by (default {DEFAULT_SIGNOFF_NAME})")
    parser.add_argument("--signoff-email", help=f"the e-mail used for Signed-off-by (default {DEFAULT_SIGNOFF_EMAIL})")
    parser.add_argument("--body-out", help="write the new PR body (for `gh pr create --body-file`) here")
    parser.add_argument(
        "--comment-out",
        help=(
            "write the markdown comment for the original PR here: the plan (dry run), the refusal, or — "
            "with --apply — a notice containing the {{NEW_PR_URL}} placeholder"
        ),
    )
    parser.add_argument("--summary-out", help="with --apply: write a JSON summary (pushed SHA, counts) here")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    pr = args.pr

    def write(path: str | None, text: str) -> None:
        if path:
            Path(path).write_text(text, encoding="utf-8")

    try:
        plan = build_plan(args, pr)
        preflight(plan, apply=args.apply)
    except Refusal as refusal:
        reason = str(refusal)
        print(f"REFUSED: {reason}", file=sys.stderr)
        if args.json:
            print(json.dumps(refusal_payload(pr, reason), ensure_ascii=False, indent=2))
        write(args.comment_out, render_refusal_comment(pr, reason))
        return EXIT_REFUSED
    except Failure as failure:
        print(f"FAILED: {failure}", file=sys.stderr)
        return EXIT_FAILED

    if args.apply:
        try:
            summary = apply_plan(plan)
        except Refusal as refusal:  # a race discovered mid-flight (remote branch appeared)
            print(f"REFUSED: {refusal}", file=sys.stderr)
            if args.json:
                print(json.dumps(refusal_payload(pr, str(refusal)), ensure_ascii=False, indent=2))
            write(args.comment_out, render_refusal_comment(pr, str(refusal)))
            return EXIT_REFUSED
        except Failure as failure:
            print(f"FAILED: {failure}", file=sys.stderr)
            return EXIT_FAILED
        write(args.body_out, summary["pr_body"])
        if args.summary_out:
            write(args.summary_out, json.dumps(summary, ensure_ascii=False, indent=2))
        write(args.comment_out, render_adopted_notice(plan))
        if args.json:
            print(json.dumps(summary, ensure_ascii=False, indent=2))
        else:
            print(
                f"ADOPTED PR #{pr}: pushed {summary['pushed_sha'][:12]} to {summary['target_branch']} "
                f"({summary['commit_count']} commit(s), {summary['dropped_empty']} dropped as empty)."
            )
            if args.body_out:
                print(f"New PR body written to {args.body_out}")
        return EXIT_OK

    write(args.body_out, plan.build_pr_body())
    write(args.comment_out, plan.render_comment())
    if args.json:
        print(json.dumps(plan.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(plan.render())
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
