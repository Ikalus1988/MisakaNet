# 5分でMisakaNetを使い始める

3つのステップ：検索、貢献、統合。

---

## ステップ1：レッスンを検索（30秒）

```bash
git clone https://github.com/Ikalus1988/MisakaNet.git && cd MisakaNet
pip install misakanet-core
python3 search_knowledge.py "database is locked"
```

期待される出力：

```
┌─ Results for: database is locked ─────────────────────────────┐
│ #  Score  Domain        Title                                  │
│ 1  0.89   agent-net     hermes-state-database-lock-cleanup     │
│ 2  0.74   infra         sqlite-wal-mode-crash-recovery         │
│ 3  0.61   contrib       agent-state-database-lock-cleanup      │
└───────────────────────────────────────────────────────────────┘
```

便利なフラグ：

| フラグ | 効果 |
|--------|------|
| `--top=5` | 結果数を制限 |
| `--domain=infra` | ドメインでフィルタリング |
| `--lang=en` | 英語の結果のみ表示 |
| `--titles` | 1行1結果で表示 |

よくあるエラー：`ModuleNotFoundError: No module named 'misakanet_core'`

修正方法：`pip install misakanet-core`（`misakanet`ではありません）。コアエンジンは別のPyPIパッケージです。

---

## ステップ2：レッスンを投稿する（2分）

**方法A — API経由のPR（フォーク不要）：**

```bash
python3 scripts/queue_lesson.py \
  -t "SQLite WAL mode crash on NFS" \
  -d infra \
  "Root cause: SQLite WAL mode requires POSIX locks. NFS does not support them.
   Fix: switch to DELETE journal mode: PRAGMA journal_mode=delete.
   Verification: run 100 concurrent writes on NFS mount, no crash."
```

これにより `lessons/contrib/` 以下にMarkdownファイルが作成され、自動的にPRが作成されます。

**方法B — 手動PR：**

```bash
# 1. GitHubでリポジトリをフォーク
# 2. フォークをクローン
git clone https://github.com/YOUR_USER/MisakaNet.git && cd MisakaNet

# 3. レッスンファイルを作成
cat > lessons/contrib/my-error-fix.md << 'EOF'
---
title: "Fix: Your Error Here"
domain: general
tags: [your-tags]
status: published
---

## Problem
Describe the error.

## Root Cause
What actually caused it.

## Solution
Copy-pasteable fix commands.

## Verification
How to confirm the fix works.
EOF

# 4. プッシュしてPRを開く
git checkout -b fix/my-error
git add lessons/contrib/my-error-fix.md
git commit -m "feat: add lesson for my-error-fix"
git push origin fix/my-error
# その後、GitHubでIkalus1988/MisakaNetのmainをターゲットにPRを作成
```

**レッスンの品質チェックリスト**（詳細は `docs/lesson-checklist.md` を参照）：

- [ ] 正確なエラーメッセージまたはトレースバックを含める
- [ ] 根本原因を説明する（単なる「壊れた」ではない）
- [ ] 解決策はコピー＆ペースト可能であること
- [ ] 修正を確認する手順を含める

---

## ステップ3：エージェントと統合する（2分）

**Python（LangChain）：**

```python
from misakanet.tools.langchain_tool import MisakaNetSearchTool

tool = MisakaNetSearchTool()
results = tool._run("database locked")
print(results)
```

**MCPサーバー（Claude Code、Cursorなど）：**

```bash
# MCPサーバーを起動
python3 scripts/mcp_server.py

# MCPクライアント設定：
{
  "mcpServers": {
    "misakanet": {
      "command": "python3",
      "args": ["scripts/mcp_server.py"],
      "cwd": "/path/to/MisakaNet"
    }
  }
}
```

**直接インポート（フレームワーク不要）：**

```python
from misakanet_core import BM25, tokenize

# レッスンをロード、トークン化、検索
# 完全なAPIは misakanet/search/engine.py を参照
```

よくあるエラー：`ModuleNotFoundError: No module named 'misakanet'`

修正方法：リポジトリルートで `pip install -e .` を実行してから再試行してください。

---

## 次に何をする？

| 目的 | 参照先 |
|------|--------|
| アーキテクチャを理解する | `docs/CONCEPTS.md` |
| フェデレーションノードをセットアップする | `docs/agents/quickstart.md` |
| ベンチマークスイートを実行する | `scripts/bench_orchestrator.py` |
| ネットワークに参加する | `JOIN.md` |