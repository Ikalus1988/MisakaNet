import re
import logging

class SecurityError(Exception):
    pass

def _find_block_reason(command):
    patterns = [
        (r'rm\s+-rf', "Deletion of root or system directories"),
        (r'DROP\s+TABLE', "Database deletion command"),
        (r'TRUNCATE\s+', "Table clearing command")
    ]
    for pattern, reason in patterns:
        if re.search(pattern, command, re.IGNORECASE):
            return reason
    return None

def _log_blocked_command(command, reason):
    logging.warning(f"BLOCKED: {command} REASON: {reason}")

def secure_command_hook(command):
    if not isinstance(command, str):
        raise TypeError("command must be a string")
    reason = _find_block_reason(command)
    if reason:
        _log_blocked_command(command, reason)
        raise SecurityError(f"Blocked dangerous command: {reason}")
    return True
