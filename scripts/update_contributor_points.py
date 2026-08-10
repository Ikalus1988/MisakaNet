#!/usr/bin/env python3
"""Update contributor reputation points in MisakaNet.
Usage:
  python scripts/update_contributor_points.py --user <username> --action <action> [--detail <json>]
"""

import json, os, sys, argparse
from datetime import datetime, timezone, timedelta

POINTS_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'contributor-points.json')

POINT_RULES = {
    'lesson_merge': 10,
    'search_hit': 1,
    'helpful_vote': 3,
    'e2_evidence': 5,
    'fix_stale': 5,
    'maintenance': 3,
    'social_media': 15,
    'not_helpful': -2,
    'lesson_deleted': -10,
}

DAILY_CAP = 50
NEW_DAILY_CAP = 20
NEW_DAYS = 7
FREEZE_MONTHS = 12


def load():
    if os.path.exists(POINTS_FILE):
        with open(POINTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"_schema": "1.0", "contributors": {}}


def save(data):
    data["_last_updated"] = datetime.now(timezone.utc).isoformat()
    os.makedirs(os.path.dirname(POINTS_FILE), exist_ok=True)
    with open(POINTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def daily_pts(contributor):
    today = datetime.now(timezone.utc).date()
    total = 0
    for e in contributor.get('history', []):
        if datetime.fromisoformat(e['timestamp']).date() == today:
            total += e['points']
    return total


def account_days(contributor):
    first = contributor.get('first_activity')
    if not first:
        return 0
    return (datetime.now(timezone.utc) - datetime.fromisoformat(first)).days


def dedup_search(contributor, lesson_id, query):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    for e in contributor.get('history', []):
        if e['action'] == 'search_hit':
            d = e.get('detail', {})
            if d.get('lesson_id') == lesson_id and d.get('query') == query:
                if datetime.fromisoformat(e['timestamp']) > cutoff:
                    return True
    return False


def dedup_vote(contributor, lesson_id, voter):
    for e in contributor.get('history', []):
        if e['action'] == 'helpful_vote':
            d = e.get('detail', {})
            if d.get('lesson_id') == lesson_id and d.get('voter') == voter:
                return True
    return False


def update(username, action, detail=None):
    if action not in POINT_RULES:
        print("ERROR: Unknown action: " + action, file=sys.stderr)
        return False

    pts = POINT_RULES[action]
    data = load()
    c = data['contributors'].get(username, {
        'total_points': 0,
        'history': [],
        'first_activity': datetime.now(timezone.utc).isoformat(),
        'last_activity': datetime.now(timezone.utc).isoformat()
    })

    # Check freeze
    last = datetime.fromisoformat(c.get('last_activity', c['first_activity']))
    months = (datetime.now(timezone.utc) - last).days / 30
    if months >= FREEZE_MONTHS and pts > 0:
        print("Contributor " + username + " frozen (" + str(int(months)) + " months inactive)")
        return False

    # Daily cap
    daily = daily_pts(c)
    cap = NEW_DAILY_CAP if account_days(c) < NEW_DAYS else DAILY_CAP
    if daily + pts > cap and pts > 0:
        pts = max(0, cap - daily)
        if pts == 0:
            print("Daily cap reached (" + str(cap) + ")")
            return False
        print("Reduced to " + str(pts) + " pt(s) (daily cap: " + str(cap) + ", earned today: " + str(daily) + ")")

    # Dedup checks
    if action == 'search_hit' and detail:
        if dedup_search(c, detail.get('lesson_id', ''), detail.get('query', '')):
            print("Search hit already counted in last 24h")
            return False

    if action == 'helpful_vote' and detail:
        if dedup_vote(c, detail.get('lesson_id', ''), detail.get('voter', '')):
            print("Vote already counted for this lesson+voter")
            return False

    # Apply
    entry = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'action': action,
        'points': pts,
        'detail': detail or {}
    }
    c['history'].append(entry)
    c['total_points'] += pts
    c['last_activity'] = datetime.now(timezone.utc).isoformat()
    data['contributors'][username] = c

    save(data)
    sign = '+' if pts >= 0 else ''
    print("OK: " + username + " " + action + " -> " + sign + str(pts) + " pts (total: " + str(c['total_points']) + ")")
    return True


def main():
    p = argparse.ArgumentParser(description='Update contributor reputation points')
    p.add_argument('--user', required=True)
    p.add_argument('--action', required=True, choices=list(POINT_RULES.keys()))
    p.add_argument('--detail', default='{}')
    args = p.parse_args()
    detail = json.loads(args.detail)
    ok = update(args.user, args.action, detail)
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
