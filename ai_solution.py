```yaml
name: update_lessons_json
on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  tests:
    runs-on: ${{{{ matrix.os }}}}
    strategy:
      matrix:
        os: [ubuntu, windows]
    steps:
      - uses: actions/checkout@v3
      - name: Run Python script
        run: python3 scripts/update_lessons_json.py
      - name: Run tests
        run: pytest tests/
  build_lesson_pages:
    runs-on: ${{{{ matrix.os }}}}
    strategy:
      matrix:
        os: [ubuntu, windows]
    steps:
      - uses: actions/checkout@v3
      - name: Fix YAML
        run: yamlfix -i data/lessons.json
      - name: Build lesson pages
        run: python3 scripts/build_lesson_pages.py
```