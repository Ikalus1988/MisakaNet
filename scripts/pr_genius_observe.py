#!/usr/bin/env python3
"""Record and inspect PR Genius observations (TP/TN/FP/FN)."""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
from pathlib import Path
from typing import Any

DEFAULT_OBSERVATIONS_PATH = Path(__file__).resolve().parent.parent / "data" / "pr-genius-observations.jsonl"


def determine_outcome(risk: str, issue_actually_existed: bool) -> str:
    """Determine confusion matrix classification.
    
    Positive prediction = PR Genius flagged risk (high_risk, medium_risk, or actionable flag)
    Negative prediction = PR Genius predicted clean/no risk (low_risk / pass)
    """
    predicted_risk = risk.lower() in {"high_risk", "medium_risk", "high", "medium", "risk"}
    if predicted_risk and issue_actually_existed:
        return "TP"
    if not predicted_risk and not issue_actually_existed:
        return "TN"
    if predicted_risk and not issue_actually_existed:
        return "FP"
    return "FN"


def load_observations(path: Path = DEFAULT_OBSERVATIONS_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise ValueError(f"Corrupt JSON at line {line_num} in {path}: {e}")
    return records


def record_observation(
    pr: int,
    repo: str,
    prediction: str,
    human_conclusion: str,
    outcome: str | None = None,
    issue_existed: bool | None = None,
    useful: bool = True,
    notes: str = "",
    path: Path = DEFAULT_OBSERVATIONS_PATH,
) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = load_observations(path)
    next_id = (max([r.get("id", 0) for r in existing], default=0) + 1)

    if outcome is None:
        if issue_existed is None:
            raise ValueError("Either outcome (TP/TN/FP/FN) or issue_existed (bool) must be provided.")
        outcome = determine_outcome(prediction, issue_existed)

    outcome = outcome.upper()
    if outcome not in {"TP", "TN", "FP", "FN"}:
        raise ValueError(f"Invalid outcome: {outcome}. Must be one of TP, TN, FP, FN.")

    record = {
        "id": next_id,
        "pr": pr,
        "repo": repo,
        "prediction": prediction,
        "human_conclusion": human_conclusion,
        "useful": useful,
        "outcome": outcome,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "notes": notes,
    }

    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

    return record


def calculate_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(records)
    if total == 0:
        return {
            "total": 0,
            "tp": 0,
            "tn": 0,
            "fp": 0,
            "fn": 0,
            "accuracy": 0.0,
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
            "actionable_rate": 0.0,
        }

    tp = sum(1 for r in records if r.get("outcome") == "TP")
    tn = sum(1 for r in records if r.get("outcome") == "TN")
    fp = sum(1 for r in records if r.get("outcome") == "FP")
    fn = sum(1 for r in records if r.get("outcome") == "FN")
    useful_count = sum(1 for r in records if r.get("useful", False))

    accuracy = (tp + tn) / total if total > 0 else 0.0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    actionable_rate = useful_count / total if total > 0 else 0.0

    return {
        "total": total,
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "actionable_rate": actionable_rate,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="PR Genius observation logger and analyzer.")
    subparsers = parser.add_subparsers(dest="command")

    record_parser = subparsers.add_parser("record", help="Record a new PR observation")
    record_parser.add_argument("--pr", type=int, required=True, help="Pull request number")
    record_parser.add_argument("--repo", type=str, required=True, help="Repository (owner/repo)")
    record_parser.add_argument("--prediction", type=str, required=True, help="PR Genius prediction (high_risk, medium_risk, low_risk)")
    record_parser.add_argument("--conclusion", type=str, required=True, help="Human conclusion or real outcome")
    record_parser.add_argument("--outcome", type=str, choices=["TP", "TN", "FP", "FN", "tp", "tn", "fp", "fn"], help="Classification outcome")
    record_parser.add_argument("--issue-existed", action="store_true", help="Set if a real issue existed in the PR")
    record_parser.add_argument("--no-issue-existed", action="store_true", help="Set if no real issue existed")
    record_parser.add_argument("--not-useful", action="store_true", help="Mark observation as not useful")
    record_parser.add_argument("--notes", type=str, default="", help="Additional notes")
    record_parser.add_argument("--file", type=str, default=str(DEFAULT_OBSERVATIONS_PATH), help="Custom path to jsonl log")

    list_parser = subparsers.add_parser("list", help="List recorded observations")
    list_parser.add_argument("--file", type=str, default=str(DEFAULT_OBSERVATIONS_PATH))
    list_parser.add_argument("--json", action="store_true", help="Output JSON")

    stats_parser = subparsers.add_parser("stats", help="Compute metrics summary")
    stats_parser.add_argument("--file", type=str, default=str(DEFAULT_OBSERVATIONS_PATH))
    stats_parser.add_argument("--json", action="store_true", help="Output JSON")

    args = parser.parse_args()

    if args.command == "record":
        issue_existed = None
        if args.issue_existed:
            issue_existed = True
        elif args.no_issue_existed:
            issue_existed = False

        record = record_observation(
            pr=args.pr,
            repo=args.repo,
            prediction=args.prediction,
            human_conclusion=args.conclusion,
            outcome=args.outcome,
            issue_existed=issue_existed,
            useful=not args.not_useful,
            notes=args.notes,
            path=Path(args.file),
        )
        print(f"Recorded observation #{record['id']} for {record['repo']}#{record['pr']} -> outcome: {record['outcome']}")
        return 0

    if args.command == "list":
        records = load_observations(Path(args.file))
        if args.json:
            print(json.dumps(records, indent=2))
        else:
            print(f"{'ID':<4} | {'PR':<7} | {'OUT':<4} | {'PREDICTION':<12} | {'REPO':<30} | {'CONCLUSION'}")
            print("-" * 90)
            for r in records:
                print(f"{r.get('id', 0):<4} | #{r.get('pr', 0):<6} | {r.get('outcome', 'N/A'):<4} | {r.get('prediction', 'unknown'):<12} | {r.get('repo', '')[:30]:<30} | {r.get('human_conclusion', '')[:30]}")
        return 0

    if args.command == "stats":
        records = load_observations(Path(args.file))
        metrics = calculate_metrics(records)
        if args.json:
            print(json.dumps(metrics, indent=2))
        else:
            print("=== PR Genius Observation Metrics ===")
            print(f"Total Observations : {metrics['total']}")
            print(f"True Positives (TP): {metrics['tp']}")
            print(f"True Negatives (TN): {metrics['tn']}")
            print(f"False Positives(FP): {metrics['fp']}")
            print(f"False Negatives(FN): {metrics['fn']}")
            print(f"Accuracy           : {metrics['accuracy'] * 100:.1f}%")
            print(f"Precision          : {metrics['precision'] * 100:.1f}%")
            print(f"Recall             : {metrics['recall'] * 100:.1f}%")
            print(f"F1 Score           : {metrics['f1']:.3f}")
            print(f"Actionable Rate    : {metrics['actionable_rate'] * 100:.1f}%")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
