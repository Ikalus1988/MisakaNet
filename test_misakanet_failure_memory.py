import pytest
from misaka import run, capture

def test_failure_memory_rule():
    # Arrange
    rule_path = '.cursor/rules/misakanet-failure-memory.mdc'
    # Act
    result = run(rule_path)
    # Assert
    assert result == 'Failure-memory rule triggers'

def test_claude_playbook():
    # Arrange
    playbook_path = 'CLAUDE.md'
    # Act
    result = run(playbook_path)
    # Assert
    assert result == 'Playbook triggers after 2 failed attempts'

def test_misaka_run():
    # Arrange
    test_path = 'tests/test_failure.py'
    # Act
    result = run(f'-- python -m pytest {test_path}')
    # Assert
    assert result == 'Failing test shows relevant lessons'

def test_misaka_capture():
    # Arrange
    summary = 'test error'
    # Act
    result = capture(summary)
    # Assert
    assert result == 'Redacted intake submitted'