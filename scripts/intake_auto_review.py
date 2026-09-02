#!/usr/bin/env python3
"""Intake auto-review engine.

Multi-dimensional scoring for intake issues:
- completeness: problem/error/fix sections present
- generalization: not specific to one user/environment
- verification: has verification steps/results
- detail: word count, code blocks, error messages
- format: proper markdown structure

Decision thresholds:
- score >= 80 → auto-approve (create lesson PR)
- 50 <= score < 80 → needs human review
- score < 50 → auto-reject

Usage:
    python3 scripts/intake_auto_review.py --issue 1170 --body "..."
    python3 scripts/intake_auto_review.py --file issue_body.txt
    python3 scripts/intake_auto_review.py --json '{"body": "...", "issue_number": 1170}'
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Import the existing validate_intake function
sys.path.insert(0, str(Path(__file__).parent))
from validate_intake import validate_intake, ValidationResult


# === Scoring Weights ===
DIMENSION_WEIGHTS = {
    "completeness": 0.20,   # Required sections present
    "generalization": 0.15, # Not specific to one user/env
    "verification": 0.30,   # Has verification steps (most important)
    "detail": 0.15,         # Sufficient detail
    "format": 0.10,         # Proper markdown structure
    "uniqueness": 0.10,     # Not duplicate content
}

# === Decision Thresholds (可被环境变量覆盖) ===
THRESHOLD_APPROVE = int(os.environ.get("MISAKANET_THRESHOLD_APPROVE", "75"))
THRESHOLD_REVIEW = int(os.environ.get("MISAKANET_THRESHOLD_REVIEW", "40"))


@dataclass
class DimensionScore:
    """Score for a single dimension."""
    name: str
    score: float  # 0-100
    weight: float
    reasons: list[str] = field(default_factory=list)


@dataclass
class AutoReviewResult:
    """Complete auto-review result."""
    issue_number: int = 0
    intake_score: int = 0  # From validate_intake.py
    dimensions: list[DimensionScore] = field(default_factory=list)
    weighted_score: float = 0.0
    confidence: float = 0.7  # Base confidence
    final_score: float = 0.0
    decision: str = "review"  # approve | review | reject
    reasons: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    lesson_title: str = ""
    lesson_domain: str = "general"
    lesson_tags: list[str] = field(default_factory=list)

    def __post_init__(self):
        self.confidence = max(0.0, min(1.0, self.confidence))


# === Dimension Scorers ===

def score_completeness(body: str, sections: dict[str, str]) -> DimensionScore:
    """Score field completeness (0-100)."""
    score = 0
    reasons = []

    # Required fields - check both section headers and body content
    required = {
        "problem": (
            "## Problem" in body or "## 问题" in body or
            "## 背景" in body or "## Background" in body
        ),
        "error": (
            "error" in body.lower() or "exception" in body.lower() or
            "traceback" in body.lower() or "失败" in body or
            "403" in body or "timeout" in body.lower() or
            "错误" in body or "异常" in body or
            "误判" in body or "漏召回" in body
        ),
        "fix": (
            "## Fix" in body or "## Solution" in body or
            "## 修复" in body or "## What was tried" in body or
            "harvested from" in body.lower() or
            "## Fix (if known)" in body
        ),
    }

    for field_name, present in required.items():
        if present:
            score += 25
            reasons.append(f"✓ {field_name} present")
        else:
            reasons.append(f"✗ {field_name} missing")

    # Bonus for recommended sections
    recommended = {
        "verification": (
            "## Verification" in body or "## 验证" in body or
            "验证" in body
        ),
        "background": (
            "## Background" in body or "## 背景" in body
        ),
        "root_cause": (
            "## Root Cause" in body or "## 根因" in body
        ),
    }

    bonus = 0
    for field_name, present in recommended.items():
        if present:
            bonus += 5
            reasons.append(f"✓ {field_name} present (bonus)")

    score = min(100, score + bonus)
    return DimensionScore(
        name="completeness",
        score=score,
        weight=DIMENSION_WEIGHTS["completeness"],
        reasons=reasons,
    )


def score_generalization(body: str, sections: dict[str, str]) -> DimensionScore:
    """Score how generalizable the lesson is (0-100)."""
    score = 30  # Start lower - need to earn points
    reasons = []

    # Check for user-specific paths (negative)
    user_paths = [
        r"/home/\w+/",
        r"/Users/\w+/",
        r"C:\\Users\\",
        r"~/",
    ]
    has_user_paths = any(re.search(p, body) for p in user_paths)
    if has_user_paths:
        score -= 15
        reasons.append("✗ Contains user-specific paths")
    else:
        score += 15
        reasons.append("✓ No user-specific paths")

    # Check for internal tools (negative)
    internal_patterns = [
        r"xiaomi",
        r"mify",
        r"internal",
        r"公司内部",
        r"内网",
    ]
    has_internal = any(re.search(p, body, re.IGNORECASE) for p in internal_patterns)
    if has_internal:
        score -= 15
        reasons.append("✗ Contains internal references")
    else:
        score += 10
        reasons.append("✓ No internal references")

    # Check for generic keywords (positive)
    generic_keywords = [
        "github", "git", "python", "node", "npm", "pip",
        "docker", "kubernetes", "ci/cd", "linux", "windows",
        "api", "database", "ssh", "curl", "error", "timeout",
    ]
    keyword_count = sum(1 for kw in generic_keywords if kw in body.lower())
    if keyword_count >= 5:
        score += 20
        reasons.append(f"✓ {keyword_count} generic tech keywords")
    elif keyword_count >= 3:
        score += 10
        reasons.append(f"✓ {keyword_count} generic tech keywords")
    else:
        reasons.append(f"✗ Only {keyword_count} generic tech keywords")

    # Check for multiple environments (positive)
    env_patterns = [
        r"ubuntu|debian|centos",
        r"macos|darwin",
        r"windows|wsl",
        r"python\s*\d",
        r"node\s*v?\d",
    ]
    env_count = sum(1 for p in env_patterns if re.search(p, body, re.IGNORECASE))
    if env_count >= 2:
        score += 15
        reasons.append(f"✓ {env_count} environments mentioned")
    elif env_count >= 1:
        score += 5
        reasons.append(f"✓ {env_count} environment mentioned")

    # Check for specific project names (negative - reduces generalizability)
    project_names = [
        r"self-grow-wiki",
        r"misakanet",
        r"hermes",
        r"codewhale",
    ]
    has_project = any(re.search(p, body, re.IGNORECASE) for p in project_names)
    if has_project:
        score -= 10
        reasons.append("✗ Contains specific project names")

    return DimensionScore(
        name="generalization",
        score=max(0, min(100, score)),
        weight=DIMENSION_WEIGHTS["generalization"],
        reasons=reasons,
    )


def score_verification(body: str, sections: dict[str, str]) -> DimensionScore:
    """Score verification quality (0-100)."""
    score = 0
    reasons = []

    # Check for verification section in both sections dict and body
    has_verification = (
        any("verification" in name.lower() or "验证" in name.lower()
            for name in sections) or
        "## Verification" in body or
        "## 验证" in body
    )

    if has_verification:
        score += 20  # Base score for having section
        reasons.append("✓ Verification section present")

        # Get verification content from sections or extract from body
        verification_content = ""
        for name, content in sections.items():
            if "verification" in name.lower() or "验证" in name.lower():
                verification_content = content
                break

        # If section content is empty, try to extract from body
        if not verification_content:
            # Find content between ## Verification and next section or end
            match = re.search(
                r"##\s*(?:Verification|验证)\s*\n((?:(?!\n##).)*)",
                body,
                re.DOTALL | re.IGNORECASE
            )
            if match:
                verification_content = match.group(1)

        # Has executable commands
        if re.search(r"```(bash|sh|shell|console)", verification_content):
            score += 25
            reasons.append("✓ Has executable commands in verification")
        elif re.search(r"^\s*\$\s+", verification_content, re.MULTILINE):
            score += 20
            reasons.append("✓ Has shell commands in verification")

        # Has expected results
        if re.search(r"expected|output|result|成功|通过", verification_content, re.IGNORECASE):
            score += 20
            reasons.append("✓ Has expected results")

        # Has verification steps
        if re.search(r"^\s*[-*]\s+", verification_content, re.MULTILINE):
            score += 15
        reasons.append("✓ Has verification steps (list)")
    else:
        # Check if verification is mentioned anywhere in body
        if re.search(r"verified|验证|确认|测试通过", body, re.IGNORECASE):
            score += 15
            reasons.append("✓ Verification mentioned (no dedicated section)")
        else:
            reasons.append("✗ No verification section")

    # Check for verification mentions anywhere in body (not just section)
    if re.search(r"验证通过|verified|确认.*落地|确认.*成功|no leaks found", body, re.IGNORECASE):
        score += 15
        reasons.append("✓ Verification results mentioned in body")

    return DimensionScore(
        name="verification",
        score=min(100, score),
        weight=DIMENSION_WEIGHTS["verification"],
        reasons=reasons,
    )


def score_uniqueness(body: str, sections: dict[str, str], lesson_title: str = "") -> DimensionScore:
    """Score content uniqueness and novelty (0-100)."""
    score = 50  # Start at neutral
    reasons = []

    # Check for common duplicate topics
    duplicate_topics = [
        (r"DCO.*signoff|Signed-off-by", "DCO/signoff"),
        (r"force.with.lease", "force-with-lease"),
        (r"BM25.*RRF|hybrid.*search", "BM25/hybrid search"),
        (r"mcp.*intake|MCP.*submit", "MCP intake"),
    ]

    topic_matches = []
    for pattern, topic_name in duplicate_topics:
        if re.search(pattern, body, re.IGNORECASE):
            topic_matches.append(topic_name)

    if len(topic_matches) > 1:
        score -= 30
        reasons.append(f"[X] Covers multiple common topics: {', '.join(topic_matches)}")
    elif len(topic_matches) == 1:
        score -= 10
        reasons.append(f"[!] Common topic: {topic_matches[0]}")

    # Check for unique value propositions
    unique_indicators = [
        r"novel|unique|first.time|new approach|different from",
        r"unlike.*existing|compared to|alternatives",
        r"edge case|rare|uncommon|specific scenario",
    ]

    has_unique = any(re.search(p, body, re.IGNORECASE) for p in unique_indicators)
    if has_unique:
        score += 20
        reasons.append("[OK] Contains unique value proposition")

    # Check for references to existing lessons (good practice)
    if re.search(r"related.*lesson|see also|similar to|extends", body, re.IGNORECASE):
        score += 10
        reasons.append("[OK] References related lessons")

    return DimensionScore(
        name="uniqueness",
        score=min(100, max(0, score)),
        weight=DIMENSION_WEIGHTS["uniqueness"],
        reasons=reasons,
    )

    # Check for test mentions in body
    if re.search(r"test|测试|verified", body, re.IGNORECASE):
        score += 10
        reasons.append("✓ Test/verification mentioned in body")

    return DimensionScore(
        name="verification",
        score=max(0, min(100, score)),
        weight=DIMENSION_WEIGHTS["verification"],
        reasons=reasons,
    )


def score_detail(body: str, word_count: int) -> DimensionScore:
    """Score detail level (0-100)."""
    score = 0
    reasons = []

    # Word count
    if word_count >= 300:
        score += 30
        reasons.append(f"✓ Excellent word count: {word_count}")
    elif word_count >= 150:
        score += 25
        reasons.append(f"✓ Good word count: {word_count}")
    elif word_count >= 100:
        score += 20
        reasons.append(f"✓ Adequate word count: {word_count}")
    elif word_count >= 50:
        score += 10
        reasons.append(f"⚠ Short word count: {word_count}")
    else:
        reasons.append(f"✗ Very short word count: {word_count}")

    # Code blocks
    code_blocks = re.findall(r"```(?:(?!```).)*```", body, flags=re.DOTALL)
    if len(code_blocks) >= 3:
        score += 25
        reasons.append(f"✓ {len(code_blocks)} code blocks (excellent)")
    elif len(code_blocks) >= 2:
        score += 20
        reasons.append(f"✓ {len(code_blocks)} code blocks (good)")
    elif len(code_blocks) >= 1:
        score += 15
        reasons.append(f"✓ {len(code_blocks)} code block")
    else:
        reasons.append("✗ No code blocks")

    # Error messages - more flexible patterns
    error_patterns = [
        r"Error:",
        r"Exception:",
        r"Traceback",
        r"FAILED",
        r"error\[",
        r"fatal:",
        r"403",
        r"404",
        r"500",
        r"timeout",
        r"连接",
        r"凭证",
        r"hook",
    ]
    error_count = sum(1 for p in error_patterns if re.search(p, body, re.IGNORECASE))
    if error_count >= 3:
        score += 25
        reasons.append(f"✓ {error_count} error patterns (excellent)")
    elif error_count >= 2:
        score += 20
        reasons.append(f"✓ {error_count} error patterns")
    elif error_count >= 1:
        score += 10
        reasons.append(f"✓ {error_count} error pattern")
    else:
        reasons.append("✗ No error messages")

    # Technical depth indicators
    tech_indicators = [
        r"stack\s*trace",
        r"debug",
        r"log",
        r"config",
        r"env\s*var",
        r"environment",
        r"version",
        r"dependency",
        r"推送",
        r"commit",
        r"branch",
        r"merge",
        r"rebase",
    ]
    tech_count = sum(1 for p in tech_indicators if re.search(p, body, re.IGNORECASE))
    if tech_count >= 4:
        score += 20
        reasons.append(f"✓ {tech_count} technical depth indicators")
    elif tech_count >= 2:
        score += 10
        reasons.append(f"✓ {tech_count} technical depth indicators")

    return DimensionScore(
        name="detail",
        score=max(0, min(100, score)),
        weight=DIMENSION_WEIGHTS["detail"],
        reasons=reasons,
    )


def score_format(body: str, sections: dict[str, str]) -> DimensionScore:
    """Score format quality (0-100)."""
    score = 0
    reasons = []

    # Headers
    headers = re.findall(r"^#{1,4}\s+.+", body, re.MULTILINE)
    if len(headers) >= 4:
        score += 30
        reasons.append(f"✓ {len(headers)} headers (excellent)")
    elif len(headers) >= 3:
        score += 25
        reasons.append(f"✓ {len(headers)} headers (good)")
    elif len(headers) >= 2:
        score += 15
        reasons.append(f"✓ {len(headers)} headers")
    elif len(headers) >= 1:
        score += 5
        reasons.append(f"✓ {len(headers)} header")
    else:
        reasons.append("✗ No headers")

    # Lists
    list_items = re.findall(r"^[\s]*[-*]\s+.+", body, re.MULTILINE)
    if len(list_items) >= 5:
        score += 25
        reasons.append(f"✓ {len(list_items)} list items (excellent)")
    elif len(list_items) >= 3:
        score += 20
        reasons.append(f"✓ {len(list_items)} list items")
    elif len(list_items) >= 1:
        score += 10
        reasons.append(f"✓ {len(list_items)} list item")
    else:
        reasons.append("✗ No lists")

    # JSON frontmatter
    if body.strip().startswith("{"):
        try:
            json.loads(body.split("\n\n")[0])
            score += 20
            reasons.append("✓ Valid JSON frontmatter")
        except (json.JSONDecodeError, IndexError):
            reasons.append("✗ Invalid JSON frontmatter")
    elif body.strip().startswith("---"):
        score += 15
        reasons.append("✓ YAML frontmatter")
    else:
        reasons.append("✗ No frontmatter")

    # Code blocks with language tags
    tagged_blocks = re.findall(r"```(\w+)", body)
    if tagged_blocks:
        score += 15
        reasons.append(f"✓ {len(tagged_blocks)} code blocks with language tags")

    # Tables
    if re.search(r"\|.+\|.+\|", body):
        score += 10
        reasons.append("✓ Contains tables")

    return DimensionScore(
        name="format",
        score=max(0, min(100, score)),
        weight=DIMENSION_WEIGHTS["format"],
        reasons=reasons,
    )


# === Confidence Calculator ===

def calculate_confidence(body: str, is_test: bool) -> float:
    """Calculate confidence in the scoring (0.0-1.0)."""
    confidence = 0.7  # Base confidence

    # Has code blocks
    if re.search(r"```", body):
        confidence += 0.1

    # Has error stacktrace
    if re.search(r"Traceback|stack\s*trace", body, re.IGNORECASE):
        confidence += 0.1

    # Has verification steps
    if re.search(r"##\s*(Verification|验证)", body):
        confidence += 0.1

    # Not a test issue
    if not is_test:
        confidence += 0.05

    # Has substantial content (>200 words)
    word_count = len(re.findall(r"\b\w+\b", body))
    if word_count >= 200:
        confidence += 0.05

    return min(1.0, confidence)


# === Decision Maker ===

def make_decision(final_score: float, confidence: float) -> str:
    """Make approve/review/reject decision."""
    # Adjust thresholds based on confidence
    adjusted_approve = THRESHOLD_APPROVE * confidence
    adjusted_review = THRESHOLD_REVIEW * confidence

    if final_score >= adjusted_approve:
        return "approve"
    elif final_score >= adjusted_review:
        return "review"
    else:
        return "reject"


# === Lesson Generator ===

def generate_lesson_from_intake(
    issue_number: int,
    title: str,
    body: str,
    sections: dict[str, str],
) -> tuple[str, str, list[str]]:
    """Generate lesson content from intake issue.

    Returns: (lesson_title, domain, tags)
    """
    # Extract title from issue
    lesson_title = title.replace("[Intake]", "").strip()
    if not lesson_title:
        lesson_title = f"lesson-from-issue-{issue_number}"

    # Clean title for filename
    lesson_title = re.sub(r"[^\w\s-]", "", lesson_title)
    lesson_title = re.sub(r"\s+", "-", lesson_title.lower())

    # Determine domain from content
    domain = "general"
    domain_keywords = {
        "git": ["git", "github", "commit", "push", "pull"],
        "python": ["python", "pip", "pylint", "pytest"],
        "node": ["node", "npm", "yarn", "javascript"],
        "docker": ["docker", "container", "image"],
        "ci-cd": ["ci/cd", "github actions", "workflow", "pipeline"],
        "mcp": ["mcp", "model context protocol"],
        "rag": ["rag", "retrieval", "embedding", "vector"],
    }

    body_lower = body.lower()
    for dom, keywords in domain_keywords.items():
        if any(kw in body_lower for kw in keywords):
            domain = dom
            break

    # Extract tags from content
    tags = []
    tag_patterns = [
        r"git", r"python", r"node", r"docker", r"ci/cd",
        r"mcp", r"rag", r"api", r"database", r"ssh",
        r"error", r"timeout", r"performance", r"security",
    ]
    for pattern in tag_patterns:
        if re.search(pattern, body_lower):
            tags.append(pattern.replace("/", "-"))

    # Ensure at least 3 tags
    if len(tags) < 3:
        tags.extend(["debugging", "troubleshooting", "lesson"][:3 - len(tags)])

    return lesson_title, domain, tags[:10]


# === Main Review Function ===

def auto_review_issue(
    issue_number: int,
    title: str,
    body: str,
    is_test: bool = False,
) -> AutoReviewResult:
    """Perform auto-review on an intake issue.

    Args:
        issue_number: GitHub issue number
        title: Issue title
        body: Issue body text
        is_test: Whether this is a test issue

    Returns:
        AutoReviewResult with scores and decision
    """
    result = AutoReviewResult(issue_number=issue_number)

    # Step 1: Get intake validation score
    validation = validate_intake(body)
    result.intake_score = validation.quality_score

    # Step 2: Extract sections
    sections = {}
    current_section = None
    current_content = []

    for line in body.split("\n"):
        header_match = re.match(r"^#{1,4}\s+(.+)", line)
        if header_match:
            if current_section:
                sections[current_section.lower()] = "\n".join(current_content).strip()
            current_section = header_match.group(1).strip()
            current_content = []
        else:
            current_content.append(line)

    if current_section:
        sections[current_section.lower()] = "\n".join(current_content).strip()

    # Step 3: Count words
    word_count = len(re.findall(r"\b\w+\b", body))

    # Step 4: Score each dimension
    result.dimensions = [
        score_completeness(body, sections),
        score_generalization(body, sections),
        score_verification(body, sections),
        score_detail(body, word_count),
        score_format(body, sections),
        score_uniqueness(body, sections, result.lesson_title),
    ]

    # Step 5: Calculate weighted score
    result.weighted_score = sum(
        dim.score * dim.weight for dim in result.dimensions
    )

    # Step 6: Calculate confidence
    result.confidence = calculate_confidence(body, is_test)

    # Step 7: Calculate final score
    result.final_score = result.weighted_score * result.confidence

    # Step 8: Make decision
    result.decision = make_decision(result.final_score, result.confidence)

    # Step 9: Collect reasons and suggestions
    for dim in result.dimensions:
        result.reasons.extend(dim.reasons)
    result.suggestions = validation.suggestions

    # Step 10: Generate lesson metadata
    result.lesson_title, result.lesson_domain, result.lesson_tags = (
        generate_lesson_from_intake(issue_number, title, body, sections)
    )

    return result


# === Output Formatting ===

def format_result_json(result: AutoReviewResult) -> str:
    """Format result as JSON."""
    return json.dumps({
        "issue_number": result.issue_number,
        "intake_score": result.intake_score,
        "dimensions": {
            dim.name: {
                "score": dim.score,
                "weight": dim.weight,
                "reasons": dim.reasons,
            }
            for dim in result.dimensions
        },
        "weighted_score": result.weighted_score,
        "confidence": result.confidence,
        "final_score": result.final_score,
        "decision": result.decision,
        "reasons": result.reasons,
        "suggestions": result.suggestions,
        "lesson_title": result.lesson_title,
        "lesson_domain": result.lesson_domain,
        "lesson_tags": result.lesson_tags,
    }, indent=2)


def format_result_comment(result: AutoReviewResult) -> str:
    """Format result as GitHub comment."""
    lines = []

    if result.decision == "approve":
        lines.append("## [APPROVED] Auto-Approved — Lesson Created\n")
    elif result.decision == "review":
        lines.append("## [REVIEW] Needs Human Review\n")
    else:
        lines.append("## [REJECTED] Auto-Rejected\n")

    # Score summary
    lines.append("### Score Summary\n")
    lines.append(f"| Metric | Score |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Intake Validation | {result.intake_score}/100 |")
    lines.append(f"| Weighted Score | {result.weighted_score:.1f}/100 |")
    lines.append(f"| Confidence | {result.confidence:.0%} |")
    lines.append(f"| **Final Score** | **{result.final_score:.1f}/100** |")
    lines.append("")

    # Dimension breakdown
    lines.append("### Dimension Breakdown\n")
    lines.append(f"| Dimension | Weight | Score | Weighted |")
    lines.append(f"|-----------|--------|-------|----------|")
    for dim in result.dimensions:
        weighted = dim.score * dim.weight
        lines.append(f"| {dim.name} | {dim.weight:.0%} | {dim.score:.0f} | {weighted:.1f} |")
    lines.append("")

    # Decision
    if result.decision == "approve":
        lines.append(f"**Decision:** Auto-approved (score >= {THRESHOLD_APPROVE})")
        lines.append(f"\nLesson will be created in `lessons/contrib/` directory.")
    elif result.decision == "review":
        lines.append(f"**Decision:** Needs review ({THRESHOLD_REVIEW} <= score < {THRESHOLD_APPROVE})")
        lines.append(f"\nMaintainer please review and decide:")
        lines.append(f"- Approve: convert to lesson")
        lines.append(f"- Improve: request changes")
        lines.append(f"- Reject: close issue")
    else:
        lines.append(f"**Decision:** Auto-rejected (score < {THRESHOLD_REVIEW})")
        lines.append(f"\n**Rejection Reasons:**")
        for reason in [r for r in result.reasons if r.startswith("✗")]:
            lines.append(f"- {reason}")

    # Suggestions
    if result.suggestions:
        lines.append(f"\n### Suggestions\n")
        for suggestion in result.suggestions[:5]:
            lines.append(f"- {suggestion}")

    return "\n".join(lines)


# === Archiving Functions ===

def get_archive_paths(issue_number: int) -> dict[str, Path]:
    """Get archive paths for an issue.

    Returns dict with keys: confidence_judgment, badcase, intake_md, metadata_json
    """
    base_dir = Path(__file__).parent.parent

    confidence_dir = base_dir / "confidence-judgment" / str(issue_number)
    badcase_dir = base_dir / "badcase" / str(issue_number)

    return {
        "confidence_judgment": confidence_dir,
        "badcase": badcase_dir,
        "intake_md": "intake.md",
        "metadata_json": "metadata.json",
        "reasons_md": "reasons.md",
        "feedback_md": "feedback.md",
    }


def create_archive_files(
    result: AutoReviewResult,
    title: str,
    body: str,
) -> dict[str, str]:
    """Create archive files for review/reject decisions.

    Returns dict with keys: archive_path, archive_type, files_created
    """
    paths = get_archive_paths(result.issue_number)
    files_created = []

    if result.decision == "review":
        archive_dir = paths["confidence_judgment"]
        archive_type = "confidence-judgment"
    elif result.decision == "reject":
        archive_dir = paths["badcase"]
        archive_type = "badcase"
    else:
        return {"archive_path": "", "archive_type": "", "files_created": []}

    # Create directory
    archive_dir.mkdir(parents=True, exist_ok=True)

    # Create intake.md
    intake_path = archive_dir / paths["intake_md"]
    intake_content = f"""---
