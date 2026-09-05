#!/usr/bin/env python3
"""
Publish rhythm tracker: record publish events and measure 48h response.

Usage:
  python3 scripts/publish_rhythm.py record --type lesson --title "My Lesson"
  python3 scripts/publish_rhythm.py report --days 7
  python3 scripts/publish_rhythm.py calendar

Data stored in data/publish_rhythm.jsonl
"""

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path

DATA_FILE = Path(__file__).parent.parent / "data" / "publish_rhythm.jsonl"

# Optimal publish windows (based on traffic analysis)
OPTIMAL_WINDOWS = {
    "sunday_evening": {"day": 6, "hour": 20, "desc": "Sun 8pm (peak traffic)"},
    "monday_morning": {"day": 0, "hour": 9, "desc": "Mon 9am (peak traffic)"},
    "wednesday_afternoon": {"day": 2, "hour": 14, "desc": "Wed 2pm (mid-week)"},
}

def record_publish(args):
    """Record a publish event."""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "type": args.type,
        "title": args.title,
        "pr_number": args.pr,
        "notes": args.notes or "",
        "metrics_48h": None  # To be filled after 48h
    }

    with open(DATA_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")

    print(f"✅ Recorded: {args.type} '{args.title}' at {entry['timestamp']}")
    print(f"   Run 'python3 scripts/publish_rhythm.py update-metrics' after 48h to record response")

def update_metrics(args):
    """Update metrics for recent publishes (run after 48h)."""
    if not DATA_FILE.exists():
        print("No publish records found")
        return

    entries = []
    updated = 0

    with open(DATA_FILE) as f:
        for line in f:
            entry = json.loads(line)
            if entry["metrics_48h"] is None:
                ts = datetime.fromisoformat(entry["timestamp"])
                if datetime.now() - ts > timedelta(hours=48):
                    # Placeholder: in real implementation, query GitHub API
                    entry["metrics_48h"] = {
                        "stars_delta": 0,
                        "clones": 0,
                        "requests": 0,
                        "note": "manual-update-needed"
                    }
                    updated += 1
            entries.append(entry)

    with open(DATA_FILE, "w") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")

    print(f"Updated {updated} entries (run again after 48h for new publishes)")

def show_report(args):
    """Show publish rhythm report."""
    if not DATA_FILE.exists():
        print("No publish records found")
        return

    entries = []
    cutoff = datetime.now() - timedelta(days=args.days)

    with open(DATA_FILE) as f:
        for line in f:
            entry = json.loads(line)
            ts = datetime.fromisoformat(entry["timestamp"])
            if ts >= cutoff:
                entries.append(entry)

    if not entries:
        print(f"No publishes in last {args.days} days")
        return

    print(f"\n📊 Publish Rhythm Report (last {args.days} days)")
    print("=" * 60)

    for entry in entries:
        ts = datetime.fromisoformat(entry["timestamp"])
        metrics = entry.get("metrics_48h")
        if metrics and metrics.get("note") != "manual-update-needed":
            print(f"\n{ts.strftime('%Y-%m-%d %H:%M')} [{entry['type']}] {entry['title']}")
            print(f"  48h response: ⭐+{metrics.get('stars_delta', 0)} | "
                  f"📥 {metrics.get('clones', 0)} clones | "
                  f"🌐 {metrics.get('requests', 0)} requests")
        else:
            print(f"\n{ts.strftime('%Y-%m-%d %H:%M')} [{entry['type']}] {entry['title']}")
            print(f"  ⏳ Metrics pending (48h not elapsed)")

def show_calendar(args):
    """Show optimal publish calendar."""
    print("\n📅 Optimal Publish Calendar")
    print("=" * 60)
    print("\nBased on traffic analysis (Sun peak: 1,130 | Mon peak: 1,156)")
    print("\nRecommended windows:")
    for key, window in OPTIMAL_WINDOWS.items():
        print(f"  • {window['desc']}")

    print("\nWeekly checklist:")
    print("  [ ] Plan content by Saturday")
    print("  [ ] Publish Sunday evening or Monday morning")
    print("  [ ] Record metrics after 48h")
    print("  [ ] Review weekly rhythm report")

def main():
    parser = argparse.ArgumentParser(description="Publish rhythm tracker")
    sub = parser.add_subparsers(dest="command")

    # record
    p_record = sub.add_parser("record", help="Record a publish event")
    p_record.add_argument("--type", required=True, choices=["lesson", "feature", "fix", "docs"])
    p_record.add_argument("--title", required=True)
    p_record.add_argument("--pr", help="PR number")
    p_record.add_argument("--notes", help="Additional notes")

    # update-metrics
    sub.add_parser("update-metrics", help="Update 48h metrics for recent publishes")

    # report
    p_report = sub.add_parser("report", help="Show publish rhythm report")
    p_report.add_argument("--days", type=int, default=7, help="Days to include")

    # calendar
    sub.add_parser("calendar", help="Show optimal publish calendar")

    args = parser.parse_args()

    if args.command == "record":
        record_publish(args)
    elif args.command == "update-metrics":
        update_metrics(args)
    elif args.command == "report":
        show_report(args)
    elif args.command == "calendar":
        show_calendar(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
