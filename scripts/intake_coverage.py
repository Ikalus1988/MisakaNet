#!/usr/bin/env python3
"""Normalize an intake title and measure local lesson coverage.

This helper deliberately imports the local search engine instead of invoking
``search_knowledge.py``.  The CLI has an anonymous remote-search path and its
quota/telemetry side effects are not appropriate for batch triage.

Examples::

    python3 scripts/intake_coverage.py --issue 1460
    python3 scripts/intake_coverage.py \
        --title "[Intake] Docker build fails with exit code 137"
    python3 scripts/intake_coverage.py --issue 1460 --json

The default threshold (0.40) is intentionally above the search engine's
0.325 no-match baseline.  It was calibrated against five known-covered and
five known-uncovered intake queries; see the bounty PR description for the
measurement table and rationale.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import re
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

# Allow direct execution from a checkout without installing the package.
REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from misakanet.search.engine import (  # noqa: E402
    LESSONS,
    _load_docs,
    _rank_docs,
)

SEARCH_REPO = REPO

DEFAULT_REPO = "Ikalus1988/MisakaNet"
DEFAULT_MIN_SCORE = 0.40
DEFAULT_TOP_N = 5

# The issue pipeline puts these fields at the top of intake bodies.  Match the
# whole line so a reporter can still discuss a source or a deduplication key in
# the actual report below it.
_METADATA_LINE_RE = re.compile(
    r"^\s*\*\*(?:Kind|Source|Dedup|Contributor|Node|Matched lesson[^*]*):\*\*.*$",
    re.IGNORECASE,
)
_DETAILS_RE = re.compile(r"<details\b[^>]*>.*?</details\s*>", re.IGNORECASE | re.DOTALL)
_SUBMITTED_LINE_RE = re.compile(r"^\s*_Submitted via remote MCP\b.*$", re.IGNORECASE)
_SEPARATOR_RE = re.compile(r"^\s*<(?:br|hr)\s*/?>\s*$", re.IGNORECASE)
_PREFIX_RE = re.compile(
    r"^\s*(?:(?:\[(?:Intake|Question|Lesson)\])\s*)+",
    re.IGNORECASE,
)

# Common English, Simplified Chinese, and Portuguese glue words.  Technical
# words such as ``exit``, ``code``, ``docker`` and ``137`` are deliberately not
# in this list.  The lists are small and explicit so normalization remains
# deterministic and reviewable.
_STOPWORDS = {
    # English
    "a",
    "about",
    "after",
    "again",
    "all",
    "also",
    "an",
    "and",
    "any",
    "are",
    "as",
    "at",
    "be",
    "because",
    "been",
    "before",
    "being",
    "between",
    "but",
    "by",
    "can",
    "could",
    "did",
    "do",
    "does",
    "doing",
    "for",
    "from",
    "had",
    "has",
    "have",
    "having",
    "how",
    "if",
    "in",
    "into",
    "is",
    "it",
    "its",
    "itself",
    "me",
    "more",
    "most",
    "my",
    "no",
    "not",
    "of",
    "off",
    "on",
    "once",
    "only",
    "or",
    "other",
    "our",
    "out",
    "over",
    "same",
    "she",
    "should",
    "so",
    "some",
    "such",
    "than",
    "that",
    "the",
    "their",
    "theirs",
    "them",
    "then",
    "there",
    "these",
    "they",
    "this",
    "those",
    "through",
    "to",
    "too",
    "under",
    "until",
    "up",
    "us",
    "very",
    "was",
    "we",
    "were",
    "what",
    "when",
    "where",
    "which",
    "while",
    "who",
    "whom",
    "why",
    "will",
    "with",
    "would",
    "you",
    "your",
    "using",
    "used",
    "via",
    "when",
    "without",
    # Chinese
    "的",
    "了",
    "和",
    "是",
    "在",
    "与",
    "及",
    "或",
    "这",
    "那",
    "也",
    "以",
    "对",
    "将",
    "把",
    "被",
    "等",
    "中",
    "上",
    "下",
    "为",
    "于",
    "从",
    "到",
    "一个",
    "问题",
    # Portuguese
    "a",
    "ao",
    "aos",
    "as",
    "com",
    "como",
    "da",
    "das",
    "de",
    "do",
    "dos",
    "e",
    "em",
    "entre",
    "era",
    "essa",
    "esse",
    "esta",
    "este",
    "foi",
    "há",
    "isso",
    "na",
    "nas",
    "no",
    "nos",
    "num",
    "ou",
    "para",
    "pela",
    "pelas",
    "pelo",
    "pelos",
    "por",
    "que",
    "se",
    "sem",
    "sua",
    "suas",
    "seu",
    "seus",
    "um",
    "uma",
    "umas",
    "uns",
}

# Verbs and generic prose immediately before an error marker are not useful as
# the context seed.  For example, ``Docker build fails with exit code 137``
# should produce ``docker exit code 137``, not ``build fails exit code 137``.
_CONTEXT_FILLERS = {
    "build",
    "builds",
    "built",
    "fail",
    "fails",
    "failed",
    "failure",
    "failing",
    "happen",
    "happens",
    "issue",
    "problem",
    "large",
    "limit",
    "limits",
    "make",
    "makes",
    "using",
    "use",
    "used",
    "when",
    "with",
    "without",
    "image",
    "images",
    "base",
    "multi-stage",
    "runner",
    "runners",
    "the",
    "and",
    "or",
}

# Match words while retaining the shapes that are useful for retrieval:
# ``ERR_CONNECTION_RESET``, ``package.json``, ``src/foo.py`` and versions are
# each kept as one candidate token.  The local BM25 tokenizer may additionally
# split punctuation when it indexes a document; preserving it here ensures the
# original error/command remains visible to the user.
_TOKEN_RE = re.compile(
    r"(?:[A-Za-zÀ-ÖØ-öø-ÿ0-9_.-]+/)+[A-Za-zÀ-ÖØ-öø-ÿ0-9_.-]+|"
    r"[A-Za-z]:[\\/][A-Za-zÀ-ÖØ-öø-ÿ0-9_.\\/-]+|"
    r"[A-Za-zÀ-ÖØ-öø-ÿ0-9]+(?:[_.-][A-Za-zÀ-ÖØ-öø-ÿ0-9]+)*|"
    r"[\u3400-\u9fff]+"
)

_ERROR_PATTERNS = (
    re.compile(
        r"\b(?:exit|return|status)[ \t]+(?:code|status)?[ \t]*[:=]?[ \t]*\d+\b", re.IGNORECASE
    ),
    re.compile(
        r"\b(?i:error|errno|http|status)[ \t]*(?:code)?[ \t]*[:=]?[ \t]*"
        r"(?:\d{3,}|[A-Z][A-Za-z0-9_.-]*|[A-Z0-9]+[_-][A-Z0-9_-]+)\b"
    ),
    re.compile(r"\b(?:E\d{2,}|ERR[_-][A-Z0-9_-]+|[A-Z][A-Z0-9]+_[A-Z0-9_]+)\b"),
)
_COMMAND_RE = re.compile(r"`([^`\n]{2,160})`|^\s*\$\s+(.+)$", re.MULTILINE)


def strip_pipeline_boilerplate(text: str) -> str:
    """Remove intake metadata and the generated Opire/MCP footer.

    The function is intentionally line-oriented for metadata: it removes only
    known generated fields, not arbitrary lines containing words such as
    ``source`` or ``kind``.  Opire's HTML ``<details>`` block is removed as a
    whole, including its explanatory payment text.
    """
    if not text:
        return ""

    without_details = _DETAILS_RE.sub("\n", text)
    kept: list[str] = []
    for line in without_details.splitlines():
        if _METADATA_LINE_RE.match(line) or _SUBMITTED_LINE_RE.match(line):
            continue
        if _SEPARATOR_RE.match(line):
            continue
        kept.append(line.rstrip())

    # Trim generated separator whitespace while preserving paragraph breaks.
    return "\n".join(kept).strip()


def normalize_title(title: str) -> str:
    """Remove the standard intake/question/lesson title prefix."""
    return _PREFIX_RE.sub("", title or "").strip()


def _tokens(text: str) -> list[str]:
    return [
        match.group(0).strip(".,;:!?()[]{}<>\"'`").lower() for match in _TOKEN_RE.finditer(text)
    ]


def _meaningful_tokens(text: str) -> list[str]:
    result: list[str] = []
    for token in _tokens(text):
        if not token or token in _STOPWORDS:
            continue
        if len(token) == 1 and token.isalpha() and token.isascii():
            continue
        if token not in result:
            result.append(token)
    return result


def _special_error_queries(text: str) -> list[str]:
    """Return compact queries for error strings, identifiers, and commands."""
    queries: list[str] = []
    seen_phrases: set[str] = set()
    all_terms = _tokens(text)

    for pattern in _ERROR_PATTERNS:
        for match in pattern.finditer(text):
            phrase = " ".join(_meaningful_tokens(match.group(0)))
            if not phrase or phrase in seen_phrases:
                continue
            seen_phrases.add(phrase)
            before = _meaningful_tokens(text[: match.start()])
            context_terms = [
                term for term in before[-6:] if term not in _CONTEXT_FILLERS and not term.isdigit()
            ]
            context = " ".join(context_terms[-2:])
            query = f"{context} {phrase}".strip() if context else phrase
            if query not in queries:
                queries.append(query)

    command_queries: list[str] = []
    for match in _COMMAND_RE.finditer(text):
        command = match.group(1) or match.group(2) or ""
        command_terms = _meaningful_tokens(command)
        if len(command_terms) >= 2:
            query = " ".join(command_terms[:8])
            if query not in command_queries:
                command_queries.append(query)

    # Preserve distinctive identifiers, dotted names, paths, and underscored
    # error strings even when they do not match one of the phrase patterns.
    distinctive = [
        term
        for term in all_terms
        if ("_" in term or "." in term or "/" in term or "\\" in term)
        and len(term) > 2
        and term not in _STOPWORDS
    ]
    context = next((term for term in all_terms if term not in _STOPWORDS), "")
    for query in command_queries:
        if query not in queries:
            queries.append(query)

    for term in distinctive:
        query = f"{context} {term}".strip() if context and context != term else term
        if query not in queries:
            queries.append(query)

    return queries


def build_queries(title: str, body: str = "") -> tuple[str, list[str]]:
    """Return cleaned title text and one to three deterministic search queries."""
    cleaned_title = normalize_title(title)
    cleaned_body = strip_pipeline_boilerplate(body)
    title_terms = _meaningful_tokens(cleaned_title)
    normalized_query = " ".join(title_terms)

    # The long query is based on the title (the source of the false-negative
    # described by the issue).  The cleaned body contributes only compact error
    # and command candidates, so acceptance-template prose cannot drown out the
    # title's domain terms.
    candidates: list[str] = []
    if normalized_query:
        candidates.append(normalized_query)
    candidates.extend(
        _special_error_queries("\n".join(part for part in (cleaned_title, cleaned_body) if part))
    )

    # A title made entirely of stopwords is still actionable if its body has a
    # technical error/command.  Conversely, direct --title input always yields
    # at least one candidate when it contains any non-whitespace text.
    if not candidates:
        fallback = " ".join(_meaningful_tokens(cleaned_body))
        if fallback:
            candidates.append(fallback)
    if not candidates and cleaned_title:
        candidates.append(cleaned_title)

    deduped: list[str] = []
    for candidate in candidates:
        candidate = re.sub(r"\s+", " ", candidate).strip()
        if candidate and candidate not in deduped:
            deduped.append(candidate)
        if len(deduped) == 3:
            break
    return cleaned_title, deduped


def _frontmatter_type(content: str, path: Path, title: str) -> str:
    """Read the optional lesson/FAQ type without changing search-engine code."""
    if content.startswith("---"):
        end = content.find("\n---", 3)
        frontmatter = content[3:end] if end >= 0 else content[3:]
    else:
        frontmatter = ""

    # Support both top-level ``type: faq`` and the historical nested
    # ``metadata:\n  type: feedback`` shape.
    top_level = re.search(
        r"^\s*type\s*:\s*[\"']?([^\"'\n#]+)", frontmatter, re.IGNORECASE | re.MULTILINE
    )
    if top_level:
        return top_level.group(1).strip().lower()
    nested = re.search(
        r"^\s*metadata\s*:\s*\n(?:^[ \t]+.*\n)*?^[ \t]+type\s*:\s*[\"']?([^\"'\n#]+)",
        frontmatter,
        re.IGNORECASE | re.MULTILINE,
    )
    if nested:
        return nested.group(1).strip().lower()
    if "faq" in path.parts or "faq" in title.lower():
        return "faq"
    return "lesson"


def _relative_path(path: Path) -> str:
    try:
        return path.relative_to(SEARCH_REPO).as_posix()
    except ValueError:
        return path.as_posix()


def search_local(query: str, docs: list[Any], top_n: int, min_score: float) -> list[dict[str, Any]]:
    """Search one candidate and return stable, human-readable result records."""
    if not query:
        return []
    # Cache initialization/status messages are useful to an interactive search,
    # but would corrupt this helper's JSON mode.  Keep the engine itself intact.
    with contextlib.redirect_stdout(io.StringIO()):
        ranked = _rank_docs(query, docs, titles_only=False, broad_only=False)

    results: list[dict[str, Any]] = []
    for score, doc in ranked[:top_n]:
        path = Path(doc.filepath)
        title = str(doc.title or path.stem)
        value = float(score)
        results.append(
            {
                "id": path.stem,
                "type": _frontmatter_type(doc.content or "", path, title),
                "score": round(value, 6),
                "meets_threshold": value >= min_score,
                "title": title,
                "path": _relative_path(path),
            }
        )
    return results


def classify_conclusion(query_results: Iterable[dict[str, Any]]) -> str:
    """Classify qualifying hits using the exact issue vocabulary."""
    qualifying = [item for item in query_results if item.get("meets_threshold")]
    if any(str(item.get("type", "lesson")).lower() != "faq" for item in qualifying):
        return "lesson-covered"
    if any(str(item.get("type", "lesson")).lower() == "faq" for item in qualifying):
        return "faq-only"
    return "no-coverage"


def analyze(
    title: str, body: str = "", min_score: float = DEFAULT_MIN_SCORE, top_n: int = DEFAULT_TOP_N
) -> dict[str, Any]:
    """Build the complete coverage report for a title/body pair."""
    normalized_title, queries = build_queries(title, body)
    with contextlib.redirect_stdout(io.StringIO()):
        docs = _load_docs(LESSONS, is_lesson=True)

    query_reports: list[dict[str, Any]] = []
    all_results: list[dict[str, Any]] = []
    for query in queries:
        results = search_local(query, docs, top_n=top_n, min_score=min_score)
        query_reports.append({"query": query, "results": results})
        all_results.extend(results)

    return {
        "title": title,
        "normalized_title": normalized_title,
        "queries": query_reports,
        "min_score": min_score,
        "top_n": top_n,
        "conclusion": classify_conclusion(all_results),
    }


def fetch_issue(issue_number: int, repo: str = DEFAULT_REPO) -> tuple[str, str]:
    """Fetch an issue through gh without using the search CLI or its quota."""
    try:
        completed = subprocess.run(
            ["gh", "api", f"repos/{repo}/issues/{issue_number}"],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("找不到 gh；請安裝 GitHub CLI，或改用 --title 離線執行。") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "GitHub API 查詢失敗").strip()
        raise RuntimeError(detail) from exc

    try:
        payload = json.loads(completed.stdout)
        return str(payload["title"]), str(payload.get("body") or "")
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise RuntimeError("GitHub API 回傳缺少 issue title/body。") from exc


def format_human(report: dict[str, Any]) -> str:
    """Render the same information as the JSON report for terminal users."""
    lines = [
        f"標題：{report['title']}",
        f"規範化：{report['normalized_title']}",
        f"門檻：{report['min_score']:.3f}（top-{report['top_n']}）",
    ]
    for index, query_report in enumerate(report["queries"], start=1):
        lines.append("")
        lines.append(f"Query {index}：{query_report['query']}")
        if not query_report["results"]:
            lines.append("  （沒有結果）")
            continue
        for result in query_report["results"]:
            marker = "✓" if result["meets_threshold"] else "·"
            lines.append(
                f"  {marker} {result['id']} [{result['type']}] "
                f"score={result['score']:.3f} — {result['title']}"
            )
    lines.extend(["", f"結論：{report['conclusion']}"])
    return "\n".join(lines)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Normalize an intake title and check local lesson coverage."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--issue", type=int, help="Fetch title/body from a GitHub issue number.")
    source.add_argument("--title", help="Use this title directly; no GitHub request is made.")
    parser.add_argument(
        "--body", default="", help="Optional body for --title mode and offline tests."
    )
    parser.add_argument(
        "--repo",
        default=DEFAULT_REPO,
        help=f"GitHub repository for --issue (default: {DEFAULT_REPO}).",
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=DEFAULT_MIN_SCORE,
        help="Coverage score threshold (default: 0.40).",
    )
    parser.add_argument(
        "--top-n", type=int, default=DEFAULT_TOP_N, help="Results retained per query (default: 5)."
    )
    parser.add_argument("--json", action="store_true", help="Emit the report as JSON.")
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.min_score < 0:
        parser.error("--min-score must be non-negative")
    if args.top_n < 1:
        parser.error("--top-n must be at least 1")

    try:
        if args.issue is not None:
            title, body = fetch_issue(args.issue, args.repo)
        else:
            title, body = args.title or "", args.body
        if not title.strip():
            parser.error("title 不能為空")
        report = analyze(title, body, min_score=args.min_score, top_n=args.top_n)
    except RuntimeError as exc:
        print(f"錯誤：{exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(format_human(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
