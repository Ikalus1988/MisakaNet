"""MisakaNet — Lesson / Node / Search. Zero dep Agent Library.

Commands:
    python3 -m misakanet             Show this help
    python3 search_knowledge.py      Search Lessons (BM25, zero-dep)
    python3 scripts/new_lesson.py    Create a Lesson
    python3 scripts/contribute.py    Submit a Lesson via GitHub API
    python3 scripts/setup.py --check Environment check
    python3 scripts/score_lessons.py Quality score for all Lessons
    python3 scripts/referral.py      Referral code (Node invites)
    python3 hub/misaka_hub.py        Start MisakaHub (optional)
"""
import sys

USAGE = """MisakaNet — Lesson / Node / Search

Commands:
    python3 search_knowledge.py "query"    Search Lessons (BM25, zero-dep)
    python3 scripts/new_lesson.py          Create a Lesson
    python3 scripts/contribute.py          Submit via GitHub API
    python3 scripts/setup.py --check       Environment check
    python3 scripts/score_lessons.py       Quality score
    python3 scripts/referral.py            Referral code
    python3 hub/misaka_hub.py              Start MisakaHub (optional)

Docs: https://github.com/Ikalus1988/MisakaNet
"""

def main():
    print(USAGE)

if __name__ == "__main__":
    main()
