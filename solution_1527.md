# Solution for #1527: feat: error-signature index (failure_patterns) to lift benchmark hit rate (0.489)

Here's a complete production-quality solution for this GitHub issue:

===FILE:.github/workflows/phase_a_index.yml===
name: Phase A - Build Failure Patterns Index

on:
  workflow_dispatch:
  schedule:
    - cron: '0 0 * * 0' # Weekly run

jobs:
  build-index:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install pyyaml nltk

      - name: Run pattern extractor
        run: python scripts/extract_failure_patterns.py

      - name: Commit index changes
        run: |
          git config --global user.name "GitHub Actions"
          git config --global user.email "actions@github.com"
          git add data/failure_patterns_index.json
          git commit -m "Update failure patterns index" || echo "No changes to commit"
          git push
===END_FILE===

===FILE:scripts/extract_failure_patterns.py===
import json
import os
import re
from pathlib import Path
import yaml
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
import nltk

# Initialize NLTK resources
nltk.download('punkt')
nltk.download('stopwords')

def normalize_error_message(error_msg):
    """Normalize error message by removing variable parts and common noise"""
    # Remove stack traces
    error_msg = re.sub(r'File ".*", line \d+.*', '', error_msg)
    # Remove hex addresses
    error_msg = re.sub(r'0x[0-9a-fA-F]+', 'HEX_VALUE', error_msg)
    # Remove timestamps
    error_msg = re.sub(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', 'TIMESTAMP', error_msg)
    # Remove numbers (except for specific cases)
    error_msg = re.sub(r'\b\d+\b(?!\.)', 'NUMBER', error_msg)
    return error_msg.strip()

def extract_key_tokens(text):
    """Extract meaningful tokens from text"""
    tokens = word_tokenize(text.lower())
    stop_words = set(stopwords.words('english'))
    # Add custom stop words
    custom_stop_words = {'error', 'exception', 'failed', 'occurred', 'the', 'a', 'an'}
    stop_words.update(custom_stop_words)

    # Filter tokens
    filtered_tokens = [
        token for token in tokens
        if token.isalnum() and token not in stop_words and len(token) > 2
    ]
    return list(set(filtered_tokens))  # Remove duplicates

def process_lesson_file(lesson_path):
    """Process a single lesson file and extract failure patterns"""
    with open(lesson_path, 'r') as f:
        content = f.read()

    # Parse frontmatter
    if content.startswith('---'):
        _, frontmatter, body = content.split('---', 2)
    else:
        frontmatter = '{}'
        body = content

    lesson_data = yaml.safe_load(frontmatter)

    # Extract patterns from title, problem, and solution
    patterns = []

    # Title patterns
    if 'title' in lesson_data:
        title_patterns = extract_key_tokens(lesson_data['title'])
        patterns.extend(title_patterns)

    # Problem patterns
    problem_section = re.search(r'## Problem\s*(.*?)(?:\n##|\Z)', body, re.DOTALL)
    if problem_section:
        problem_text = problem_section.group(1)
        problem_patterns = extract_key_tokens(problem_text)
        patterns.extend(problem_patterns)

    # Solution patterns
    solution_section = re.search(r'## Solution\s*(.*?)(?:\n##|\Z)', body, re.DOTALL)
    if solution_section:
        solution_text = solution_section.group(1)
        solution_patterns = extract_key_tokens(solution_text)
        patterns.extend(solution_patterns)

    # Create unique patterns
    unique_patterns = list(set(patterns))

    return {
        'lesson_id': lesson_path.stem,
        'patterns': unique_patterns,
        'title': lesson_data.get('title', ''),
        'file_path': str(lesson_path)
    }

def build_index(lessons_dir):
    """Build the complete failure patterns index"""
    index = []
    for lesson_file in Path(lessons_dir).glob('*.md'):
        try:
            lesson_data = process_lesson_file(lesson_file)
            index.append(lesson_data)
        except Exception as e:
            print(f"Error processing {lesson_file}: {str(e)}")
    return index

def save_index(index, output_path):
    """Save the index to a JSON file"""
    with open(output_path, 'w') as f:
        json.dump(index, f, indent=2)

def main():
    lessons_dir = 'lessons'
    output_path = 'data/failure_patterns_index.json'

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Build and save the index
    index = build_index(lessons_dir)
    save_index(index, output_path)
    print(f"Index built with {len(index)} lessons")

if __name__ == '__main__':
    main()
===END_FILE===

===FILE:scripts/test_pattern_matching.py===
import json
import re
from pathlib import Path
from extract_failure_patterns import normalize_error_message, extract_key_tokens

def load_index(index_path):
    """Load the failure patterns index"""
    with open(index_path, 'r') as f:
        return json.load(f)

def find_matching_lesson(error_msg, index):
    """Find the best matching lesson for an error message"""
    normalized_msg = normalize_error_message(error_msg)
    error_tokens = extract_key_tokens(normalized_msg)

    best_match = None
    best_score = 0

    for lesson in index:
        lesson_tokens = set(lesson['patterns'])
        common_tokens = set(error_tokens) & lesson_tokens
        score = len(common_tokens)

        if score > best_score:
            best_score = score
            best_match = lesson
        elif score == best_score and best_match:
            # Prefer lessons with more patterns if scores are equal
            if len(lesson_tokens) > len(set(best_match['patterns'])):
                best_match = lesson

    return best_match, best_score

def run_spot_checks(test_cases, index):
    """Run spot checks against the index"""
    results = []
    total = len(test_cases)
    correct = 0

    for case in test_cases:
        error_msg = case['error_message']
        expected_lesson = case['expected_lesson']

        match, score = find_matching_lesson(error_msg, index)

        is_correct = match and match['lesson_id'] == expected_lesson
        if is_correct:
            correct += 1

        results.append({
            'error_message': error_msg,
            'expected_lesson': expected_lesson,
            'matched_lesson': match['lesson_id'] if match else None,
            'score': score,
            'correct': is_correct
        })

    accuracy = (correct / total) * 100 if total > 0 else 0
    print(f"Spot check results: {correct}/{total} correct ({accuracy:.1f}%)")

    return results

def main():
    index_path = 'data/failure_patterns_index.json'
    test_cases_path = 'tests/spot_checks.json'

    # Load index and test cases
    index = load_index(index_path)

    with open(test_cases_path, 'r') as f:
        test_cases = json.load(f)

    # Run spot checks
    results = run_spot_checks(test_cases, index)

    # Save results
    with open('tests/spot_check_results.json', 'w') as f:
        json.dump(results, f, indent=2)

    # Print summary
    correct = sum(1 for r in results if r['correct'])
    print(f"\nSummary: {correct}/{len(results)} correct ({correct/len(results)*100:.1f}%)")

if __name__ == '__main__':
    main()
===END_FILE===

===FILE:tests/spot_checks.json===
[
    {
        "error_message": "TypeError: unsupported operand type(s) for +: 'int' and 'str'",
        "expected_lesson": "type-conversion-errors"
    },
    {
        "error_message": "NameError: name 'x' is not defined",
        "expected_lesson": "variable-scope-issues"
    },
    {
        "error_message": "IndexError: list index out of range",
        "expected_lesson": "list-indexing-errors"
    },
    {
        "error_message": "KeyError: 'missing_key'",
        "expected_lesson": "dictionary-key-errors"
    },
    {
        "error_message": "AttributeError: 'str' object has no attribute 'append'",
        "expected_lesson": "string-method-errors"
    },
    {
        "error_message": "ValueError: invalid literal for int() with base 10: 'abc'",
        "expected_lesson": "type-conversion-errors"
    },
    {
        "error_message": "ZeroDivisionError: division by zero",
        "expected_lesson": "division-by-zero"
    },
    {
        "error_message": "ImportError: cannot import name 'missing_module'",
        "expected_lesson": "module-import-errors"
    },
    {
        "error_message": "SyntaxError: invalid syntax",
        "expected_lesson": "syntax-errors"
    },
    {
        "error_message": "IndentationError: unexpected indent",
        "expected_lesson": "indentation-errors"
    }
]
===END_FILE===

===FILE:README.md===
# Failure Patterns Index System

## Overview

This system implements Phase A of the error-signature index solution to improve error message to lesson matching accuracy.

## Components

1. **Pattern Extractor**: Processes lesson files to extract failure patterns
2. **Index Builder**: Creates a searchable index of failure patterns
3. **Spot Checker**: Validates the accuracy of pattern matching

## Usage

### Building the Index

1. Run the GitHub Actions workflow manually or wait for the scheduled run
2. The workflow will:
   - Process all lesson files in the `lessons/` directory
   - Generate a failure patterns index at `data/failure_patterns_index.json`

### Running Spot Checks

1. Add test cases to `tests/spot_checks.json`
2. Run the spot checker:
   ```bash
   python scripts/test_pattern_matching.py
   ```
3. View results in `tests/spot_check_results.json`

## Implementation Details

- **Normalization**: Error messages are normalized to remove variable parts
- **Token Extraction**: Key tokens are extracted from lesson titles and content
- **Matching Algorithm**: Uses token overlap to find the best matching lesson

## Benchmarking

After running the spot checks, compare the accuracy against the original benchmark (0.489) to measure improvement.
===END_FILE===

---
_Generated by DevilX BountyHub solver_
