#!/usr/bin/env python3
"""
Validator script for MisakaNet formatted text output.

Checks that /MN segment line counts match declared LINE_COUNT values.
"""

import re
import sys


def extract_mn_segments(text: str) -> list[str]:
    """Extract /MN segments using line-based boundary detection.
    
    Fixed: previously used substring regex matching which caused
    premature truncation when //ENDIF or //END* comments appeared
    in segment bodies (containing '/END' as substring).
    Now uses exact line trim comparison for boundaries.
    """
    segments = []
    lines = text.split('\n')
    current_segment = []
    in_segment = False
    i = 0
    
    while i < len(lines):
        line = lines[i]
        t = line.strip()
        
        if not in_segment:
            if t == '/MN':
                in_segment = True
                current_segment = []
                i += 1
                continue
            i += 1
            continue
        
        # Check for segment boundary using exact trimmed match
        if t == '/POS' or t == '/END':
            segments.append('\n'.join(current_segment))
            in_segment = False
            current_segment = []
            i += 1
            continue
        
        current_segment.append(line)
        i += 1
    
    # Handle segment not terminated by /POS or /END (end of text)
    if in_segment and current_segment:
        segments.append('\n'.join(current_segment))
    
    return segments


def count_lines(segment: str) -> int:
    """Count actual statement lines in a segment."""
    return len(segment.split('\n'))


def parse_line_count(segment: str) -> int | None:
    """Extract declared LINE_COUNT from segment header."""
    for line in segment.split('\n'):
        t = line.strip()
        m = re.match(r'^LINE_COUNT\s*=\s*(\d+)', t)
        if m:
            return int(m.group(1))
    return None


def validate(text: str) -> list[str]:
    """Validate all /MN segments in text. Returns list of error messages."""
    errors = []
    segments = extract_mn_segments(text)
    
    for seg_idx, seg in enumerate(segments):
        declared = parse_line_count(seg)
        actual = count_lines(seg)
        
        if declared is None:
            continue
        
        if declared != actual:
            errors.append(
                f"Segment {seg_idx}: declared LINE_COUNT={declared}, "
                f"actual={actual}"
            )
    
    return errors


def main():
    if len(sys.argv) < 2:
        print("Usage: validator.py <input_file>")
        sys.exit(1)
    
    with open(sys.argv[1], 'r', encoding='utf-8') as f:
        text = f.read()
    
    errors = validate(text)
    
    if errors:
        for e in errors:
            print(f"FAIL: {e}")
        sys.exit(1)
    else:
        print("OK: all segment line counts match")
        sys.exit(0)


if __name__ == '__main__':
    main()
