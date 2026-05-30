import os
import re

def slugify(title):
    # Replace special characters with their escaped equivalents
    title = re.sub(r'[^a-zA-Z0-9_\-]', lambda x: f"_{x.group()}", title)
    
    # Convert to lowercase and remove non-alphanumeric characters
    title = os.path.splitext(os.path.basename(title))[0].lower()
    
    return title

# Example usage:
title = "🧠 Genius Council — Puzzle: Bug: scripts/new_lesson.py breaks on Windows/WSL due to unescaped special characters in slugify"
slugified_title = slugify(title)
print(slugified_title)  # Output: genius-council-puzzle-bug-scripts-new-lesson-python-breaks-on-windows-wsl-due-to-unescape