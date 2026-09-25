# SPDX-License-Identifier: MIT
import pytest
from scripts.tombstone_to_draft import _parse_tombstone


def test_parse_tombstone_non_dict_input_raises_value_error():
    """Verify that non-object JSON payloads raise ValueError instead of raw AttributeError (closes #1838)."""
    for invalid in [[], [1, 2, 3], "string_input", 12345, True, None]:
        with pytest.raises(ValueError, match="Tombstone JSON 必须是对象"):
            _parse_tombstone(invalid)


def test_parse_tombstone_valid_dict():
    """Verify standard valid tombstone dictionary parses properly."""
    valid_data = {
        "pid": 1024,
        "timestamp": "2026-09-18T12:00:00Z",
        "reason": "node out of memory",
        "exit_code": 137,
    }
    result = _parse_tombstone(valid_data)
    assert result["pid"] == 1024
    assert result["exit_code"] == 137