issue_number: {result.issue_number}
title: "{title}"
score: {result.final_score}
decision: {result.decision}
created_at: "{__import__('datetime').datetime.utcnow().isoformat()}Z"
---

# {title}

{body}
"""
    intake_path.write_text(intake_content, encoding="utf-8")
    files_created.append(str(intake_path))

    # Create metadata.json
    metadata_path = archive_dir / paths["metadata_json"]
    metadata = {
        "issue_number": result.issue_number,
        "title": title,
        "intake_score": result.intake_score,
        "dimensions": {
            dim.name: {
                "score": dim.score,
                "weight": dim.weight,
                "weighted": dim.score * dim.weight,
                "reasons": dim.reasons,
            }
            for dim in result.dimensions
        },
        "weighted_score": result.weighted_score,
        "confidence": result.confidence,
        "final_score": result.final_score,
        "decision": result.decision,
        "reasons": result.reasons,
        "suggestions": result.suggestions,
        "lesson_title": result.lesson_title,
        "lesson_domain": result.lesson_domain,
        "lesson_tags": result.lesson_tags,
        "created_at": __import__('datetime').datetime.utcnow().isoformat() + "Z",
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    files_created.append(str(metadata_path))

    # Create reasons.md for rejected issues
    if result.decision == "reject":
        reasons_path = archive_dir / paths["reasons_md"]
        reasons_content = f"""# Rejection Reasons

