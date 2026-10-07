#!/usr/bin/env python3
"""
Solution for: [Bounty] Answer 2 linked question(s) as a lesson
"""

def merge_questions(q1: str, q2: str) -> str:
    """Combine two related questions into a single lesson."""
    lesson = f"""Lesson:
1. {q1.strip()}
   -> Explanation: Understand the core concept behind this question.
2. {q2.strip()}
   -> Explanation: Apply the same principle to a slightly different scenario.

Key takeaway: Master the underlying idea once, and you can solve both variations."""
    return lesson

def main():
    import sys
    # Expect two lines of input, each a question
    if len(sys.argv) > 1 and sys.argv[1] == '--demo':
        q1 = "What is the time complexity of quicksort in the average case?"
        q2 = "How does quicksort differ from mergesort in space usage?"
    else:
        print("Enter first question:", end=' ')
        q1 = sys.stdin.readline()
        print("Enter second question:", end=' ')
        q2 = sys.stdin.readline()
    result = merge_questions(q1, q2)
    print(result)

if __name__ == "__main__":
    main()