import os
import sys
from misaka import run, capture

def main():
    # Run cursor rule
    rule_path = '.cursor/rules/misakanet-failure-memory.mdc'
    result = run(rule_path)
    print(f'Cursor rule result: {result}')
    # Run claude playbook
    playbook_path = 'CLAUDE.md'
    result = run(playbook_path)
    print(f'Claude playbook result: {result}')
    # Run misaka run
    test_path = 'tests/test_failure.py'
    result = run(f'-- python -m pytest {test_path}')
    print(f'Misaka run result: {result}')
    # Run misaka capture
    summary = 'test error'
    result = capture(summary)
    print(f'Misaka capture result: {result}')
if __name__ == '__main__':
    main()