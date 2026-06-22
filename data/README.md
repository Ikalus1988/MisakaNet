# data/ — CI 自动生成数据目录

⚠️ **此目录下的文件由 GitHub Actions / CI 自动生成，请勿手动编辑。**

| 文件 | 生成者 | 说明 |
|------|--------|------|
| `bench_leaderboard.json` | `gen_leaderboard.py` (CI) | Agent 战力天梯榜快照 |
| `leaderboard.json` | `gen_leaderboard.py` (CI) | 同上（旧路径兼容） |
| `lessons.json` | `batch_lesson_upgrade.py` (CI) | 全量 Lesson 索引 |
| `quality_scores.json` | `check_lesson_quality.py` (CI) | 质量评分聚合 |
| `counter.json` | 注册流程 | 节点计数器 |

**外部贡献者注意**：
- 提 PR 时请忽略此目录的 diff，不要手动修改任何 JSON
- 如需新增数据文件，请将生成逻辑写入 `scripts/` 并配置 `.github/workflows/` 自动更新
