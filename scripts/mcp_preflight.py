#!/usr/bin/env python3
"""MisakaNet Preflight MCP Tool & Engine.

Evaluates high-risk agent intents, assigns risk profiles/levels, matches relevant lessons,
and injects risk-mitigation guards and checklists before execution.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# Risk Profiles & Default Rules
RISK_PROFILES = {
    "rag_build": {
        "name": "RAG build",
        "patterns": [
            r"\brag\b",
            r"\bembedding[s]?\b",
            r"\bvector[s]?\b",
            r"\bchroma\b",
            r"\bfaiss\b",
            r"\bindex\b",
            r"\bbuild_index\b",
            r"\bknowledge_base\b",
        ],
        "default_risk": "high",
        "guards": [
            "start with 3-5 sample PDFs before full batch",
            "set batch_size <= 8 to control VRAM usage",
            "write checkpoint every N documents",
            "monitor WSL memory via /proc/meminfo",
            "test resume from checkpoint before scaling",
            "abort if VRAM usage exceeds 90% or OOM kills occur",
        ],
        "default_recommendation": "run small-scale probe first, then scale",
        "lesson_hints": ["rag-build-strategy-batch", "chroma-rebuild-no-checkpoint-cn"],
    },
    "wsl_gpu_heavy": {
        "name": "WSL/GPU heavy",
        "patterns": [
            r"\bwsl\b",
            r"\bcuda\b",
            r"\bgpu\b",
            r"\bvram\b",
            r"\blm_studio\b",
            r"\bollama\b",
            r"\bpytorch\b",
            r"\btorch\b",
            r"\bllm_load\b",
        ],
        "default_risk": "high",
        "guards": [
            "check WSL memory limit (.wslconfig)",
            "monitor VRAM usage before and during execution",
            "avoid loading all models at once; unload idle weights",
            "ensure swap and system RAM buffers are adequate",
        ],
        "default_recommendation": "verify GPU memory headroom and .wslconfig limits prior to execution",
        "lesson_hints": ["wsl-memory-limit", "cuda-out-of-memory-mitigation"],
    },
    "bulk_import": {
        "name": "Bulk import",
        "patterns": [
            r"\bunzip\b",
            r"\bextract\b",
            r"\bbulk\b",
            r"\bbatch_import\b",
            r"\b100\+\s*files\b",
            r"\bmass\s*ingest\b",
            r"\bmigration\b",
        ],
        "default_risk": "medium",
        "guards": [
            "count files and verify manifest before processing",
            "estimate total uncompressed size and disk space headroom",
            "process in bounded chunks with rate limiting",
            "maintain progress tracking and resume checkpoints",
        ],
        "default_recommendation": "stage files in smaller batches with automated progress logging",
        "lesson_hints": ["bulk-file-ingest-strategy", "batch-import-fault-tolerance"],
    },
}

# Explicit critical markers
CRITICAL_PATTERNS = [
    r"\bformat\b",
    r"\brm\s+-rf\b",
    r"\bdrop\s+database\b",
    r"\bdelete\s+all\b",
    r"\boverwrite\s+production\b",
    r"\bflash\s+firmware\b",
]


def evaluate_intent(intent: str, context: Optional[str] = None) -> Dict[str, Any]:
    """Evaluate agent intent and context to assess risk, match lessons, and generate guards."""
    if not intent:
        return {
            "risk": "low",
            "matched_lessons": [],
            "guards": [],
            "recommendation": "no intent provided",
        }

    combined_text = f"{intent} {context or ''}".lower()

    matched_profiles = []
    matched_guards = []
    matched_lessons = []
    matched_recommendations = []

    # Check for critical keywords
    is_critical = any(re.search(pat, combined_text, re.I) for pat in CRITICAL_PATTERNS)

    # Match risk profiles
    for profile_key, profile_data in RISK_PROFILES.items():
        if any(re.search(pat, combined_text, re.I) for pat in profile_data["patterns"]):
            matched_profiles.append(profile_data)
            for g in profile_data["guards"]:
                if g not in matched_guards:
                    matched_guards.append(g)
            if profile_data["default_recommendation"] not in matched_recommendations:
                matched_recommendations.append(profile_data["default_recommendation"])

    # Determine risk level
    if is_critical:
        risk_level = "critical"
    elif any(p["default_risk"] == "high" for p in matched_profiles):
        # Escalate to critical if multiple high risk profiles match or high data volumes mentioned
        if len(matched_profiles) > 1 and ("wsl" in combined_text or "gpu" in combined_text or "pdf" in combined_text or "200" in combined_text):
            risk_level = "critical"
        else:
            risk_level = "high"
    elif any(p["default_risk"] == "medium" for p in matched_profiles):
        risk_level = "medium"
    else:
        risk_level = "low"

    # Attempt to retrieve lessons from index or known hints
    try:
        from misakanet.search.engine import search
        search_results = search(intent, top=3)
        for r in search_results:
            matched_lessons.append({
                "id": r.get("id") or r.get("lesson_id") or Path(r.get("path", "")).stem,
                "title": r.get("title", ""),
                "relevance": round(float(r.get("score", 0.8)), 2),
            })
    except Exception:
        # Fallback to profile hints if search is offline
        for p in matched_profiles:
            for hint in p["lesson_hints"]:
                matched_lessons.append({
                    "id": hint,
                    "title": f"Lesson {hint}",
                    "relevance": 0.85,
                })

    recommendation = "; ".join(matched_recommendations) if matched_recommendations else "proceed with standard verification"
    if risk_level == "critical" and "probe" not in recommendation:
        recommendation = "run small-scale probe first, then scale; require explicit confirmation"

    return {
        "risk": risk_level,
        "matched_lessons": matched_lessons[:5],
        "guards": matched_guards,
        "recommendation": recommendation,
    }


def main():
    """CLI test interface."""
    import argparse
    parser = argparse.ArgumentParser(description="MisakaNet Preflight Risk Assessment")
    parser.add_argument("intent", help="Action description to assess")
    parser.add_argument("--context", default=None, help="Optional environment context")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    res = evaluate_intent(args.intent, args.context)
    if args.json:
        import json
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        print(f"Risk: {res['risk'].upper()}")
        print(f"Recommendation: {res['recommendation']}")
        print("\nGuards:")
        for g in res["guards"]:
            print(f"- {g}")
        print("\nMatched Lessons:")
        for l in res["matched_lessons"]:
            print(f"- [{l['id']}] {l['title']} (relevance: {l['relevance']})")


if __name__ == "__main__":
    main()
