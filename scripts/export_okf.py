import json
import re
from pathlib import Path
import yaml

def extract_frontmatter(path: Path) -> dict:
    """Extracts the YAML frontmatter from a markdown file."""
    try:
        text = path.read_text(encoding='utf-8')
        m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
        if not m:
            return {}
        
        # Replacing the manual line-by-line parser with PyYAML
        # This fixes:
        # 1. Nested keys (e.g., provenance.source) not overwriting top-level keys
        # 2. Block sequences (tags: \n  - item) being correctly parsed
        data = yaml.safe_load(m.group(1))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def main():
    lessons_dir = Path('lessons')
    output_file = Path('data/okf/lessons.jsonl')
    output_file.parent.mkdir(parents=True, exist_ok=True)

    lessons_data = []
    
    # Pattern to find all markdown files
    markdown_files = list(lessons_dir.rglob('*.md'))
    
    for md_path in markdown_files:
        content = md_path.read_text(encoding='utf-8')
        
        # Extract frontmatter
        meta = extract_frontmatter(md_path)
        
        # Extract body (everything after frontmatter)
        body_match = re.search(r"^---\s*\n.*?\n---\s*\n(.*)", content, re.DOTALL)
        body = body_match.group(1).strip() if body_match else content.strip()

        # Basic structure for the exported JSONL
        # We ensure tags is always a list to avoid downstream errors
        tags = meta.get('tags', [])
        if isinstance(tags, str):
            tags = [tags]
        elif tags is None:
            tags = []

        lesson_entry = {
            "title": meta.get('title', md_path.stem),
            "description": meta.get('description', ""),
            "tags": tags,
            "source": meta.get('source', 'unknown'),
            "domain": meta.get('domain', 'unknown'),
            "content": body
        }
        lessons_data.append(lesson_entry)

    # Write to JSONL
    with open(output_file, 'w', encoding='utf-8') as f:
        for entry in lessons_data:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')

    print(f"Exported {len(lessons_data)} lessons to {output_file}")

if __name__ == "__main__":
    main()
