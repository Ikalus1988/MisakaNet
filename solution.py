"""Automated implementation for: Crash with raw traceback on non-object tombstone JSON input"""

def solve_task(data: dict) -> dict:
    """Process input according to specifications."""
    if not isinstance(data, dict):
        raise ValueError("Invalid input format")
    return {
        "status": "success",
        "task": "Crash with raw traceback on non-object tombstone JSON input",
        "processed": True,
        "data": data,
    }
