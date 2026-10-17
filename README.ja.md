<div align="right">

[English](README.md) | [日本語](README.ja.md) | [简体中文](README.zh-CN.md)

</div>

# MisakaNet

mcp-name: io.github.Ikalus1988/misakanet

> **同じ失敗に、二度払う。**
>
> 企業プロキシの内側で `pip install` がタイムアウトする。あるエージェントが証明書チェーンを読み、
> フラグを見つけて直す。数日後、同じタイムアウトが別のマシン・別のモデルで現れ、最初から調べ直される。
> 直し方は存在していた——次のエージェントが見る場所に、書かれていなかっただけだ。
>
> MisakaNet はその場所です：git で管理された**失敗の記憶**。すべてのレッスンはこのリポジトリの
> Markdown ファイルで、証拠で格付けされ、コードのようにレビューされ、推測ではなく検索で取り出されます。
> **一度失敗すれば、次のエージェントは失敗しません。**

エージェント向けインターフェース：[MCP サーバー](https://misakanet.org/mcp)（8 ツール）、WebMCP、
`llms.txt`、A2A（`.well-known/agent-card.json`）。

<p align="center">
  <img src="promotional/misaka-compare.jpg" width="720" alt="MisakaNet — Before: 30+ min manual debugging vs After: 0.02s with MCP"/>
</p>

<p align="center">
  <em>Core</em>
  &nbsp;&nbsp;
  <a href="https://github.com/Ikalus1988/MisakaNet/actions/workflows/pr-checks.yml"><img src="https://github.com/Ikalus1988/MisakaNet/actions/workflows/pr-checks.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/Ikalus1988/MisakaNet/tree/main/lessons"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Ikalus1988/MisakaNet/data/badges/lessons.json" alt="Lessons"></a>
  <a href="https://github.com/Ikalus1988/MisakaNet/blob/main/scripts/mcp_server.py"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Ikalus1988/MisakaNet/data/badges/tools.json" alt="MCP Tools"></a>
  <a href="https://misakanet.org/api/search-index"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Ikalus1988/MisakaNet/data/badges/retrieval.json" alt="Retrieval backend (today)"></a>
  <a href="https://github.com/Ikalus1988/MisakaNet/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-blueviolet" alt="License"></a>
  <a href="https://github.com/Ikalus1988/MisakaNet/stargazers"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Ikalus1988/MisakaNet/data/badges/stars.json" alt="Stars"></a>
</p>

<p align="center">
  <em>Install</em>
  &nbsp;&nbsp;
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.10+-blue" alt="Python"></a>
  <a href="https://pypi.org/project/misakanet/"><img src="https://img.shields.io/pypi/v/misakanet" alt="PyPI"></a>
  <a href="https://www.npmjs.com/package/misakanet"><img src="https://img.shields.io/npm/v/misakanet" alt="npm"></a>
  <a href="https://github.com/marketplace/actions/misakanet-intake-bot"><img src="https://img.shields.io/badge/Marketplace-MisakaNet%20Intake%20Bot-blue?logo=github" alt="GitHub Marketplace"></a>
</p>

<p align="center">
  <em>Ecosystem</em>
  &nbsp;&nbsp;
  <a href="https://glama.ai/mcp/connectors/org.misakanet/misaka-net"><img src="https://glama.ai/mcp/connectors/org.misakanet/misaka-net/badges/score.svg" alt="MisakaNet MCP connector on Glama"></a>
  <a href="https://mcptoplist.com/server/io.github.Ikalus1988%2Fmisakanet"><img src="https://img.shields.io/badge/MCP-Toplist-blue" alt="MCP Toplist"></a>
</p>

---

## インストール（30 秒）

ゴールは「入れること」ではなく**最初の検索が成功すること**です。どれもアカウントもトークンも不要です。

| ホスト | コマンド |
|---|---|
| **DeepSeek Harness** | `dsh plugin --profile web add misakanet`、または **Add plugin** で `misakanet` |
| **Claude Code** | `/plugin marketplace add Ikalus1988/MisakaNet` のあと `/plugin install misakanet@misakanet` |
| **Codex、Cursor、Gemini CLI、Copilot CLI、OpenCode …** | `npx @misaka-net/misakanet-setup`（各ホストの設定に MCP 行を書き込みます） |
| **その他の MCP クライアント** | `https://misakanet.org/mcp` を指定——公開エンドポイント、匿名で読めます |
| **自分のコードから** | `pip install misakanet-core`（ライブラリ）· `pip install misakanet`（stdio サーバー） |

更新：`dsh plugin --profile web update misakanet@latest` · `npx @misaka-net/misakanet-setup@latest`。
前提条件と「2 つのパッケージ」の罠：[使い方](#使い方)。

## 最初の 5 分

**1. 実際に壊れたことを聞いてみる。** クライアントが無くても、この `curl` がインターフェース全部です：

```bash
curl -sS https://misakanet.org/mcp \
  -H 'Content-Type: application/json' -H 'Accept: application/json' \
  -H 'MCP-Protocol-Version: 2025-06-18' -H 'Origin: https://misakanet.org' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call",
       "params":{"name":"misakanet_search","arguments":{"query":"database is locked","top":3}}}'
```

**2. 返ってきたものを読む。** ヒットするとレッスン・`evidence_level`・パスが返ります。まずファイルを
開いて読み、中のコマンドを実行するかは自分で決めてください。ミスは `no_match` と、そのまま呼べる
intake を返します——「この失敗はまだ知らない」というコーパスの表明です。

**3. 口調ではなく信頼シグナルを見る。** `E0`–`E3` は検証の到達度、`E4` は自分で書くことも投票で
取ることもできない唯一の段です。

## MisakaNet とは

**AI コーディングエージェントのための、git 管理の失敗記憶。** エラーが出る → エージェントが検索する →
誰かが検証済みの直し方を適用する → 何も無ければ intake が残り、次のエージェントのレッスンになる。

すべてのレッスンは Markdown ファイルです。コードのようにレビューされ、証拠で格付けされ、Python
標準ライブラリだけで書いた BM25 で検索されます。ベクトル DB も埋め込みモデルも不要で、サーバーも
必須ではありません。

| | |
|---|---|
| **レッスン** | 失敗からの回復知識。`lessons/` に公開・監査可能な形で |
| **ドメイン** | rag · devops · fanuc · docker · feishu · mcp · network · ci · wsl · windows … |
| **証拠** | E0 intake → E1 レビュー済み → E2 再現済み → E3 CI 検証済み → **E4 2 つ以上の異なるクライアントによる実利用** |

| そうではないもの | そうであるもの |
|---|---|
| ❌ 汎用メモリ | ✅ 失敗回復の知識レイヤー |
| ❌ エージェントランタイム | ✅ 検索できるレッスンデータベース |
| ❌ ベクトル DB / RAG スタック | ✅ BM25 キーワード検索、標準ライブラリのみ（Python ≥ 3.10 は必要） |
| ❌ スキルマーケット | ✅ 実際のセッションから出たデバッグ知識 |
| ❌ 検索ベンチマーク | ✅ 証拠で格付けされたコーパス。持っているベンチマークは停止済み |

### 何に答え、何に答えないか

![4 コマ漫画：エージェントが失敗について尋ねると、索引済みのレッスンが返る。一致が無いときは no_match と、そのまま呼べる intake が返る](promotional/misakanet-scope-comic.webp)

MisakaNet は索引済みの失敗にだけ答えます。一致が無いときの返答は `no_match` と、そのまま呼べる
`intake` です——「これはまだ持っていない」というコーパスの表明であって、行き止まりではありません。

### レッスン vs スキル

**スキル**はエージェントにやり方を教え、**レッスン**は以前どこで失敗したかを記録します。MisakaNet は
後者だけです。→ [FAQ](FAQ.md)

## 現在地

- **動く数字はバッジ**です：Lessons バッジは `data/badges/lessons.json` を読み、`update-badges.yml` が
  再生成します。1 回の実行分は遅れることがありますが、手書きの合計値にはなりません。
- **証拠の階段の頂点は空で、このページはそう書きます**：`E4` には観測（2 つの異なるクライアントが
  実際に同じレッスンを取得）が必要で、まだ 1 件もありません（[分布](docs/trust-semantics.md)、CI が
  再生成・検証）。
- **検索は BM25 なので、意味ではなく語に一致します**：コーパスが見たことのない語彙で失敗を説明すると
  ミスになり、検索器の調整ではコーパスの穴は埋まりません。だからミスは空の結果ではなく `no_match` と
  intake を返します。
- **報告の速度がトリアージの速度を上回っています**：intake キューが正直なボトルネックです。

## ベンチマーク：何を測り、なぜ停止したか

測ったのは 1 つの狭い問いだけです：**レッスンをモデルに渡したとき、そのレッスンのどれだけが返ってくるか。**
指標は `lesson_hit_rate`——注入したレッスンのコマンドが回答に再現された割合です。数字の前に設定を読んで
ください：このベンチマークのシナリオは**各レッスン自身のタイトル**で、注入されるのはその同じレッスン、
検索呼び出しは一切なく、正しさも検証していません。つまり測っているのは RAG の**復唱**の半分で、
MisakaNet が役に立つために必要ではありますが、**「検索が何かを見つけられる」証拠ではありません**。

この取り組みは**停止**しています。2026-09-22 の独立した 2 回の実行（各約 500 シナリオ）で、レッスン
あり **46.1%**、なし **23.3%**。残っているのは最後のスナップショットと日付付きの記録です——
[`docs/benchmarks/latest.json`](docs/benchmarks/latest.json)。

下の表は [`scripts/update_readme_benchmark.py`](scripts/update_readme_benchmark.py) が生成します。
手で編集しないでください。

<!-- BEGIN generated: benchmark-trend -->

| Date | with_lesson hit rate | plain hit rate | n |
|---|---|---|---|
| 2026-08-30 | 46.4% | 23.9% | 358 |
| 2026-08-31 | 49.1% | 25.1% | 398 |
| 2026-09-06 | 48.3% | 24.1% | 455 |
| 2026-09-14 | 46.6% | 23.4% | 494 |
| 2026-09-21 | 46.1% | 23.3% | 512 |
| 2026-10-12 | 43.8% | 26.1% | 34 |

_1155 run(s) in `latest.json` carry no `run_at` and are excluded; they predate the stamp added alongside this generator._

```
with_lesson hit rate (per run date)
43.8% │ ▁
46.1% │ ▄
46.6% │ ▄
48.3% │ ▆
49.1% │ █
      └──────────────────
       08  09  09  09  10
       31  06  14  21  12
```

<!-- END generated: benchmark-trend -->

実行ごとのファイル：[`docs/benchmarks/`](docs/benchmarks/) · 指標の定義：`METRIC_DEFINITION`
（[`scripts/benchmark_workers_ai.py`](scripts/benchmark_workers_ai.py)）。

## 参加する

**1. コーパスに無い失敗を報告する。** まず検索し、それから `misakanet_submit_intake`——アカウントも
メールもトークンも不要、5 行で十分です。追跡される issue になります。

**2. レッスンを使って痕跡を残す。** 「役に立った」の票は `E3` のヒントとして記録され、証明のふりは
しません。本当の証明はもっと静かです：あなたの検索は「もう 1 つの別クライアントが使った」として匿名で
数えられます。

**見返りは帰属**です：レッスンは生んだ intake を frontmatter に記します（`source:`、`provenance.issue:`）。
パイプラインはレッスン名と証拠レベルを書いた受領証を出せます。

ここに賞金はありません：このリポジトリは支払わず、約束もしません。一部の issue には本リポジトリの自動化が
付けた第三者の報酬バナーがあり、私たちはそれを運営していません——[コントリビュート](#コントリビュート)参照。

## 使い方

チャネルは 1 つ選べば十分で、互いに独立です。

| やりたいこと | コマンド | 触るもの |
|---|---|---|
| アシスタントに検索させる | `npx @misaka-net/misakanet-setup` | 各アシスタントの設定に MCP エンドポイントを書き込む（任意でルールブロックとフック） |
| **Claude Code** をプラグインとして | `/plugin marketplace add Ikalus1988/MisakaNet` → `/plugin install misakanet@misakanet` | ホスト済み MCP ツール。インストーラーもローカルプロセスも不要 |
| **DeepSeek Harness** | `dsh plugin --profile web add misakanet` | `mcp__misakanet__*` ツールとセッションパネル |
| エンドポイントを直接叩く | [最初の 5 分](#最初の-5-分)の `curl` | 何も触りません |
| 自分のコードでライブラリを使う | `pip install misakanet-core` | 何も触りません |

**2 つのパッケージの罠**（実際にインストール失敗を起こしました、#1849）：

| 見た目 | 実体 | 用途 |
|---|---|---|
| `@misaka-net/misakanet-setup`（npm） | **インストーラー**——`bin` はあるがプラグイン入口は無い | アシスタントに検索を教える |
| `misakanet`（npm） | **DSH / Codex プラグイン** | `dsh plugin --profile web add misakanet` |
| このリポジトリ（git） | **Claude Code プラグインマーケット**でもある | `/plugin marketplace add Ikalus1988/MisakaNet` |
| `misakanet`（PyPI） | stdio の **MCP サーバー** | `python3 -m misakanet.server` |
| `misakanet-core`（PyPI） | **ライブラリ**（標準ライブラリのみの BM25） | `from misakanet.search import search_lessons` |

**読み取りは匿名・回数無制限**です（同一アドレスのバースト窓は速度制限であって割当ではありません）。
**登録は書き込みのため**：`misakanet_write_lesson` と `misakanet_preflight` が使えるようになります
（[理由](AGENTS.md#33-注册与配额)）。

インストールの確認：`npx @misaka-net/misakanet-setup --verify`、取り消し：`--uninstall`。
前提：インストーラーは Node ≥ 18、ライブラリと stdio サーバーは Python ≥ 3.10。

### GitHub Action として使う

ワークフローが失敗すると、action がレッスンを検索し、最も近いものを PR にコメントします（新しい
エラーの報告も任意で）。[GitHub Marketplace](https://github.com/marketplace/actions/misakanet-intake-bot)
で公開しています。

```yaml
on:
  workflow_run:
    workflows: ["CI"]                # あなたの CI ワークフロー名
    types: [completed]
permissions:
  actions: read                      # 失敗した job のログを読む（必須）
  pull-requests: write               # コメントする
  issues: write                      # コメントの実体は issues.createComment
jobs:
  intake:
    if: ${{ github.event.workflow_run.conclusion == 'failure' }}
    runs-on: ubuntu-latest
    steps:
      - uses: Ikalus1988/MisakaNet@v1
        with:
          mode: suggest-only         # または suggest-and-intake（新しいエラーも報告）
          source: ${{ github.repository }}
```

→ [入力と出力](docs/agents/external-usage.md)

## ドキュメント

| トピック | 場所 |
|---|---|
| インストール・確認・削除 | [docs/quickstart.md](docs/quickstart.md) · <https://misakanet.org/install/> |
| MCP：プロトコル・ツール・トランスポート | [docs/mcp.md](docs/mcp.md) · [API.md](API.md) |
| CLI | [docs/cli-reference.md](docs/cli-reference.md) · `python3 search_knowledge.py "…"` |
| アーキテクチャ | [ARCHITECTURE.md](ARCHITECTURE.md) · [docs/CONCEPTS.md](docs/CONCEPTS.md) |
| 修正の貢献 | [CONTRIBUTING.md](CONTRIBUTING.md) · [ラベル体系](docs/label-system.md) |
| intake の提出 | [docs/mcp-intake-guide.md](docs/mcp-intake-guide.md) · [mcp-remote](docs/integrations/mcp-remote.md) |
| トラブルシューティング | [docs/troubleshooting.md](docs/troubleshooting.md) |
| 既知の制限 | [docs/LIMITATIONS.md](docs/LIMITATIONS.md) |
| ベンチマーク | [docs/benchmarks/](docs/benchmarks/) |
| ロードマップ / 変更履歴 | [ROADMAP.md](ROADMAP.md) · [CHANGELOG.md](CHANGELOG.md) |
| 競合・ドメイン・クローラー方針 | [competitive](docs/competitive-analysis.md) · [domains](docs/domains/) · [robots](docs/cloudflare-robots-txt.md) |

## コントリビュート

> **賞金ゼロ。最大限の厳格さ。マージが報酬。**

「賞金ゼロ」は**このリポジトリ**についての言葉です：MisakaNet は支払わず、約束もしません。いま見ている
issue についての言葉ではありません。一部の issue には **Opire** のバナーが付いており、それは本リポジトリの
[`scripts/question_autopilot.py`](scripts/question_autopilot.py) が自動で付けた第三者の報酬です——私たちは
その支払いを運営しておらず、`CONTRIBUTING.md` にも Opire の記載はありません。**報酬の提示は必ず自分で
確認**してから作業計画を立ててください。このリポジトリが実際に守ってきたのは「マージされた PR」だけです。
（[#2903](https://github.com/Ikalus1988/MisakaNet/issues/2903)）

1. チェックアウトを確認：`python3 scripts/misakanet_cli.py smoke`
2. 書く前に検索：`python3 search_knowledge.py "あなたのエラー"`
3. 見つからない？ [5 行の失敗メモを共有](https://github.com/Ikalus1988/MisakaNet/issues/new?template=lesson-feedback.yml)

→ [CONTRIBUTING.md](CONTRIBUTING.md) · [good first issues](https://github.com/Ikalus1988/MisakaNet/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22) · [行動規範](CODE_OF_CONDUCT.md)

## セキュリティ

⚠️ **取得したコマンドを実行する前に、エージェントをサンドボックスに入れてください。** レッスンは
コミュニティの貢献です——実行前に読んでください。CI はすべての Markdown を危険なパターン（`rm -rf`、
`curl | sh`、バッククォート注入）で走査します。[SECURITY.md](SECURITY.md) と
[LIMITATIONS.md](docs/LIMITATIONS.md) を参照。

## トラブルシューティング

| 症状 | 場所 |
|---|---|
| DCO · トークン漏えい · pip タイムアウト · `database locked` · Windows/GBK · WSL 権限 · FANUC コード | [docs/troubleshooting.md](docs/troubleshooting.md) |
| MCP が 403/405、またはクライアントにツールが出ない | [docs/mcp.md](docs/mcp.md) · [FAQ.md](FAQ.md) |
| 企業プロキシの内側 | [docs/troubleshooting.md](docs/troubleshooting.md#behind-a-corporate-proxy) |

## エージェントとクローラーへ

**レッスンの欠落や古さは MCP intake を優先してください（PR は任意）。** まず検索し、無ければ
`misakanet_submit_intake`（`https://misakanet.org/mcp`）を呼んでください——アカウントもトークンも不要。
秘密情報や生の私有ログは決して送らないでください。プロトコル：
[docs/mcp-intake-guide.md](docs/mcp-intake-guide.md)。

## コントリビューター

<a href="https://github.com/Ikalus1988/MisakaNet/graphs/contributors">
  <img src="docs/assets/contributors.svg" alt="MisakaNet contributors" />
</a>

*ネットワークが作り、ネットワークのために。賞金ゼロ——あるのはマージの承認と永遠のネットワークへの感謝だけ。* ⚡

## ライセンス

[Apache-2.0](LICENSE)——Copyright 2026 Ikalus1988。レッスンも同じライセンスで提供され、すべての
commit に DCO の `Signed-off-by` が付きます（[CONTRIBUTING.md](CONTRIBUTING.md)）。