## Issue #{result.issue_number}: {title}

**Score:** {result.final_score}/100
**Decision:** Auto-rejected

## Reasons

"""
        for reason in [r for r in result.reasons if r.startswith("✗")]:
            reasons_content += f"- {reason}\n"

        reasons_content += f"""
## Suggestions for Improvement

"""
        for suggestion in result.suggestions:
            reasons_content += f"- {suggestion}\n"

        reasons_path.write_text(reasons_content, encoding="utf-8")
        files_created.append(str(reasons_path))

    # Create feedback.md template for review issues
    if result.decision == "review":
        feedback_path = archive_dir / paths["feedback_md"]
        feedback_content = f"""# Feedback

## Issue #{result.issue_number}: {title}

**Score:** {result.final_score}/100
**Status:** Pending review

## Feedback Log

<!-- Add feedback entries below -->

| Date | User | Action | Notes |
|------|------|--------|-------|
| | | | |

## Re-evaluation History

<!-- Will be populated when re-evaluated -->

| Date | Old Score | New Score | Trigger |
|------|-----------|-----------|---------|
| | | | |
"""
        feedback_path.write_text(feedback_content, encoding="utf-8")
        files_created.append(str(feedback_path))

    return {
        "archive_path": str(archive_dir),
        "archive_type": archive_type,
        "files_created": files_created,
    }


def update_index_file(archive_type: str, result: AutoReviewResult, title: str) -> None:
    """Update the index.json file for the archive type."""
    base_dir = Path(__file__).parent.parent

    if archive_type == "confidence-judgment":
        index_path = base_dir / "confidence-judgment" / "index.json"
    elif archive_type == "badcase":
        index_path = base_dir / "badcase" / "index.json"
    else:
        return

    # Load existing index or create new
    if index_path.exists():
        index = json.loads(index_path.read_text(encoding="utf-8"))
    else:
        index = {
            "version": "1.0",
            "last_updated": "",
            "items": [],
            "stats": {"total": 0},
        }

    # Add new item
    item = {
        "issue_number": result.issue_number,
        "title": title,
        "score": result.final_score,
        "confidence": result.confidence,
        "created_at": __import__('datetime').datetime.utcnow().isoformat() + "Z",
        "status": "pending",
        "feedback_count": 0,
    }

    if archive_type == "badcase":
        item["category"] = categorize_rejection(result)
        item["rejection_reasons"] = [r for r in result.reasons if r.startswith("✗")]

    index["items"].append(item)
    index["last_updated"] = __import__('datetime').datetime.utcnow().isoformat() + "Z"
    index["stats"]["total"] = len(index["items"])

    if archive_type == "badcase":
        # Count by category
        categories = {}
        for i in index["items"]:
            cat = i.get("category", "unknown")
            categories[cat] = categories.get(cat, 0) + 1
        index["stats"]["by_category"] = categories

    # Save index
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")


def categorize_rejection(result: AutoReviewResult) -> str:
    """Categorize why an issue was rejected."""
    reasons_text = " ".join(result.reasons).lower()

    if "very short word count" in reasons_text or "too short" in reasons_text:
        return "vague"
    elif "missing required field" in reasons_text:
        return "incomplete"
    elif "test" in reasons_text or "heartbeat" in reasons_text:
        return "test"
    elif "spam" in reasons_text or "promotional" in reasons_text:
        return "spam"
    else:
        return "incomplete"


# === CLI ===

def main():
    parser = argparse.ArgumentParser(description="Auto-review intake issues")
    parser.add_argument("--issue", "-i", type=int, help="Issue number")
    parser.add_argument("--title", "-t", help="Issue title")
    parser.add_argument("--body", "-b", help="Issue body text")
    parser.add_argument("--file", "-f", help="Read body from file")
    parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")
    parser.add_argument("--test", action="store_true", help="Mark as test issue")
    parser.add_argument("--archive", "-a", action="store_true",
                       help="Create archive files for review/reject decisions")
    parser.add_argument("--min-score", "-m", type=int, default=0,
                       help="Exit with error if score below threshold")

    args = parser.parse_args()

    # Get body text
    if args.file:
        body = Path(args.file).read_text(encoding="utf-8")
    elif args.body:
        body = args.body
    elif not sys.stdin.isatty():
        body = sys.stdin.read()
    else:
        parser.error("Provide body via --body, --file, or stdin")

    title = args.title or f"[Intake] Issue #{args.issue or 'unknown'}"
    issue_number = args.issue or 0

    # Run auto-review
    result = auto_review_issue(issue_number, title, body, args.test)

    # Create archive files if requested
    if args.archive and result.decision in ["review", "reject"]:
        archive_info = create_archive_files(result, title, body)
        update_index_file(archive_info["archive_type"], result, title)

        if not args.json:
            print(f"\n📁 Archived to: {archive_info['archive_path']}")
            print(f"   Files created: {len(archive_info['files_created'])}")

    # Output
    if args.json:
        output = json.loads(format_result_json(result))
        if args.archive and result.decision in ["review", "reject"]:
            output["archive"] = archive_info
        print(json.dumps(output, indent=2))
    else:
        print(format_result_comment(result))

    # Exit code based on decision
    if args.min_score > 0 and result.final_score < args.min_score:
        sys.exit(1)
    elif result.decision == "reject":
        sys.exit(1)


if __name__ == "__main__":
    main()
