```python
#!/usr/bin/env python3
import os
import glob
import yaml
from hashlib import sha256

def rebuild_lessons_index():
    lesson_dirs = ['lessons/core', 'lessons/contrib', 'lessons/en']
    lessons = []
    
    for directory in lesson_dirs:
        for filename in glob.glob(os.path.join(directory, '**/*.md')):
            if 'README.md' in filename:
                continue
            with open(filename, 'r', encoding='utf-8') as f:
                content = f.read()
                frontmatter = content.split('---', 2)[0].strip()
                try:
                    lesson = yaml.safe_load(frontmatter)
                    lessons.append(lesson)
                except yaml.YAMLError:
                    continue

    lessons.sort(key=lambda x: x['title'])
    index_content = "## Lessons\n\n"
    for lesson in lessons:
        index_content += f"- [{lesson['title']}](./{lesson['file']}): {lesson['description']}\n"

    with open('lessons/index.md', 'w', encoding='utf-8') as f:
        f.write(index_content)

    if '--check' in os.sys.argv:
        with open('lessons/index.md', 'rb') as f:
            index_sha = sha256(f.read()).hexdigest()
        with open('.github/workflows/index.sha256', 'r') as f:
            if f.read().strip() == index_sha:
                print("Index is up to date.")
            else:
                print("Index needs update.")

if __name__ == '__main__':
    rebuild_lessons_index()
```