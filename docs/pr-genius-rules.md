# PR Genius 規則設定

PR Genius 由 `scripts/pr_genius_rules.py` 提供可攜核心規則，並在 repo 根目錄
讀取可選的 `pr-genius.yaml`。未設定 `enabled: false` 的規則會依序執行；同一
`id` 的 repo 規則會覆寫核心規則，新的規則則附加在最後。

```yaml
rules:
  - id: dco
    enabled: true
  - id: lesson-lint
    name: Lesson lint
    category: repo
    paths: ["lessons/*.md"]
    command: "python3 scripts/check_lesson_quality.py"
```

欄位：`id` 必填且須唯一；`name`、`category`、`command` 為顯示/執行提示；
`enabled` 可停用規則；`paths` 是 glob，存在時只有變更檔案符合任一 pattern
才觸發。沒有 `paths` 的規則永遠適用。

查看有效規則：

```bash
python3 scripts/pr_genius_report.py
python3 scripts/pr_genius_report.py --changed scripts/mcp_server.py --json
```
