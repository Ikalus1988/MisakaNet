#!/usr/bin/env python3
"""Intake content validation script (Issue #1252).

Validates intake issue content for quality, completeness, and format compliance.

Usage:
    python3 scripts/validate_intake.py <issue_body>
    python3 scripts/validate_intake.py --file issue_body.txt
    python3 scripts/validate_intake.py --json '{"problem": "...", "error": "...", "fix": "..."}'

Output:
    JSON with quality_score (0-100), issues list, and suggestions.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class ValidationResult:
    """Validation result with score and feedback."""
    quality_score: int = 0
    issues: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    fields_found: dict[str, bool] = field(default_factory=dict)
    word_count: int = 0
    has_code: bool = False
    has_error_msg: bool = False


# Required fields for a valid lesson
REQUIRED_FIELDS = ["problem", "error", "fix"]

# Optional but recommended fields
RECOMMENDED_FIELDS = ["background", "root cause", "verification", "steps", "environment"]

# Minimum word counts
MIN_WORDS_PROBLEM = 10
MIN_WORDS_FIX = 15
MIN_TOTAL_WORDS = 50

# Quality thresholds
QUALITY_WEIGHTS = {
    "completeness": 40,    # Has required fields
    "detail": 25,          # Sufficient word count
    "format": 15,          # Follows format guidelines
    "code_examples": 10,   # Has code/error examples
    "clarity": 10,         # Clear structure
}


def extract_sections(body: str) -> dict[str, str]:
    """Extract sections from markdown body."""
    sections = {}
    current_section = None
    current_content = []

    for line in body.split("\n"):
        # Check for headers
        header_match = re.match(r"^#{1,4}\s+(.+)", line)
        if header_match:
            # Save previous section
            if current_section:
                sections[current_section.lower()] = "\n".join(current_content).strip()
            current_section = header_match.group(1).strip()
            current_content = []
        else:
            current_content.append(line)

    # Save last section
    if current_section:
        sections[current_section.lower()] = "\n".join(current_content).strip()

    return sections


def count_words(text: str) -> int:
    """Count words in text, excluding code blocks."""
    # Remove code blocks
    text = re.sub(r"```(?:(?!```).)*```", "", text, flags=re.DOTALL)
    text = re.sub(r"`[^`]+`", "", text)
    # Split and count
    words = re.findall(r"\b\w+\b", text)
    return len(words)


def has_code_blocks(text: str) -> bool:
    """Check if text contains code blocks."""
    return bool(re.search(r"```(?:(?!```).)*```", text, flags=re.DOTALL) or re.search(r"`[^`]+`", text))


def has_error_patterns(text: str) -> bool:
    """Check if text contains error messages."""
    error_patterns = [
        r"Error:",
        r"Exception:",
        r"Traceback",
        r"FAILED",
        r"error\[",
        r"fatal:",
        r"errno",
        r"exit code",
    ]
    return any(re.search(p, text, re.IGNORECASE) for p in error_patterns)


def validate_completeness(sections: dict[str, str]) -> tuple[int, list[str], list[str]]:
    """Validate field completeness. Returns (score, issues, suggestions)."""
    score = 0
    issues = []
    suggestions = []

    # Check required fields
    for field_name in REQUIRED_FIELDS:
        found = False
        for section_name in sections:
            if field_name in section_name:
                found = True
                break
        if found:
            score += 10
        else:
            issues.append(f"Missing required field: {field_name}")
            suggestions.append(f"Add a '{field_name.title()}' section")

    # Check recommended fields (bonus)
    for field_name in RECOMMENDED_FIELDS:
        for section_name in sections:
            if field_name in section_name:
                score += 2
                break

    return min(score, QUALITY_WEIGHTS["completeness"]), issues, suggestions


def validate_detail(sections: dict[str, str], total_words: int) -> tuple[int, list[str], list[str]]:
    """Validate detail level. Returns (score, issues, suggestions)."""
    score = 0
    issues = []
    suggestions = []

    # Check total word count
    if total_words >= MIN_TOTAL_WORDS:
        score += 10
    else:
        issues.append(f"Too short: {total_words} words (minimum {MIN_TOTAL_WORDS})")
        suggestions.append("Add more detail to your explanation")

    # Check problem section length
    problem_text = ""
    for name, content in sections.items():
        if "problem" in name:
            problem_text = content
            break
    if problem_text:
        problem_words = count_words(problem_text)
        if problem_words >= MIN_WORDS_PROBLEM:
            score += 8
        else:
            issues.append(f"Problem section too short: {problem_words} words")
            suggestions.append("Describe the problem in more detail")

    # Check fix section length
    fix_text = ""
    for name, content in sections.items():
        if "fix" in name or "solution" in name:
            fix_text = content
            break
    if fix_text:
        fix_words = count_words(fix_text)
        if fix_words >= MIN_WORDS_FIX:
            score += 7
        else:
            issues.append(f"Fix section too short: {fix_words} words")
            suggestions.append("Explain the fix in more detail")

    return min(score, QUALITY_WEIGHTS["detail"]), issues, suggestions


def validate_format(body: str) -> tuple[int, list[str], list[str]]:
    """Validate format compliance. Returns (score, issues, suggestions)."""
    score = 0
    issues = []
    suggestions = []

    # Check for headers
    headers = re.findall(r"^#{1,4}\s+", body, re.MULTILINE)
    if headers:
        score += 5
    else:
        issues.append("No section headers found")
        suggestions.append("Use markdown headers to organize content")

    # Check for lists
    has_lists = bool(re.search(r"^[\s]*[-*]\s+", body, re.MULTILINE))
    if has_lists:
        score += 3

    # Check for code blocks
    if has_code_blocks(body):
        score += 4
    else:
        suggestions.append("Consider adding code examples or error messages")

    # Check for JSON frontmatter
    if body.strip().startswith("{"):
        try:
            json.loads(body.split("\n\n")[0])
            score += 3
        except json.JSONDecodeError:
            pass

    return min(score, QUALITY_WEIGHTS["format"]), issues, suggestions


def validate_code_examples(body: str) -> tuple[int, list[str], list[str]]:
    """Validate code examples. Returns (score, issues, suggestions)."""
    score = 0
    issues = []
    suggestions = []

    if has_code_blocks(body):
        score += 5
    else:
        suggestions.append("Add code snippets to illustrate the problem or fix")

    if has_error_patterns(body):
        score += 5
    else:
        suggestions.append("Include actual error messages or stack traces")

    return min(score, QUALITY_WEIGHTS["code_examples"]), issues, suggestions


def validate_clarity(sections: dict[str, str]) -> tuple[int, list[str], list[str]]:
    """Validate clarity and structure. Returns (score, issues, suggestions)."""
    score = 0
    issues = []
    suggestions = []

    # Check section count
    if len(sections) >= 3:
        score += 5
    elif len(sections) > 0:
        suggestions.append("Add more sections for better structure")

    # Check for empty sections (only if there are sections)
    if sections:
        empty_sections = [name for name, content in sections.items() if not content.strip()]
        if empty_sections:
            issues.append(f"Empty sections: {', '.join(empty_sections)}")
            suggestions.append("Fill in or remove empty sections")
        else:
            score += 5

    return min(score, QUALITY_WEIGHTS["clarity"]), issues, suggestions


def validate_intake(body: str) -> ValidationResult:
    """Validate intake issue content.

    Args:
        body: Issue body text (markdown)

    Returns:
        ValidationResult with score, issues, and suggestions
    """
    result = ValidationResult()

    # Extract sections
    sections = extract_sections(body)

    # Count words
    result.word_count = count_words(body)
    result.has_code = has_code_blocks(body)
    result.has_error_msg = has_error_patterns(body)

    # Track which fields were found
    for field_name in REQUIRED_FIELDS + RECOMMENDED_FIELDS:
        found = any(field_name in section_name for section_name in sections)
        result.fields_found[field_name] = found

    # Run validations
    completeness_score, completeness_issues, completeness_suggestions = validate_completeness(sections)
    detail_score, detail_issues, detail_suggestions = validate_detail(sections, result.word_count)
    format_score, format_issues, format_suggestions = validate_format(body)
    code_score, code_issues, code_suggestions = validate_code_examples(body)
    clarity_score, clarity_issues, clarity_suggestions = validate_clarity(sections)

    # Aggregate results
    result.quality_score = completeness_score + detail_score + format_score + code_score + clarity_score
    result.issues = completeness_issues + detail_issues + format_issues + code_issues + clarity_issues
    result.suggestions = completeness_suggestions + detail_suggestions + format_suggestions + code_suggestions + clarity_suggestions

    # Cap score at 100
    result.quality_score = min(100, max(0, result.quality_score))

    return result


def format_report(result: ValidationResult, output_json: bool = False) -> str:
    """Format validation result as report."""
    if output_json:
        return json.dumps({
            "quality_score": result.quality_score,
            "issues": result.issues,
            "suggestions": result.suggestions,
            "fields_found": result.fields_found,
            "word_count": result.word_count,
            "has_code": result.has_code,
            "has_error_msg": result.has_error_msg,
        }, indent=2)

    lines = []
    lines.append("=" * 50)
    lines.append("INTAKE VALIDATION REPORT")
    lines.append("=" * 50)
    lines.append(f"\nQuality Score: {result.quality_score}/100")
    lines.append(f"Word Count: {result.word_count}")

    if result.issues:
        lines.append("\n❌ Issues:")
        for issue in result.issues:
            lines.append(f"  - {issue}")

    if result.suggestions:
        lines.append("\n💡 Suggestions:")
        for suggestion in result.suggestions:
            lines.append(f"  - {suggestion}")

    lines.append("\n✅ Fields Found:")
    for field_name, found in result.fields_found.items():
        status = "✓" if found else "✗"
        lines.append(f"  {status} {field_name}")

    lines.append("\n" + "=" * 50)
    if result.quality_score >= 70:
        lines.append("✅ PASSED - Good quality intake")
    elif result.quality_score >= 50:
        lines.append("⚠️  NEEDS IMPROVEMENT - Consider adding more detail")
    else:
        lines.append("❌ FAILED - Please address the issues above")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Validate intake issue content")
    parser.add_argument("body", nargs="?", help="Issue body text")
    parser.add_argument("--file", "-f", help="Read body from file")
    parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")
    parser.add_argument("--min-score", "-m", type=int, default=0,
                       help="Exit with error if score below this threshold")

    args = parser.parse_args()

    # Get body text
    if args.file:
        body = Path(args.file).read_text(encoding="utf-8")
    elif args.body:
        body = args.body
    elif not sys.stdin.isatty():
        body = sys.stdin.read()
    else:
        parser.error("Provide body text via argument, --file, or stdin")

    # Validate
    result = validate_intake(body)

    # Output report
    print(format_report(result, args.json))

    # Exit with error if below threshold
    if args.min_score > 0 and result.quality_score < args.min_score:
        sys.exit(1)


if __name__ == "__main__":
    main()
