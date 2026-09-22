"""Pure policy decisions; callers provide the current GitHub event snapshot."""

from dataclasses import dataclass
from enum import Enum
import re

ISSUE_REF = re.compile(r"(?<![\w-])(?:[\w.-]+/[^\s#]+)?#(\d+)(?!\d)")
RETURN_PATH = "回主线的路"


class Decision(str, Enum):
    ACCEPT = "accept"
    MISSING_ISSUE = "missing_issue"
    IN_FLIGHT = "in_flight"
    SATISFIED = "satisfied"


@dataclass(frozen=True)
class PullRequest:
    number: int
    body: str = ""


@dataclass(frozen=True)
class IssueSnapshot:
    number: int
    in_flight_pr: int | None = None
    satisfied: bool = False


@dataclass(frozen=True)
class CheckResult:
    decision: Decision
    issue_number: int | None
    receipt: str | None = None

    @property
    def blocked(self) -> bool:
        """Whether this PR must stay out of the bounty queue."""
        return self.decision in {Decision.IN_FLIGHT, Decision.SATISFIED}


def referenced_issue_numbers(text: str) -> tuple[int, ...]:
    """Return unique issue numbers mentioned as #123 (including owner/repo#123)."""
    return tuple(dict.fromkeys(int(number) for number in ISSUE_REF.findall(text or "")))


def check_pull_request(pr: PullRequest, issues: dict[int, IssueSnapshot]) -> CheckResult:
    """Check an opened PR without mutating state or blocking unrelated PRs.

    A PR may mention multiple issues; the first actionable issue is used. A clean
    PR is accepted when it contains no bounty-style issue reference requirement.
    """
    refs = referenced_issue_numbers(pr.body)
    if not refs:
        return CheckResult(Decision.MISSING_ISSUE, None, missing_issue_receipt(pr.number))

    for issue_number in refs:
        issue = issues.get(issue_number)
        if issue is None:
            continue
        if issue.satisfied:
            return CheckResult(Decision.SATISFIED, issue_number, satisfied_receipt(issue_number))
        if issue.in_flight_pr is not None and issue.in_flight_pr != pr.number:
            return CheckResult(Decision.IN_FLIGHT, issue_number,
                               in_flight_receipt(issue_number, issue.in_flight_pr))
        return CheckResult(Decision.ACCEPT, issue_number, None)
    return CheckResult(Decision.ACCEPT, refs[0], None)


def missing_issue_receipt(pr_number: int) -> str:
    return (f"PR #{pr_number} 暂不进入悬赏队列：请在描述中引用目标 issue（如 `#123`）。"
            f" {RETURN_PATH}：补充 issue 引用后重新检查；普通 PR 不受影响。")


def in_flight_receipt(issue_number: int, first_pr: int) -> str:
    return (f"issue #{issue_number} 已有进行中的 PR #{first_pr}，请先在该 PR 协作或说明不同范围。"
            f" {RETURN_PATH}：到 #{first_pr} 留言认领协作，或与维护者确认后再拆分提交。")


def satisfied_receipt(issue_number: int) -> str:
    return (f"issue #{issue_number} 已满足（课程/文档等成果已落地），本 PR 不进入重复赏金队列。"
            f" {RETURN_PATH}：请查看现有成果并提交补充改进，或在原 issue 讨论新的缺口。")
