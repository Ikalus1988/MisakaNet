#!/usr/bin/env python3
"""One implementation per bounty issue, enforced mechanically (issue #2043).

The rule "one implementation per bounty, claim it with `/try`" is prose — an `issues/1528` comment
and a section of `CONTRIBUTING.md` — and nothing checked it. On **2026-09-21** that cost a queue:
**#1959 / #1968 / #1980 all claimed the already-satisfied #1942 and asked about payment**, and
#1959's tree was byte-identical to #1960's (both `docs/integrations/gemini-cli.md` hashed to
`c8795f3ba8fcf7441989a31cbb2ab600`) while being its ancestor. A second, cheaper failure sits next to
it: a PR whose body names no issue **at all** cannot be triaged, and that is a one-line body edit
away from being fixable.

Two halves, deliberately separated:

* :func:`decide` — **all** of the judgement, a pure function over :class:`PullRequestFacts`. No
  network, no token, no disk: the tests run offline, and every rule is a separately named function in
  :data:`RULES` so a test can take one out and watch a verdict change (:func:`decide_with`).
* :func:`main` — a **thin** CLI wrapper. Fetch the facts over the GitHub API, call ``decide()``, post
  the receipt when the verdict is not ``ok``. The tests never execute it.

Receipts follow this repository's house style: a verdict is not a receipt until it says **what the
author should do next** (``**回主线的路**``). The maintainer's own receipts on #1959/#1960/#1961 all
end with one, and a receipt without one is incomplete — so `tests/test_bounty_claim.py` asserts the
section exists for every non-``ok`` verdict, including verdicts added later.

Exit codes (a decision is not a failure): ``0`` decided — posted, updated, or nothing to say;
``1`` decided but the receipt could not be delivered (e.g. a read-only token on a fork PR);
``2`` could not decide. The workflow treats all three as non-blocking: a comment is the whole action,
and a governance rule that fails a contributor's PR is how a gate becomes the queue noise it was
written to remove.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, replace
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
API = "https://api.github.com"
WEB = "https://github.com"
REPO_SLUG = os.environ.get("GITHUB_REPOSITORY", "Ikalus1988/MisakaNet")
ISSUES_URL = f"{WEB}/{REPO_SLUG}/issues"

# The marker is what makes the workflow idempotent: the same receipt is *updated* in place on every
# later `edited` event instead of being posted again (five body edits must not leave five receipts).
MARKER = "<!-- misakanet-bounty-claim-guard -->"

VERDICT_OK = "ok"
VERDICT_NO_ISSUE_REFERENCE = "no_issue_reference"
VERDICT_ISSUE_ALREADY_SATISFIED = "issue_already_satisfied"
VERDICT_COMPETING_PR_EXISTS = "competing_pr_exists"
VERDICTS = (
    VERDICT_OK,
    VERDICT_NO_ISSUE_REFERENCE,
    VERDICT_ISSUE_ALREADY_SATISFIED,
    VERDICT_COMPETING_PR_EXISTS,
)

# ── reading a PR body ────────────────────────────────────────────────────────────────────────────
#
# The two shapes are the ones this repository already recognises in `scripts/pr_genius_report.py`
# (`ISSUE_REFERENCE`): a closing keyword, or a bare `#N`. Kept as one expression here because the
# *claim* form that Opire's footer asks for (`/claim #1234`, in the PR description) is a third shape
# that file never had to see.
_EXPLICIT_REFERENCE = re.compile(
    r"(?i)\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s*:?\s+(?:[\w.-]+/[\w.-]+)?#(\d+)"
    r"|/claim\s+(?:[\w.-]+/[\w.-]+)?#(\d+)"
)
_BARE_REFERENCE = re.compile(r"(?<![\w#])#(\d+)")
_FENCE = re.compile(r"^\s*(?:```|~~~)")
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)


def visible_text(body: str) -> str:
    """The body as a human reading the rendered PR would see it.

    Fenced code blocks and HTML comments are removed, and that is a judgement rather than a detail:

    * a fenced block is a **quotation**, not a claim — this repository has received PR bodies that
      were whole agent transcripts (`SOLUTION.md`) full of `#NNNN`, and a quoted log must not be read
      as "this PR claims issue 1234";
    * a reference inside ``<!-- -->`` is **invisible** in the rendered body, which makes it exactly
      the case the guard exists to catch: the triager cannot see it either.

    The ``no_issue_reference`` receipt says this out loud, so an author whose reference is real but
    fenced gets a one-line fix instead of a dead end.
    """
    out: list[str] = []
    in_fence = False
    for line in body.splitlines():
        if _FENCE.match(line):
            in_fence = not in_fence
            continue
        if not in_fence:
            out.append(line)
    return _HTML_COMMENT.sub(" ", "\n".join(out))


def reference_issue(body: str) -> int | None:
    """The issue this PR claims, or ``None``.

    A closing keyword or an Opire ``/claim`` wins over a bare mention: a body that says "related to
    #1941 … Fixes #1942" claims **#1942**, and reporting #1941 would send the author a receipt about
    somebody else's issue. Within one shape the first match wins, which encodes "one PR = one issue".
    """
    text = visible_text(body)
    explicit = _EXPLICIT_REFERENCE.search(text)
    if explicit:
        return int(next(group for group in explicit.groups() if group))
    bare = _BARE_REFERENCE.search(text)
    return int(bare.group(1)) if bare else None


# ── the facts, as data ───────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class CompetingPullRequest:
    """Another open PR, as the caller happened to see it.

    ``body`` is optional on purpose: an entry that carries a body must actually name the issue (see
    :func:`competitors`), while an entry without one is taken as already vetted by the caller — the
    cheap path when the caller's query already filtered.
    """

    number: int
    author: str = ""
    title: str = ""
    created_at: str = ""
    body: str = ""


@dataclass(frozen=True)
class PullRequestFacts:
    """Everything the verdict is allowed to depend on. Data in, verdict out — no I/O anywhere."""

    number: int
    body: str = ""
    author: str = ""
    created_at: str = ""
    # The referenced issue, when the caller already resolved one. `None` means "read it off the body",
    # so a caller holding only the text still gets the full judgement.
    issue_number: int | None = None
    issue_title: str = ""
    issue_state: str = "open"
    # Merged work that already satisfies the issue — merged PRs, lessons already citing the intake.
    satisfied_by: tuple[str, ...] = ()
    # Other open PRs; the caller may pass every open PR and let `competitors()` do the filtering.
    competing_prs: tuple[CompetingPullRequest, ...] = ()


@dataclass(frozen=True)
class Decision:
    """A verdict plus the receipt to post. ``comment`` is ``None`` if and only if the verdict is ok."""

    verdict: str
    issue: int | None
    reason: str
    comment: str | None

    def __post_init__(self) -> None:
        if self.verdict not in VERDICTS:
            raise ValueError(f"unknown verdict {self.verdict!r}; add it to VERDICTS")
        if (self.verdict == VERDICT_OK) == (self.comment is not None):
            raise ValueError(
                "a clean PR must not be commented on, and every other verdict must carry the "
                "receipt that tells the author what to do next"
            )


# ── the rules ────────────────────────────────────────────────────────────────────────────────────
#
# Order is precedence, and it is a decision, not an accident:
#
#   no reference            → nothing else can be evaluated: we do not know which issue this is about
#   already satisfied       → the strongest thing we can tell an author ("this work is on main")
#   competing PR exists     → work is still open, but somebody is already on it
#   ok                      → say nothing at all
#
# `issue_already_satisfied` sits above `competing_pr_exists` because it is what the 2026-09-21 case
# needed: three PRs and a satisfied issue, and the useful sentence is "the issue is done", not "you
# have a rival".


def competitors(facts: PullRequestFacts, issue: int) -> list[CompetingPullRequest]:
    """Other open PRs that claim the same issue, earliest first.

    Two filters, and both are the difference between a useful receipt and one sent to the wrong
    author:

    * the PR itself is excluded by number, so re-running the guard on one PR never reports it as its
      own competitor;
    * an entry that carries a body must actually name the issue. "Another PR is open" is not "another
      PR is working on #1942", and telling a contributor to coordinate with an unrelated PR because
      their number appeared in the same list would be a false positive of the worst kind — one that
      asks a human to do work that does not exist.

    The sort makes the receipt stable: the API's ordering is not part of the verdict.
    """
    found = []
    for pr in facts.competing_prs:
        if pr.number == facts.number:
            continue
        if pr.body.strip() and reference_issue(pr.body) != issue:
            continue
        found.append(pr)
    return sorted(found, key=lambda pr: (pr.created_at or "", pr.number))


def rule_no_issue_reference(facts: PullRequestFacts, issue: int | None) -> Decision | None:
    if issue is not None:
        return None
    return Decision(
        VERDICT_NO_ISSUE_REFERENCE,
        None,
        reason="the PR body names no issue",
        comment=compose_no_issue_reference(facts),
    )


def rule_issue_already_satisfied(facts: PullRequestFacts, issue: int | None) -> Decision | None:
    """Merged work already satisfies this issue — or the issue is closed, which says the same thing.

    A closed issue we cannot point at evidence for is still not work to start: the maintainer decided
    it needs nothing more. The receipt says which of the two it is instead of pretending to know more
    than it does.
    """
    evidence = tuple(dict.fromkeys(facts.satisfied_by))
    closed = facts.issue_state.strip().lower() not in ("", "open")
    if not evidence and not closed:
        return None
    reason = ("the issue is already satisfied by merged work: " + "; ".join(evidence)) if evidence \
        else "the issue is closed"
    return Decision(
        VERDICT_ISSUE_ALREADY_SATISFIED,
        issue,
        reason=reason,
        comment=compose_issue_already_satisfied(facts, issue, evidence, closed=closed),
    )


def rule_competing_pr_exists(facts: PullRequestFacts, issue: int | None) -> Decision | None:
    rivals = competitors(facts, issue) if issue is not None else []
    if not rivals:
        return None
    return Decision(
        VERDICT_COMPETING_PR_EXISTS,
        issue,
        reason=f"{len(rivals)} other open PR(s) reference #{issue}",
        comment=compose_competing_pr_exists(facts, issue, rivals),
    )


RULES = (
    rule_no_issue_reference,
    rule_issue_already_satisfied,
    rule_competing_pr_exists,
)


def decide_with(rules, facts: PullRequestFacts) -> Decision:
    """Apply ``rules`` in order and return the first verdict.

    The seam the tests use: dropping a rule from :data:`RULES` and re-running the same facts is how
    "can this rule go red?" is answered without editing any file
    (`tests/test_bounty_claim.py::test_each_rule_is_load_bearing`).
    """
    issue = facts.issue_number if facts.issue_number is not None else reference_issue(facts.body)
    for rule in rules:
        decision = rule(facts, issue)
        if decision is not None:
            return decision
    return Decision(
        VERDICT_OK,
        issue,
        reason=f"#{issue} is open, unsatisfied, and claimed by no other open PR" if issue
        else "nothing to check",
        comment=None,
    )


def decide(facts: PullRequestFacts) -> Decision:
    """The whole judgement: facts in, verdict plus receipt out. Pure."""
    return decide_with(RULES, facts)


# ── the receipts (`**回主线的路**` is the part that makes them receipts) ───────────────────────────

_FOOTER = (
    "> 这条回执由 `.github/workflows/bounty-claim-guard.yml` 自动生成（issue #2043）。它**只评论、不拦 PR**"
    "——CI 里它永远不是阻塞项；PR 正文或引用变化时会**就地更新这一条**，不会再评论一条新的。"
)


def _receipt(headline: str, intro: list[str], path_back: list[str], note: str = "") -> str:
    lines = [MARKER, f"### {headline}", "", *intro]
    if note:
        lines += ["", note]
    lines += ["", "**回主线的路**", "", *[f"- {item}" for item in path_back], "", _FOOTER]
    return "\n".join(lines)


def _who(author: str) -> str:
    return f"@{author} " if author else ""


def compose_no_issue_reference(facts: PullRequestFacts) -> str:
    return _receipt(
        "这条 PR 没有指名要解决哪个 issue，暂时没法分诊",
        [
            f"{_who(facts.author)}谢谢投稿。这条 PR 的正文里**没有出现任何 issue 号**，所以没人能判断它是"
            "不是重复工作——本仓的队列噪音大半来自赏金：2026-09-21 有 **3 条 PR（#1959/#1968/#1980）"
            "同时声称做完 #1942**，其中一条与另一条**逐字节相同**。",
            "",
            "回执只需要你改 PR 正文（不用重开 PR，也不用 force-push）。",
        ],
        [
            "在正文里加一行 `Fixes #1234`（把 1234 换成你要解决的 issue 号）；`Closes #1234` / "
            "`Resolves #1234` 同样有效。",
            "悬赏 issue 请同时写上 `/claim #1234`（Opire 的认领格式），这样**认领**和**实现**能对上，"
            "别人也就不会再开第二条。",
            f"找不到对应的 issue？先在 {ISSUES_URL}?q=is%3Aissue+is%3Aopen 搜关键词；"
            "本仓是「先有 issue、再做实现」，确实没有就开一条，模板自带验收标准。",
            "如果你**写了** issue 号但它掉进了 ``` 代码块或 `<!-- -->` 注释里：那是引文（本仓收到过整段 "
            "agent 会话转录当正文），渲染出来的正文里读者看不到它——把它挪进正文即可。",
        ],
        note="（`Fixes/Closes/Resolves #N`、`/claim #N`，或正文里任意一个 `#N` 都算引用。）",
    )


def compose_issue_already_satisfied(facts: PullRequestFacts, issue: int | None,
                                    evidence: tuple[str, ...], *, closed: bool) -> str:
    number = f"#{issue}" if issue is not None else "这条 issue"
    intro = [f"{_who(facts.author)}谢谢你来收 {number}。它**不是没人做**："]
    note = ""
    if evidence:
        intro += ["", f"- 已经在 main 上满足它的工作：{'；'.join(evidence)}"]
    if closed and not evidence:
        intro += ["", "- 该 issue 已经**关闭**。工具没能指出是哪一份工作收的尾（可能是一份文档、"
                      "一次合并，或维护者判定它不需要再做）。"]
        note = "所以这条回执不猜：**先在上面问一句**，不要默认它还需要实现。"
    intro += ["",
              f"重复投稿不会被合并，也不会重复支付：赏金结在**合并了**的那一条上。"
              f"（2026-09-21 的 #1942 就同时收到三条 PR #1959/#1968/#1980。）"]
    return _receipt(
        (f"{number} 已经关闭，这条 PR 不需要继续" if closed and not evidence
         else f"{number} 已经有落地的工作，这条 PR 不需要继续"),
        intro,
        [
            "如果 main 上那份**确实不够**：开一条**新** PR 只做**增量**修改（在已存在的文件上追加/修正，"
            "不要整文件替换），正文里写清「现在缺什么、我补什么」。同名替换会被按重复关掉。",
            "如果内容一样：关掉这条，把独有内容（实测输出、版本号、命令、field report）作为评论补到"
            "已经合并的那份工作下面——本仓给报料者补回执用的就是这条路。",
            f"如果你认为「已满足」的判断是错的：在 {number} 下面**对着验收标准逐条**说缺哪一条，"
            "维护者会重开或另开一条。",
            f"想继续收赏金：去 {ISSUES_URL}?q=is%3Aissue+is%3Aopen+label%3Aready "
            "挑一条**还没有 PR** 的 issue，按第一条路走。",
        ],
        note=note,
    )


def compose_competing_pr_exists(facts: PullRequestFacts, issue: int | None,
                                rivals: list[CompetingPullRequest]) -> str:
    first = rivals[0]
    rows = ["| PR | 作者 | 开于 |", "|---|---|---|"]
    for pr in rivals[:5]:
        rows.append(f"| #{pr.number} | {'@' + pr.author if pr.author else '?'} | {pr.created_at or '?'} |")
    if len(rivals) > 5:
        rows.append(f"| …还有 {len(rivals) - 5} 条 | | |")

    # Who arrived first decides what "the path back" even is: the rule is first-come, so the receipt
    # must not tell the earlier author to go and join the later one. With either timestamp missing the
    # guard says it does not know rather than guessing.
    i_was_first: bool | None = None
    if facts.created_at and first.created_at:
        i_was_first = facts.created_at < first.created_at

    if i_was_first is True:
        headline = f"#{issue} 上还有另一条 PR，但按时间**你才是先到的**"
    elif i_was_first is False:
        headline = f"#{issue} 已经有另一条进行中的 PR（比你先到）"
    else:
        headline = f"#{issue} 已经有另一条进行中的 PR"

    intro = [
        f"{_who(facts.author)}谢谢你来收 #{issue}。这条 issue 上已经有**开着的** PR：",
        "", *rows, "",
    ]
    if i_was_first is True:
        intro.append(f"你的 PR 早于 #{first.number}，按本仓「先到先得」的认领规则，这里该以你为准。")
    elif i_was_first is False:
        intro.append(f"#{first.number} 比你先到。同时开两条不会更快：2026-09-21 那天三条 PR 抢同一个 "
                     "issue，最后一条都没能按原样合并。")
    else:
        intro.append("回执无法比较先后（有一条没带创建时间），所以下面两条路都列出来，"
                     "请在 PR 里贴一下时间戳。")

    if i_was_first is True:
        path_back = [
            f"在 #{first.number} 下面贴出你这条 PR 的链接与时间，请对方把独有内容并到**你**这条上。",
            "然后关掉对方那条（别两边同时改同一个文件——本仓的三条 PR 就是因为分支互相叠加，"
            "任一条都带着另外两条的内容，谁都没法干净合并）。",
            f"如果你的实现其实不如对方，反过来也一样：把 #{first.number} 里更好的那部分抄过来，"
            "合并成一条。",
            "想放弃这条去合作也完全可以：把内容并到对方那条，然后关掉这条。",
        ]
    elif i_was_first is False:
        path_back = [
            f"去 #{first.number} 下面留言，说清你能补什么（缺的测试、field report、真实输出），"
            "把独有内容并到**那一条** PR 上。",
            "两条都没合并时先协商出**一条**：谁的内容更完整谁留，另一条关掉。重复的 PR 不会被合并，"
            "也不会重复支付。",
            f"如果你的实现**确实不同**（例如一条你没见过的路径）：在正文里加一段「与 #{first.number} "
            "的差异」并写明取舍，维护者会按差异判断，而不是按先后来。",
            "如果你其实比它早：在这条 PR 下面贴出创建时间，本条回执会随正文变化更新。",
        ]
    else:
        path_back = [
            f"先弄清先后：在 PR 正文里写上你的创建时间，并在 #{first.number} 下面留言对齐；按本仓规则，"
            "先到的那条为准。",
            f"然后把内容合并到**一条** PR 上（谁更完整谁留），另一条关掉。与 #{first.number} 的差异"
            "请单独写一段说明。",
        ]
    return _receipt(headline, intro, path_back)


# ── the thin CLI (never executed by the tests) ───────────────────────────────────────────────────


def _token(explicit: str | None = None) -> str | None:
    if explicit:
        return explicit.strip()
    for var in ("GITHUB_TOKEN", "GH_TOKEN"):
        if os.environ.get(var):
            return os.environ[var].strip()
    return None


def _api(url: str, token: str, method: str = "GET", payload: dict | None = None):
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
        "User-Agent": "misakanet-bounty-claim-guard",
    })
    with urllib.request.urlopen(request, timeout=30) as response:  # a hung request must not hang the job
        body = response.read().decode("utf-8")
    return json.loads(body) if body.strip() else {}


def _open_pull_requests(repo: str, token: str, limit: int = 300) -> list[dict]:
    out: list[dict] = []
    page = 1
    while len(out) < limit:
        batch = _api(f"{API}/repos/{repo}/pulls?state=open&per_page=100&page={page}", token)
        if not batch:
            break
        out += batch
        page += 1
    return out[:limit]


def _satisfaction_evidence(repo: str, issue: int, token: str) -> list[str]:
    """Merged work that already satisfies the issue.

    Two resolvers, because the two ways an issue gets satisfied here look nothing alike: a **merged
    PR** (the closing commit / a cross-reference from a merged PR in the issue timeline) and a
    **lesson already citing the intake**, which is what `scripts/intake_receipt.py` resolves for
    receipts and is reused rather than re-derived — one answer per question.
    """
    evidence: list[str] = []
    try:
        events = _api(f"{API}/repos/{repo}/issues/{issue}/timeline?per_page=100", token)
    except urllib.error.HTTPError as exc:
        print(f"warning: could not read the timeline of #{issue} ({exc.code}); "
              "satisfaction is decided from the issue state alone", file=sys.stderr)
        events = []
    for event in events:
        source = ((event.get("source") or {}).get("issue") or {})
        pull = source.get("pull_request") or {}
        if event.get("event") == "cross-referenced" and pull.get("merged_at"):
            evidence.append(f"PR #{source.get('number')}（已合并）")
        elif event.get("event") == "closed" and event.get("commit_id"):
            evidence.append(f"关闭事件 commit {str(event['commit_id'])[:9]}"
                            f"（by @{((event.get('actor') or {}).get('login')) or '?'}）")
    try:
        sys.path.insert(0, str(REPO))
        from scripts.intake_receipt import lessons_citing  # single resolver, on purpose

        evidence += [f"`{lesson['path']}`（已引用 intake #{issue}）" for lesson in lessons_citing(issue)]
    except Exception as exc:  # a missing corpus must not turn into a wrong verdict
        print(f"warning: could not read the lesson corpus ({exc}); "
              "merged PRs still decide satisfaction", file=sys.stderr)
    return list(dict.fromkeys(evidence))


def gather_facts(repo: str, pr_number: int, token: str, *, extra_satisfied_by=(),
                 issue_override: int | None = None, state_override: str | None = None) -> PullRequestFacts:
    """The API half: read the PR, its issue, the merged evidence, and the other open PRs."""
    pull = _api(f"{API}/repos/{repo}/pulls/{pr_number}", token)
    body = pull.get("body") or ""
    issue = issue_override if issue_override is not None else reference_issue(body)
    facts = PullRequestFacts(
        number=pull.get("number", pr_number),
        body=body,
        author=((pull.get("user") or {}).get("login") or ""),
        created_at=pull.get("created_at") or "",
        issue_number=issue,
    )
    if issue is None:
        return facts

    issue_data = _api(f"{API}/repos/{repo}/issues/{issue}", token)
    evidence = list(extra_satisfied_by) + _satisfaction_evidence(repo, issue, token)
    facts = replace(
        facts,
        issue_title=issue_data.get("title") or "",
        issue_state=state_override or issue_data.get("state") or "open",
        satisfied_by=tuple(dict.fromkeys(evidence)),
    )
    # Every open PR goes in; `competitors()` decides which of them is a rival. Putting that filter in
    # the pure core is what makes it testable in both directions.
    others = tuple(
        CompetingPullRequest(
            number=pr.get("number", 0),
            author=((pr.get("user") or {}).get("login") or ""),
            title=pr.get("title") or "",
            created_at=pr.get("created_at") or "",
            body=pr.get("body") or "",
        )
        for pr in _open_pull_requests(repo, token)
    )
    return replace(facts, competing_prs=others)


def offline_facts(args) -> PullRequestFacts:
    """Facts from flags only — no token, no network. How a maintainer rehearses a receipt."""
    body = ""
    if args.body_file:
        body = Path(args.body_file).read_text(encoding="utf-8")
    rivals = []
    for spec in args.competitor or []:
        number, _, rest = spec.partition(":")
        author, _, created = rest.partition("@")
        rivals.append(CompetingPullRequest(number=int(number), author=author.strip(),
                                           created_at=created.strip()))
    return PullRequestFacts(
        number=args.pr,
        body=body,
        author=args.author or "",
        created_at=args.created_at or "",
        issue_number=args.issue,
        issue_state=args.issue_state or "open",
        satisfied_by=tuple(args.satisfied_by or ()),
        competing_prs=tuple(rivals),
    )


def receipt_action(existing_comments: list[dict], marker: str = MARKER) -> tuple[str, int | None]:
    """Whether to post the receipt or update the one this guard posted before.

    Pure, because idempotency is a **decision** rather than an HTTP detail: `edited` fires on every
    body change, and creating on each one would leave five receipts on one PR — the queue noise this
    guard exists to remove, produced by the guard itself. A receipt already posted for this PR is
    updated in place, never duplicated.
    """
    for comment in existing_comments:
        if marker in (comment.get("body") or ""):
            return "update", comment.get("id")
    return "create", None


def upsert_receipt(repo: str, pr_number: int, comment: str, token: str) -> str:
    """Post the receipt, or update the one this guard posted before. Returns what happened."""
    existing = _api(f"{API}/repos/{repo}/issues/{pr_number}/comments?per_page=100", token)
    action, comment_id = receipt_action(existing)
    if action == "update":
        _api(f"{API}/repos/{repo}/issues/comments/{comment_id}", token, "PATCH", {"body": comment})
        return f"updated comment {comment_id}"
    _api(f"{API}/repos/{repo}/issues/{pr_number}/comments", token, "POST", {"body": comment})
    return "posted a new comment"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="One implementation per bounty issue (#2043).")
    parser.add_argument("--repo", default=REPO_SLUG)
    parser.add_argument("--pr", type=int, required=True)
    parser.add_argument("--token", default=None, help="defaults to GITHUB_TOKEN / GH_TOKEN")
    parser.add_argument("--post", action="store_true", help="post/update the receipt (non-ok only)")
    parser.add_argument("--dry-run", action="store_true", help="print the receipt, post nothing")
    parser.add_argument("--json", action="store_true", help="print the decision as JSON")
    parser.add_argument("--verdict-file", default=None, help="write the bare verdict here")
    parser.add_argument("--comment-file", default=None,
                        help="write the receipt here (empty when the verdict is ok)")
    parser.add_argument("--issue", type=int, default=None, help="override the referenced issue")
    parser.add_argument("--issue-state", default=None, help="override the issue state (open/closed)")
    parser.add_argument("--satisfied-by", action="append", default=[],
                        help="evidence that the issue is already satisfied (repeatable)")
    parser.add_argument("--body-file", default=None, help="read the PR body from here instead")
    parser.add_argument("--author", default=None)
    parser.add_argument("--created-at", default=None)
    parser.add_argument("--competitor", action="append", default=[],
                        help="NUMBER[:AUTHOR][@CREATED_AT] of another open PR (repeatable)")
    parser.add_argument("--offline", action="store_true", help="no API calls at all")
    args = parser.parse_args(argv)

    if args.offline:
        facts = offline_facts(args)
        decision = decide(facts)
        delivered = "not attempted (--offline)"
    else:
        token = _token(args.token)
        if not token:
            print("no GitHub token: set GITHUB_TOKEN or pass --token "
                  "(or use --offline with --body-file/--issue)", file=sys.stderr)
            return 2
        try:
            facts = gather_facts(args.repo, args.pr, token, extra_satisfied_by=args.satisfied_by,
                                 issue_override=args.issue, state_override=args.issue_state)
        except urllib.error.HTTPError as exc:
            print(f"could not read PR #{args.pr} from {args.repo}: HTTP {exc.code} — "
                  "no verdict was produced", file=sys.stderr)
            return 2
        decision = decide(facts)
        if decision.verdict == VERDICT_OK:
            delivered = "nothing to say (verdict ok — this guard only comments on non-ok verdicts)"
        elif args.dry_run:
            delivered = "not posted (--dry-run)"
        elif not args.post:
            delivered = "not posted (--post was not passed)"
        else:
            try:
                delivered = upsert_receipt(args.repo, args.pr, decision.comment, token)
            except urllib.error.HTTPError as exc:
                print(f"verdict {decision.verdict!r} decided but the receipt was NOT delivered: "
                      f"HTTP {exc.code}. On a `pull_request` run from a fork GitHub hands this job a "
                      "read-only token; run the workflow by hand (workflow_dispatch) with a token that "
                      "can write. Not a blocker by design — see the workflow header.", file=sys.stderr)
                return 1

    if args.verdict_file:
        Path(args.verdict_file).write_text(decision.verdict + "\n", encoding="utf-8")
    if args.comment_file:
        Path(args.comment_file).write_text((decision.comment or "") + "\n", encoding="utf-8")
    print(f"verdict: {decision.verdict}")
    print(f"reason: {decision.reason}")
    print(f"receipt: {delivered}")
    if args.json:
        print(json.dumps({"verdict": decision.verdict, "issue": decision.issue,
                          "reason": decision.reason, "comment": decision.comment,
                          "delivered": delivered}, ensure_ascii=False, indent=2))
    elif decision.comment and (args.dry_run or args.offline):
        print("\n" + decision.comment)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
