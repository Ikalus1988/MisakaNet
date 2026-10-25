```yaml
name: update_lessons_json
on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  build_lesson_pages:
    runs-on: ubuntu
    steps:
      - uses: actions/checkout@v3
      - name: Run Python script
        run: |
          python3 scripts/update_lessons_json.py
          python3 scripts/build_lesson_pages.py
          yamlfix -i data/lessons.json

  build_lesson_pages_win:
    runs-on: windows
    steps:
      - uses: actions/checkout@v3
      - name: Run Python script
        run: |
          python3 scripts/update_lessons_json.py
          python3 scripts/build_lesson_pages.py
          yamlfix -i data/lessons.json
```