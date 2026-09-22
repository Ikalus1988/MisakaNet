"""Pure functions for local intake salvage review."""

from dataclasses import dataclass
from enum import Enum
import re
from typing import Iterable, List, Optional


class ReviewAction(str, Enum):
    IMPROVE = "improve"
    CONVERT = "convert"
    CLOSE = "close"


@dataclass(frozen=True)
class Issue:
    number: int
    title: str
    created: str
    url: str


@dataclass(frozen=True)
class ReviewReport:
    issue: Issue
    action: ReviewAction
    reasons: List[str]
    checklist: List[str]


_ROW = re.compile(
    r"\|\s*#(?P<number>\d+)\s*\|\s*(?P<title>.*?)\s*\|\s*"
    r"(?P<created>\d{4}-\d{2}-\d{2})\s*\|\s*\[Review\]\((?P<url>https?://[^)]+)\)\s*\|"
)


def parse_digest(text: str) -> List[Issue]:
    """Extract well-formed issue rows from a digest, ignoring malformed rows."""
    if not isinstance(text, str):
        raise TypeError("digest must be text")
    return [
        Issue(int(m.group("number")), _clean_title(m.group("title")), m.group("created"), m.group("url"))
        for m in _ROW.finditer(text)
    ]


def _clean_title(title: str) -> str:
    # Titles may contain copied snippets or line breaks; preserve meaning, not noise.
    return re.sub(r"\s+", " ", title).strip()


def sanitize_text(text: str) -> str:
    """Remove user-specific absolute paths and common secret-shaped values."""
    text = re.sub(r"(?<!\w)/(?:Users|home|var/folders)/[^\s`\"']+", "<REDACTED_PATH>", text)
    text = re.sub(r"(?i)(api[_ -]?key|token|password|secret)\s*[:=]\s*[^\s,;]+", r"\1=<REDACTED>", text)
    return text


def review_issue(issue: Issue, *, error: Optional[str] = None, example: Optional[str] = None,
                 verification: Optional[str] = None) -> ReviewReport:
    """Suggest a human-review action; never mutates or submits an issue."""
    supplied = [error, example, verification]
    missing = [name for name, value in zip(("Error", "example", "Verification"), supplied) if not value]
    if error and verification:
        action, reasons = ReviewAction.IMPROVE, ["Issue has actionable reproduction evidence."]
    elif error or example or verification:
        action, reasons = ReviewAction.IMPROVE, ["Issue has partial technical evidence; complete the missing sections."]
    else:
        action, reasons = ReviewAction.CONVERT, ["No technical evidence is present in the digest; human triage is required."]
    checklist = ["Add a ## Error section with the exact error message.", "Add a minimal reproducible code example.",
                 "Add ## Verification with deterministic steps.", "Remove user-specific paths and secrets."]
    if missing:
        checklist.insert(0, "Complete missing evidence: " + ", ".join(missing) + ".")
    return ReviewReport(issue, action, reasons, checklist)


def render_review(reports: Iterable[ReviewReport]) -> str:
    lines = ["# Salvage review plan", "", "No external GitHub changes were performed.", ""]
    for report in reports:
        lines += [f"## #{report.issue.number} — {report.issue.title}", f"Action: **{report.action.value}**"]
        lines += [f"- {reason}" for reason in report.reasons]
        lines += ["Checklist:"] + [f"- {item}" for item in report.checklist] + [""]
    return "\n".join(lines)
