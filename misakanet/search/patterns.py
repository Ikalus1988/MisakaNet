"""Failure pattern extraction, signature indexing, and retrieval fusion.

Extracts normalized error signatures (templates, regexes, distinctive tokens)
from lesson corpora and provides pattern matching for search and intake gates.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_INDEX_PATH = REPO_ROOT / "data" / "failure_patterns.json"
PATTERNS_FILE = DEFAULT_INDEX_PATH

_FAILURE_PATTERNS_CACHE: dict[str, dict[str, Any]] | None = None

STOP_WORDS = {
    "error", "errors", "exception", "exceptions", "failed", "failure", "fatal",
    "traceback", "problem", "solution", "issue", "issues", "the", "and", "for",
    "with", "from", "this", "that", "was", "but", "not", "line", "path", "sha",
    "hex", "num", "url", "user", "got", "expected", "warning", "info", "debug",
    "when", "while", "after", "before", "into", "over", "under", "again", "then",
    "check", "checks", "test", "tests", "step", "steps", "file", "files"
}

ERROR_REGEX = re.compile(
    r"(?:(?:[A-Za-z_][\w.]*(?:Error|Exception|Failure|Fault|Fatal|Lock))"
    r"|(?:HTTP[^\n]{0,30}(?:4\d\d|5\d\d))"
    r"|(?:(?:status|code)\s*[:=]?\s*(?:4\d\d|5\d\d))"
    r"|(?:FAILED[^\n]{0,80})"
    r"|(?:fatal:\s*[^\n]{0,80})"
    r"|(?:Signed-off-by[^\n]{0,80})"
    r"|(?:ECONNRESET|ETIMEDOUT|ECONNREFUSED)"
    r"|(?:GitGuardian:[^\n]{0,100})"
    r"|(?:(?:database\s+is\s+locked|lock\s+timeout))"
    r"|(?:Skipping[^\n]{0,160}evaluated\s+to\s+false)"
    r"|(?:rejects?[^\n]{0,80}model\s+names?)"
    r"|(?:provider\s+prefix\s+for\s+custom\s+endpoints?))",
    re.I,
)


def normalize_error(text: str) -> str:
    """Normalize volatile execution variables in error text into static placeholders.

    Args:
        text: Raw error string or log line.

    Returns:
        Normalized string with volatile artifacts replaced by placeholders.
    """
    if not text:
        return ""
    result = text.strip()
    result = re.sub(r"https?://[^\s<>'\"]+", "<URL>", result)
    result = re.sub(r"[\w.+-]+@[\w-]+\.[\w.-]+", "<EMAIL>", result)
    result = re.sub(r"\b0x[0-9a-fA-F]+\b", "<HEX>", result)
    result = re.sub(r"(?:commit\s+|sha:?\s*)[0-9a-fA-F]{7,40}\b", "sha: <SHA>", result, flags=re.I)
    result = re.sub(r"\b[0-9a-fA-F]{16,64}\b", "<SHA>", result)
    result = re.sub(r"[a-zA-Z]:\\(?:[^\\/:*?\"<>|\r\n]+\\)*[^\\/:*?\"<>|\r\n]+", "<PATH>", result)
    result = re.sub(r"(?:/[a-zA-Z0-9_.-]+)+/[a-zA-Z0-9_.-]+", "<PATH>", result)
    result = re.sub(r"\bline\s+\d+\b", "line <NUM>", result, flags=re.I)
    result = re.sub(r":\d+(?::\d+)?\b", ":<NUM>", result)
    result = re.sub(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "<IP>", result)
    result = re.sub(r":\d{4,5}\b", ":<PORT>", result)
    result = re.sub(r"\b\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?\b", "<TIMESTAMP>", result)
    result = re.sub(r"\s+", " ", result)
    return result.strip()


def extract_key_tokens(text: str) -> list[str]:
    """Extract distinctive search tokens from an error string.

    Args:
        text: Error message or description text.

    Returns:
        Sorted unique list of meaningful error keywords.
    """
    if not text:
        return []
    normalized = text.lower()
    hyphenated = re.findall(r"\b[a-z0-9]+(?:-[a-z0-9]+)+\b", normalized)
    words = re.findall(r"\b[a-z][a-z0-9_]{2,}\b|[\u4e00-\u9fff]{2,}", normalized)
    combined = set(hyphenated + words)
    filtered = {w for w in combined if w not in STOP_WORDS and len(w) >= 3}
    return sorted(filtered)


def generate_regex_from_template(template: str) -> str:
    """Generate a compiled-safe regex string from a normalized template.

    Args:
        template: Normalized error template containing placeholders.

    Returns:
        Regular expression matching variants of the template.
    """
    escaped = re.escape(template)
    escaped = escaped.replace(r"\<SHA\>", r"[0-9a-fA-F]{7,40}")
    escaped = escaped.replace(r"\<HEX\>", r"(?:0x)?[0-9a-fA-F]+")
    escaped = escaped.replace(r"\<PATH\>", r"\S+")
    escaped = escaped.replace(r"\<NUM\>", r"\d+")
    escaped = escaped.replace(r"\<IP\>", r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}")
    escaped = escaped.replace(r"\<PORT\>", r"\d+")
    escaped = escaped.replace(r"\<URL\>", r"\S+")
    escaped = escaped.replace(r"\<EMAIL\>", r"\S+@\S+")
    escaped = escaped.replace(r"\<TIMESTAMP\>", r"\S+")
    return escaped


def _parse_frontmatter_patterns(content: str) -> list[str]:
    """Extract explicit failure_patterns list from YAML or JSON frontmatter."""
    m_yaml = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not m_yaml:
        return []
    header = m_yaml.group(1)
    patterns: list[str] = []
    in_fp = False
    for line in header.splitlines():
        trimmed = line.strip()
        if trimmed.startswith("failure_patterns:"):
            in_fp = True
            inline_val = trimmed[len("failure_patterns:"):].strip()
            if inline_val.startswith("[") and inline_val.endswith("]"):
                try:
                    vals = json.loads(inline_val)
                    if isinstance(vals, list):
                        patterns.extend([str(v).strip() for v in vals if v])
                except json.JSONDecodeError:
                    pass
            continue
        if in_fp:
            if trimmed.startswith("- "):
                val = trimmed[2:].strip().strip("\"'")
                if val:
                    patterns.append(val)
            elif trimmed and not trimmed.startswith("#"):
                in_fp = False
    return patterns


def extract_failure_patterns_from_markdown(
    content: str,
    title: str = "",
    lesson_id: str = "",
    domain: str = "",
) -> dict[str, Any]:
    """Extract failure pattern signatures from lesson markdown text.

    Args:
        content: Raw markdown text of the lesson.
        title: Title of the lesson.
        lesson_id: Unique slug or identifier of the lesson.
        domain: Domain categorization of the lesson.

    Returns:
        Dictionary containing templates, regexes, key tokens, and source metadata.
    """
    templates: list[str] = []
    regexes: list[str] = []
    tokens_collector: set[str] = set()

    for token in extract_key_tokens(title):
        tokens_collector.add(token)
    for token in extract_key_tokens(lesson_id):
        tokens_collector.add(token)

    fm_patterns = _parse_frontmatter_patterns(content)
    for fp in fm_patterns:
        norm_fp = normalize_error(fp)
        if norm_fp and norm_fp not in templates:
            templates.append(norm_fp)
        for t in extract_key_tokens(fp):
            tokens_collector.add(t)

    clean_content = content.replace("<!--", "\n").replace("-->", "\n")

    if title and ERROR_REGEX.search(title):
        norm_title = normalize_error(title)
        if norm_title and norm_title not in templates:
            templates.append(norm_title)

    quoted_errors = re.findall(
        r"[\x27\x22`]{1,3}([^\x27\x22`\n]{4,80})[\x27\x22`]{1,3}\s+(?:error|exception|failure|alert|warning|code)",
        clean_content,
        re.I,
    )
    for qe in quoted_errors:
        norm_qe = normalize_error(qe)
        if norm_qe and norm_qe not in templates and len(norm_qe) >= 5:
            templates.append(norm_qe)
        for t in extract_key_tokens(qe):
            tokens_collector.add(t)

    code_blocks = re.findall(r"```(?:[a-zA-Z0-9_-]*\n)?([\s\S]*?)```", clean_content)
    for block in code_blocks:
        for raw_line in block.splitlines():
            line = raw_line.strip()
            if not line or line.startswith(("$", "#", "echo", "cat", "git checkout", "git add", "git commit")):
                continue
            if len(line) > 260:
                continue
            if ERROR_REGEX.search(line):
                norm = normalize_error(line)
                if norm and norm not in templates:
                    templates.append(norm)
                for t in extract_key_tokens(line):
                    tokens_collector.add(t)

    sections = re.findall(
        r"##\s*(?:Error|Problem|Symptoms|Failure|Root Cause|报错|问题)[\s\S]*?(?=\n##|\Z)",
        clean_content,
        re.I,
    )
    for section in sections:
        for raw_line in section.splitlines():
            line = raw_line.strip()
            if not line or line.startswith(("#", "```", "---")):
                continue
            if ERROR_REGEX.search(line) and len(line) <= 260:
                norm = normalize_error(line)
                if norm and norm not in templates:
                    templates.append(norm)
                for t in extract_key_tokens(line):
                    tokens_collector.add(t)

    for tmpl in templates[:6]:
        rgx = generate_regex_from_template(tmpl)
        if rgx not in regexes:
            regexes.append(rgx)

    source = "frontmatter" if fm_patterns else "extracted"

    return {
        "id": lesson_id,
        "lesson_id": lesson_id,
        "title": title,
        "domain": domain,
        "templates": templates[:8],
        "regexes": regexes[:8],
        "key_tokens": sorted(tokens_collector)[:25],
        "source": source,
    }


def match_failure_pattern(query: str, pattern: dict[str, Any]) -> tuple[float, str | None]:
    """Calculate match confidence between an error query and a pattern record.

    Args:
        query: Query string containing an error or failure message.
        pattern: Failure pattern dictionary containing templates, regexes, and key tokens.

    Returns:
        Tuple of (confidence_score, matched_signature_description).
    """
    if not query or not pattern:
        return 0.0, None

    normalized_q = normalize_error(query)
    q_lower = query.lower()
    norm_q_lower = normalized_q.lower()

    for tmpl in pattern.get("templates", []):
        t_lower = tmpl.lower()
        if t_lower == norm_q_lower or t_lower == q_lower:
            return 1.0, tmpl
        if len(t_lower) >= 12 and (t_lower in norm_q_lower or t_lower in q_lower):
            return 0.95, tmpl
        if len(norm_q_lower) >= 12 and norm_q_lower in t_lower:
            return 0.90, tmpl

    for rgx in pattern.get("regexes", []):
        try:
            if re.search(rgx, query, re.I) or re.search(rgx, normalized_q, re.I):
                return 0.95, rgx
        except re.error:
            continue

    pat_tokens = set(pattern.get("key_tokens", []))
    if pat_tokens:
        q_tokens = set(extract_key_tokens(query))
        overlap = q_tokens & pat_tokens
        if len(overlap) >= 2:
            coverage = len(overlap) / min(len(q_tokens), len(pat_tokens))
            if coverage >= 0.7:
                return 0.85, " ".join(sorted(overlap))
            if coverage >= 0.35:
                return 0.75, " ".join(sorted(overlap))

    return 0.0, None


def load_failure_patterns(
    index_path: Path | str | None = None,
    force_reload: bool = False,
) -> dict[str, dict[str, Any]]:
    """Load the failure pattern index into memory with caching.

    Args:
        index_path: Optional filesystem path to failure_patterns.json.
        force_reload: Set true to bypass in-memory cache.

    Returns:
        Dictionary mapping lesson_id to failure pattern records.
    """
    global _FAILURE_PATTERNS_CACHE
    if _FAILURE_PATTERNS_CACHE is not None and not force_reload:
        return _FAILURE_PATTERNS_CACHE

    target_path = Path(index_path) if index_path else DEFAULT_INDEX_PATH
    if not target_path.exists():
        _FAILURE_PATTERNS_CACHE = {}
        return _FAILURE_PATTERNS_CACHE

    try:
        data = json.loads(target_path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            _FAILURE_PATTERNS_CACHE = {item["id"]: item for item in data if "id" in item}
        elif isinstance(data, dict):
            _FAILURE_PATTERNS_CACHE = data
        else:
            _FAILURE_PATTERNS_CACHE = {}
    except (OSError, json.JSONDecodeError):
        _FAILURE_PATTERNS_CACHE = {}

    return _FAILURE_PATTERNS_CACHE


def find_best_pattern_match(
    query: str,
    patterns: dict[str, dict[str, Any]] | None = None,
) -> tuple[str | None, float, str | None]:
    """Find the highest scoring lesson pattern match for a query.

    Args:
        query: Error string or log line to evaluate.
        patterns: Optional pattern mapping; loads default index when omitted.

    Returns:
        Tuple of (best_lesson_id, highest_score, matched_signature).
    """
    index = patterns if patterns is not None else load_failure_patterns()
    if not index or not query:
        return None, 0.0, None

    best_id: str | None = None
    best_score = 0.0
    best_match: str | None = None

    for lesson_id, pat in index.items():
        score, match_desc = match_failure_pattern(query, pat)
        if score > best_score:
            best_score = score
            best_id = lesson_id
            best_match = match_desc

    if best_score >= 0.70:
        return best_id, best_score, best_match

    return None, 0.0, None


def get_pattern_bonus(
    query: str,
    lesson_id: str,
    patterns: dict[str, dict[str, Any]] | None = None,
    content: str = "",
) -> tuple[float, str | None]:
    """Calculate ranking bonus score for a specific lesson against a query.

    Args:
        query: User search query or error string.
        lesson_id: Identifier of the document being evaluated.
        patterns: Optional preloaded patterns index.
        content: Optional raw lesson content for dynamic fallback matching.

    Returns:
        Tuple of (pattern_match_score, matched_signature_label).
    """
    index = patterns if patterns is not None else load_failure_patterns()
    record = index.get(lesson_id)
    if record:
        return match_failure_pattern(query, record)

    if content:
        dyn_pat = extract_failure_patterns_from_markdown(content, lesson_id=lesson_id)
        return match_failure_pattern(query, dyn_pat)

    return 0.0, None


def build_failure_patterns(
    lessons_dir: Path | str,
    output_path: Path | str | None = None,
) -> list[dict[str, Any]]:
    """Generate and persist the failure patterns sidecar index.

    Args:
        lessons_dir: Directory containing lesson markdown files.
        output_path: Target path for the generated JSON index.

    Returns:
        List of generated failure pattern dictionaries.
    """
    from misakanet.lesson_index import EXCLUDED_LESSON_FILES, canonical_lessons

    dir_path = Path(lessons_dir)
    target_out = Path(output_path) if output_path else DEFAULT_INDEX_PATH

    records: list[dict[str, Any]] = []

    for f in canonical_lessons(dir_path):
        if f.name.startswith(".") or f.name in EXCLUDED_LESSON_FILES:
            continue
        try:
            content = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        title_match = re.search(r"^title:\s*[\"']?([^\"'\n]+)[\"']?", content, re.M)
        title = title_match.group(1).strip() if title_match else f.stem
        domain_match = re.search(r"^domain:\s*[\"']?([^\"'\n]+)[\"']?", content, re.M)
        domain = domain_match.group(1).strip() if domain_match else f.parent.name

        pat = extract_failure_patterns_from_markdown(
            content=content,
            title=title,
            lesson_id=f.stem,
            domain=domain,
        )
        records.append(pat)

    target_out.parent.mkdir(parents=True, exist_ok=True)
    target_out.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    load_failure_patterns(target_out, force_reload=True)

    return records
