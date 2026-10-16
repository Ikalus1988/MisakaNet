<div align="right">

[English](README.md) | [日本語](README.ja.md) | [简体中文](README.zh-CN.md)

</div>

# MisakaNet

mcp-name: io.github.Ikalus1988/misakanet

> **同じ障害に、二度払う。**
>
> 企業プロキシの背後で `pip install` がタイムアウトする。あるエージェントが証明書チェーンを読み、該当のフラグを見つけ、
> 直す。数日後、同じタイムアウトが別のリポジトリ・別のマシン・別のモデルの下に現れる —— そして今度は最初から調べ直される。
> 新しいエージェントには、誰かがすでに代償を払ったことを知る手立てがないからだ。修正は存在していた。ただ、次のエージェントが
> 見る場所に書かれていなかっただけだ。
>
> MisakaNet はその場所です。Git に支えられた **障害記憶**: レッスンはすべてこのリポジトリの Markdown ファイルで、
> エビデンスで格付けされ、コードと同じようにレビューされ、推測ではなく検索によって取り出されます。
> あなたが一度失敗すれば、次のエージェントは繰り返しません。
>
> エージェントネイティブなインターフェース: [MCP サーバー](https://misakanet.org/mcp)（8 ツール）、WebMCP（ブラウザの
> `navigator.modelContext`）、`llms.txt` / `llms-full.txt`、そして `.well-known/agent-card.json` 経由の A2A ディスカバリー。

<p align="center">
  <img src="promotional/misaka-compare.jpg" width="720" alt="MisakaNet — Before: 30+ min manual debugging vs After: 0.02s with MCP"/>
</p>

<p align="center">
  <em>Core</em>
  &nbsp;&nbsp;
  <!-- CI バッジは `pr-checks.yml`（`audit` ジョブ: 本リポジトリの Python テストスイートを実行）を指します。2026-10-17 まで
       指していた `pr-quality-gate.yml` は品質ラベルを付けるだけで、`check_run: [completed]` と
       cancel-in-progress で動き、そのファイル自身のヘッダが結果を記録しています ——
       キャンセルされた run は `gh` に `fail` と報告されるが、実際のチェックは `cancelled`
       （「直近 12 回のうち 2 回がキャンセル、実原因での失敗は 0」）。実測 2026-10-17: 旧バッジは
       "failing"、`pr-checks.yml` は "passing"。これは必須チェック 4 本には元から含まれておらず、
       赤を隠したのではなく訂正です。 -->
  <a href="https://github.com/Ikalus1988/MisakaNet/actions/workflows/pr-checks.yml"><img src="https://github.com/Ikalus1988/MisakaNet/actions/workflows/pr-checks.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/Ikalus1988/MisakaNet/tree/main/lessons"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Ikalus1988/MisakaNet/data/badges/lessons.json" alt="Lessons"></a>
  <a href="https://github.com/Ikalus1988/MisakaNet/blob/main/scripts/mcp_server.py"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Ikalus1988/MisakaNet/data/badges/tools.json" alt="MCP Tools"></a>
  <a href="https://misakanet.org/api/search-index"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Ikalus1988/MisakaNet/data/badges/retrieval.json" alt="Retrieval backend (today)"></a>
  <a href="https://github.com/Ikalus1988/MisakaNet/blob/main/LICENSE"><img src="https://img.shields.io/github/license/Ikalus1988/MisakaNet?color=blueviolet" alt="License"></a>
  <a href="https://github.com/Ikalus1988/MisakaNet/stargazers"><img src="https://img.shields.io/github/stars/Ikalus1988/MisakaNet?style=social" alt="Stars"></a>
</p>

<p align="center">
  <em>Install</em>
  &nbsp;&nbsp;
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.10+-blue" alt="Python"></a>
  <a href="https://pypi.org/project/misakanet/"><img src="https://img.shields.io/pypi/v/misakanet" alt="PyPI"></a>
  <a href="https://www.npmjs.com/package/misakanet"><img src="https://img.shields.io/npm/v/misakanet" alt="npm"></a>
  <a href="https://github.com/marketplace/actions/misakanet-intake-bot"><img src="https://img.shields.io/badge/Marketplace-MisakaNet%20Intake%20Bot-blue?logo=github" alt="GitHub Marketplace"></a>
  <a href="https://dsh-plugin.org/plugins/ikalus1988/misakanet"><img src="https://dsh-plugin.org/badges/listed.svg" alt="Listed on dsh-plugin.org"></a>
  <a href="https://dsh.directory/plugins/ikalus1988/misakanet"><img src="https://dsh.directory/badges/listed.svg" alt="Listed on DSH Directory"></a>
  <a href="https://www.dsh.so/artifact/misakanet/"><img src="https://www.dsh.so/badge/install/misakanet.svg" alt="dsh.so install"></a>
</p>

<p align="center">
  <em>Ecosystem</em>
  &nbsp;&nbsp;
  <a href="https://glama.ai/mcp/connectors/org.misakanet/misaka-net"><img src="https://glama.ai/mcp/connectors/org.misakanet/misaka-net/badges/score.svg" alt="MisakaNet MCP connector – tool definition quality and endpoint health on Glama"></a>
  <a href="https://mcptoplist.com/server/io.github.Ikalus1988%2Fmisakanet"><img src="https://mcptoplist.com/badge/io.github.Ikalus1988%2Fmisakanet.svg" alt="MCP Toplist"></a>
  <!-- Smithery バッジは shields.io の 'endpoint' バッジを使い、Kin スコアを
       data/badges/smithery.json から動的に読み取ります。update-smithery-badge
       ワークフローが毎日更新するので、手動 PR なしでも同期が保たれます。 -->
  <a href="https://smithery.ai/servers/misakanet/misakanet"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Ikalus1988/MisakaNet/refs/heads/data/badges/smithery.json" alt="Smithery"></a>
  <!-- HOL Registry バッジは 2026-10-17 に削除しました。shields の静的シールドで私たち自身の文字列
       （"HOL Registry: listed"）を配っており、リンク先の掲載ページはブラウザ以外の取得にすべて 403 を
       返します —— hol.org/registry 自体も Cloudflare のチャレンジで、読めるページではありません。
       つまりこのファイルに hol.org が私たちを掲載している証拠は何もなく、検証できない「listed」は
       今回の整理で落とす種類のものです。復活させるなら、読者（やチェック）が実際に開ける掲載リンクと
       一緒に戻してください。 -->
  <!-- Benchmark バッジは 2026-10-17 に削除しました。ハードコードされた文字列が `Benchmark / Weekly
       Workers AI` である一方、週次の実行は停止しています —— 静的バッジは真にできず、「weekly」と書きながら
       隣でジョブが止まっているバッジは、バッジが無いより信頼を損ないます。正直な形は本文にあります:
       `## ベンチマーク：何を測り、なぜ停止したか`（最後のスナップショットをリンク）。 -->
</p>

<p align="center"><em>第三者のインストールバッジは正しく読んでください: <a href="https://www.dsh.so/artifact/misakanet/">dsh.so</a> が検証するのは「どの <b>dsh ホストリリース</b>で動いたか」で、そのバージョンをバッジに印字します。バージョン非固定のバッジは遅れます —— 2026-10-17 の実測では <code>0.1.6a2</code>（dsh <code>0.1.6-alpha.2</code>、2026-09-20）でしたが、dsh.so の <code>0.2.1-alpha.4</code> 向けのバージョン固定バッジも verified を表示しています。つまりこの数字は彼らの記録であって、私たちのリリース標識でも互換性の主張でもありません。本リポジトリが宣言するホストリリースは <a href="docs/compatibility.md">compatibility</a> にあります。バージョン非固定のままなのは意図的です —— 固定バッジはリリースごとに誰かが動かす必要があり、本リポジトリはそのためのジョブを足しません。</em></p>

---

## インストール（30秒）

| ご利用の環境 | コマンド |
|---|---|
| **DeepSeek Harness** | `dsh plugin --profile web add misakanet` — あるいはホストの **Add plugin** ダイアログで `misakanet` と入力 |
| **Claude Code** | `/plugin marketplace add Ikalus1988/MisakaNet` ののち `/plugin install misakanet@misakanet` |
| **Codex、Cursor、Gemini CLI、Copilot CLI、OpenCode など** | `npx @misaka-net/misakanet-setup` — 各ホスト自身の設定に MCP の行を書き込む |
| **その他の MCP クライアント** | `https://misakanet.org/mcp` を指定する — エンドポイントは公開されており、読み取りは匿名 |
| **自前のコード** | `pip install misakanet-core`（ライブラリ） · `pip install misakanet`（stdio サーバー） |

<p align="center">
  <img src="docs/assets/dsh-plugin-add.png" width="760" alt="DeepSeek Harness のプラグインページ: (1) サイドバーのプラグインアイコン、(2) 添加插件 (Add plugin) ボタン、(3) パッケージ名 misakanet を入力した Add-plugin ダイアログ"/>
</p>

<p align="center"><em>DeepSeek Harness: サイドバーの <b>插件</b> (1) → <b>添加插件</b> (2) → <code>misakanet</code> を入力 (3) → <b>安装</b>。<br/>ダイアログは上の CLI コマンドと同じパッケージ名を受け付けます（ダイアログ自身のヒント: パッケージ名、GitHub の URL、またはローカルパス）。</em></p>

更新: `dsh plugin --profile web update misakanet@latest`。
インストーラー自体の更新: `npx @misaka-net/misakanet-setup@latest`（独自のコマンド、独自のフラグ）。

プラグイン経路ではアカウント不要、トークン不要、Python も不要です: npm バンドルがホストされたエンドポイントをマウントします。
宣言されているホストと実際に測定した内容: [compatibility](docs/compatibility.md)。各チャネル、前提条件、そして人から
インストールを代償させる「2つのパッケージの罠」: [使い方](#使い方)。

バッジの数字は正しく読んでください。MCP ツール数は私たち自身の **MCP ツール** バッジ（`data/badges/tools.json` を読み、現在は 8）
だけが根拠です。第三者の評価バッジの文言は第三者のもので古びます —— 実測 2026-10-17、Glama の server バッジは依然
"11 tools" と書いていましたが、エンドポイントは 8 を提供しています。だから壁には記述が正しい connector バッジだけを残し
（理由もそこに書いてあります）、2 つの Glama バッジを並べて互いに裏付け合っているように見せることはしません。
Glama のリスト自体の古さは [#3323](https://github.com/Ikalus1988/MisakaNet/issues/3323) で追跡されています。

## 最初の 5 分

インストールの目的はインストールではなく、**最初の検索が当たること**です。残りを読む前に、これを一度やってください。

**1. 実際に壊したものを尋ねる。** コーパスは障害そのものなので、覚えている障害が最も正直なテストです
（デモ用のキーワードは使わないでください）。クライアントを入れていない場合、この `curl` がインターフェースの全部です:

```bash
curl -sS https://misakanet.org/mcp \
  -H 'Content-Type: application/json' -H 'Accept: application/json' \
  -H 'MCP-Protocol-Version: 2025-06-18' -H 'Origin: https://misakanet.org' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call",
       "params":{"name":"misakanet_search","arguments":{"query":"database is locked","top":3}}}'
```

**2. 返ってきたものを読む。** ヒットすればレッスン本体、その `evidence_level`、このリポジトリ内のパスが返ります ——
ファイルを開いて修正を読み、中のコマンドを実行するかどうかは自分で決めてください。ヒットしなければ `no_match` と、
そのまま呼べる intake が返ります。これも結果です。コーパスが「これはまだ知らない」と言っているのであって、
それを埋める最短の方法が[参加する](#参加する)です。

**3. 口調ではなく信頼シグナルを見る。** `E0`–`E3` はどこまで検証されたかを示し、最上位の `E4` は誰も書き込めず投票もできない段です。
コーパスが実際どこに立っているかは[今日の位置](#今日の位置)にあります。

## DeepSeek Harness プラグインが追加するもの

バージョン 2.40.0 がブラウザ側を出荷し、2.41.0 がその残りを加えます。以下の面がすべて同じリリースで届いたわけでは
ないので、このセクションでは、それぞれの面を担っているバージョンごとに列挙します。ダイアログを足すのではありません。
MisakaNet を、すでにセッションが存在する場所に据えます。

**2.40.0 で公開済み。** 以下の 6 つの席が、いま `npm view misakanet version` で得られるものです。

| 場所 | 得られるもの |
| --- | --- |
| **左カラム** | `Plugins` の直下に常設する `MisakaNet` エントリ。パネルへのショートカットであり、クリックするとメインカラムに全画面が開きます。ルートスコープなので、セッションによって出たり消えたりはしません。 |
| **会話タブ** | Chat と Trajectory のとなりに `MisakaNet` タブが付きます。このセッションが何を問い合わせ、何が返り、何を記録したかを、会話自身の行から組み立て直して表示します。 |
| **右カラム** | 同じパネルをペインとして配置するので、ファイルツリー・ターミナル・ドキュメントのとなりに置けます。 |
| **ツール呼び出しの行** | `misakanet_search` と `misakanet_submit_intake` の呼び出しごとに、ツールカード上に専用の行ができます。送信されたクエリそのもの、レッスンが返ったかどうか、そして先頭にあるレッスンはどれか。生の結果はひとつ開けば見えます。この行は報告するだけで投稿しません。投票は下の回答側のアクション行に付きます。 |
| **アシスタントのアクション行** | レッスンを使った回答に 👍 / 👎。このページが送信するのはこの二つだけです。カウンタはサーバーではなくブラウザに置かれます。 |
| **音声** | 既定ではオフのスイッチで、二つの仕組みを説明します。サーバーが次回の検索で名指しする合図と、ページからは読めないローカルのフック。 |

<p align="center">
  <img src="docs/assets/dsh-client-left-column.png" width="820" alt="DeepSeek Harness: 左カラムの Plugins の下に常設する MisakaNet エントリと、それが開く全画面"/>
</p>

<p align="center">
  <img src="docs/assets/dsh-client-right-panel.png" width="820" alt="DeepSeek Harness のセッションの右カラムにある MisakaNet ペイン"/>
</p>

**2.41.0 で追加 — [リリース PR #2591](https://github.com/Ikalus1988/MisakaNet/pull/2591)。** 以下の 6 つの面は
`main` に入っており 2.41.0 で出荷されます。2.40.0 を入れた環境にはまだありません。

| 場所 | 得られるもの |
| --- | --- |
| **コンポーザーの `/misakanet`** | `/misakanet pip install timeout` と入力して Enter を押すだけ。レッスンがコンポーザー内のカードとして返り、エージェントは介在しません。送信されるのはクエリだけです。 |
| **フレーム全体のトースト** | `/misakanet` の検索がレッスンを返すと、先頭ヒットを載せたカードが全カラムを覆って表示され、閉じるかレッスンまでクリックで進めます。 |
| **サイドバーの下部** | Settings の隣に 1 つのアクション。このセッションの MisakaNet 活動を、Issue や PR 本文向けに要約としてコピーします。 |
| **中文 / English** | すべての MisakaNet 面がホストの言語に従います。パネル、`/misakanet` カード、設定行、そしてプラグインページ自身のタイトルと説明。 |
| **Settings → General** | MisakaNet の設定行。このブラウザで音声合図を鳴らすかどうかと、面を表示する細かさ（コンパクト / フル）。どちらもブラウザ内に留まります。 |
| **プラグインページ** | MCP の行が実際に使う設定、エンドポイント・トランスポート・タイムアウトを、読み取り専用で表示します。設定の編集場所（プロファイルの `cordis.patch.yml`）のそばに置いてあります。 |

どちらの側がどの席を持ち、なぜ `root` か `session` スコープなのかを、ホスト自身の契約文の引用付きで:
[compatibility](docs/compatibility.md)。自分のホストを動かしていて、プロファイルに触れない確認がほしい場合:
`python3 scripts/install_smoke.py dsh-client --serve`。

## MisakaNet とは？

**Git に支えられた、AI コーディングエージェント向けの障害記憶。** エラーが出る → エージェントがレッスンを検索 →
誰かがすでに検証した修正を適用 → どれも合致しなければ、intake がその行き止まりを次のエージェント向けのレッスンに変える。
すべてのレッスンはこのリポジトリの Markdown ファイルです。コードと同じようにレビューされ（各コミットは DCO 署名）、
エビデンスレベルで格付けされ、Python 標準ライブラリだけで BM25 による検索が走ります。ベクトルデータベースも、
埋め込みモデルも、サーバーも不要です（ほしい場合だけ用意してください）。

| | |
|---|---|
| **Lessons** | 障害復旧の知識ベース。`lessons/` の下で公開され、監査できます |
| **Domains** | rag · devops · fanuc · docker · feishu · mcp · network · ci · wsl · windows … |
| **Evidence levels** | E0 intake → E1 メンテナーによるレビュー → E2 ローカルでの再現 → E3 CI / サンドボックスでの検証 → **E4 2 つ以上の異なるクライアントによる再利用の観測** |

最上位の段だけは、誰も書くことも、投票することも、マージで押し上げることもできません。E0–E3 は「誰か・何かのパイプラインが
そのレッスンに何をしたか」を表し、E4 は「2 つの異なるクライアントが実際に戻ってきて使った」ことを表します。これはファイルに
宣言されるものではなく、トランスポート層で観測されるものです —— だからレッスン自身の自己申告ではこの段に届きません。
それがコーパスにとって何を意味するかは[今日の位置](#今日の位置)に書いてあります。

レジストリの掲載先（[Glama](https://glama.ai/mcp/connectors/org.misakanet/misaka-net)、
[Smithery](https://smithery.ai/servers/misakanet/misakanet)、MCP Toplist）はホストされたエンドポイントを中継するだけで、
そのエンドポイントは **インデックス済みの障害復旧レッスン** を配信します。*インデックス済み* であり「検証済み」では
ありません。レッスンがどれだけ立証されているかを示すのがエビデンスレベルです。

| MisakaNet は ❌ ではない | 代わりに ✅ こちらです |
|------------------|-------------------|
| ❌ 汎用メモリシステム | ✅ 障害復旧知識レイヤー |
| ❌ エージェントのランタイムやフレームワーク | ✅ 検索可能なレッスンデータベース |
| ❌ ベクトルデータベースや RAG システム | ✅ BM25 キーワード検索 — **標準ライブラリのみ**、サードパーティパッケージなし。ただし **Python 3.10 以降のインタプリタ自体は必要です** |
| ❌ サインアップが必要なクラウドサービス | ✅ `git clone` → ローカルで検索 |
| ❌ スキルマーケットプレイス | ✅ 実セッションから得たデバッグ知識 |

### 答えてくれること、答えてくれないこと

![4コマ漫画：マスコットは「すべてのAIエラーを防げる」と約束するが、猫がピザと石油缶を尋ねるとしょげてしまい、別の猫が npm ERESOLVE を見せると目を輝かせる。MisakaNet が知っているのは収録済みの障害であり、一般知識ではない。](promotional/misakanet-scope-comic.webp)

答えてくれるのは **MisakaNet がインデックス済みの障害** であり、一般知識ではありません。何も見つからないクエリは
`no_match` と、そのまま呼び出せる intake を返します。未ヒットはギャップが記録される経路そのものなので、
未ヒットもまた答えです。

### レッスン vs スキル

**スキル** はエージェントに *何かをする方法* を教える。**レッスン** は *前に何が壊れたか、そして二度と失敗しないためには
どうするか* を記録する。MisakaNet が担当するのは後者だけです。スキルマーケットプレイスでも、エージェントランタイムでも、
汎用メモリレイヤーでも、ベクトルデータベースでもありません。→ [FAQ](FAQ.md)

## 今日の位置

**変化する数字はバッジです。これは意図的です。** 上部の **Lessons** バッジはこのページに打ち込まれた数字ではなく、
`data/badges/lessons.json` を描画したもので、それを `update-badges.yml` が `data/lessons.json` から再生成します ——
`lessons/**` に触れる push ごと、そして少なくとも毎週 1 回です。つまり**スケジュールされた測定値**であって生の読み取りではなく、
1 回分遅れることがあります。それでも、このリポジトリが手で総数を維持するよりましです（実際、ハードコードされたコーパス件数は
**削除**しました）。**MCP Tools** バッジはホストされたツール集合について同じ考え方で、**Retrieval backend** バッジは
いま検索を答えている経路を報告します。`python3 scripts/sync_lesson_count.py --check` は、件数と文言が同じ出所を指していることを
保つゲートです。

数字の出所は重要なので: 私たちのツール数は **MCP Tools** バッジ（`data/badges/tools.json`）だけです。レジストリの評価バッジは
第三者の文言であり、古びます —— 実測 2026-10-17、Glama の server バッジは「11 tools」と書いたままで、エンドポイントは 8 を
提供していました。だから重複する connector バッジ（8 と書いているほう）だけを残し、2 つの Glama バッジを並べて
互いに裏付け合っているように見せることはしません。

**エビデンス階段の最上位は空です。README はそう書きます。** E4 は観測を要求します: **2 つ以上の異なるクライアントが
実際にそのレッスンを取得した**こと。`python3 scripts/evidence_distribution.py` が出す値は **0** です。
完全な分布（宣言・既定・空欄）は [`docs/trust-semantics.md`](docs/trust-semantics.md) に生成され、
CI がコーパスに対して毎回導出し直すので、静かに古びることはありません。
訪問者が最初に読むファイルに、**自分たちにとって最も都合の悪い測定値**を載せています。

完全な階段（**E0–E3 は誰かがそのレッスンにしたこと、E4 は他の誰かが実際に戻ってきて使ったこと**）:

| レベル | 意味 | 到達条件 |
|---|---|---|
| **E0** | 寄稿者による自己申告（既定） | intake の既定値 |
| **E1** | メンテナーがレビューした | メンテナーが intake を受理した |
| **E2** | ローカルで再現した | メンテナーまたは CI が修正を再現した |
| **E3** | CI / サンドボックスで検証した | 自動検証が通った |
| **E4** | **2 つ以上の異なるクライアントが再利用を観測** | worker が `search_signals` の `COUNT(DISTINCT client_hint)` から数える —— 投票では届かず、レッスン本文に `verified by` と書いても届かない |

この数字が実際に何を言っているか、そして見えている他のギャップ:

- **「使われたことで自らを証明した」レッスンはまだ 1 つもありません。** 再利用が起きていないからではなく、
  このシグナルが最近まで数えられておらず、しかも**意図的に少なく数える**からです: 匿名の呼び出し元は
  `client_hint` を書かないので、毎日使われているレッスンでも 0 のままあり得ます。
  「黙ることで間違えても、ファイルを編集して水増しできない」信頼シグナルのほうが、編集で作れる信号よりましです。
- **ほとんどのレッスンはレベルを宣言していません。** 既定ルールで `E0` と読まれるだけで、誰かが「証拠なし」と
  判定したわけではありません。E0 の集団はほとんどが**未記入**であって**無証拠**ではない —— `E0` を「悪い」の意味で
  使うこと自体が、もう一つの嘘になります。
- **検索は BM25 なので、意味ではなく語を照合します。** コーパスが一度も見たことのない言い回しで障害を説明すれば未ヒットになり、
  リトリーバーの調整ではコーパスの穴は埋まりません。だから未ヒットは空の結果ではなく `no_match` と intake を返します。
- **このファイルのベンチマークは停止しており、検索を測ったことは一度もありません。** 測っていたのは「渡された資料を
  モデルがどれだけ繰り返すか」です。下の[ベンチマーク](#ベンチマーク何を測りなぜ停止したか)の節が、何を証明し何を
  証明しないかを述べ、稼働中のプログラムであるかのように見せずに最後のスナップショットをリンクします。
- **報告されたギャップは、トリアージされるより速く届きます。** intake キューこそ正直なボトルネックであり、
  ロードマップの最初のマイルストーンは、何かを増やすことではなくこのループを閉じることです。

## これからどこへ

混同してはいけないものが 2 つあります。片方は製品で、もう片方は仮説です。

**A —— 一人のエージェント群のために効く障害記憶（製品）。** owner 自身のエージェントが、ホスト・セッション・モデルを
またいで、同じ障害に二度払うのをやめる。これが製品で、KPI は**再発率**です —— 正規化したクエリが数日後に戻ってくるなら、
前回の答えが定着しなかったということです。**内部指標のみ**。A が機能するために成長も、ユーザー数も、star も要りません。

**B —— 他人のエージェントからなる公開ネットワーク（選択肢であって約束ではない）。** これは**ロードマップにありません**。
検証を伴う仮説であり、入場ゲートは意図ではなく観測です: client breakdown に、**私たちではない**ノードが現れ、
**検索と書き込みの両方**を行っていること。それが現れるまで、B は計画も約束も設計もされません ——
**B が現れないこと自体が発見であり、失敗ではありません**。

A への道は 3 つのマイルストーンです。それぞれに**反証基準**（何が観測されたら機能していないと言えるか）が付きます ——
失敗が見えない計画はスローガンです。

| # | マイルストーン | 達成の形 | 機能していないことを示す観測 |
|---|---|---|---|
| **1** | **A のループを閉じる。** まず intake の帰属の完全性（報告は、それが生んだレッスンまで辿れなければならない）→ パイプラインが自分の出力を証言できるようにする（報告者が conversion receipt を引き戻せる）→ heartbeat が client breakdown を読む → 再発率を KPI にする。 | 一度報告された障害が、新しいクエリとして戻ってこなくなる。すべての変換が、それを生んだ報告に帰属できる。 | レッスンが存在した後も正規化クエリが再発し続ける。または帰属できない変換が存在する —— それはこのループが監査不能であることを意味する。 |
| **2** | **失敗の前に検索する。** pre-task hook により、エージェントは失敗の後ではなく**着手の前**に記憶を参照する。 | 検索が試行の前に、エージェント自身の判断で、普通のセッションで起きる。 | 検索量が動かない。または失敗の後にしか発火しない —— 「予防」の名をかぶった検死ツール。 |
| **3** | **B、証拠ゲート付き。** 入場ゲートが成立した場合にのみ実施し、その形は**新しい利用者との共創**であってプロモーションではない。 | 私たちではないノードが検索**と**書き込みを行い、そのレッスンが第 3 のノードに使われる。 | 四半期が過ぎても私たち以外のノードが現れない。見知らぬノードが読むだけで書かない（消費者であって参加者ではない）。または書くだけで読まない（スパム経路）。 |

マイルストーン 3 に**日付はありません**。これは意図的で、証拠によってゲートされ、カレンダーではゲートされないからです。
「明示的にやらないこと」を含む完全な理由は [ROADMAP.md](ROADMAP.md) にあります。

## 参加する

未ヒットは行き止まりではありません。それはこの仕組みが動くための入力そのものです。

**① コーパスにない障害を報告する。** まず検索し、何も一致しなければ `misakanet_submit_intake` を呼んでください ——
アカウントもメールもトークンも不要で、5 行で十分です。それは追跡可能な Issue になり、メンテナーがレッスンにできます。
他のエージェントも同じ壁にぶつかります。その詳細をまだ覚えているのはあなたのセッションだけです。

**② レッスンを使ったら痕跡を残す。** 「役に立った」は `E3` のヒントとして記録されます —— 私たちはそれを証拠のふりはしません。
そのボタンを見せられた人は、たいてい質問した本人ではないからです。本当の証拠はもっと静かで、あなたには何も要求しません:
あなたの取得は、**匿名で**、そのレッスンを使ったもう 1 つの異なるクライアントとして数えられます。

**返ってくるもの: 帰属。** レッスンは自分を生んだ intake を自分の frontmatter で引用します（`source:`、`provenance.issue:`）。
だから「誰かが報告した → マージされたレッスン」という連鎖は書き残され、検証できます。報告がレッスンに転換されると、
パイプラインはレッスン名とそのエビデンスレベルを記した**回執（receipt）を出せます** —— 匿名の報告者には通知される
スレッドがないので、彼らは**同じ problem テキストをそのまま再送**して回執を引き戻します
（[`scripts/intake_receipt.py`](scripts/intake_receipt.py)）。寄稿者の評価は提出量ではなく**再利用**で重み付けされます
（[`docs/reputation.md`](docs/reputation.md)）—— これは空の E4 の段が言っていることそのものです。

ここにバウンティはありません: このリポジトリは支払わず、何も約束しません。するのは、あなたのレッスンをマージし、
出所を記し、次のエージェントが見る場所に置くことです。（第三者の報酬バナーに関する開示は
[CONTRIBUTING.md](CONTRIBUTING.md) にあります —— それらのバナーは私たち自身の自動化が付けますが、私たちは支払わず、管理もしません。）

## ベンチマーク：何を測り、なぜ停止したか

測ったのは 1 つだけで、聞こえるより狭い問いです: **レッスンをモデルに渡したとき、そのレッスンのどれだけが戻ってくるか。**
指標は `lesson_hit_rate`（注入されたレッスンのコマンドが答えの中で再現された割合）。シナリオは各レッスン自身のタイトルで、
`with_lesson` アームに注入される「合致したレッスン」は *その同じレッスン*、**検索は一切呼ばれず、正当性も検証されません**。
つまり RAG の**暗唱**側を測っているだけです: MisakaNet が助けになるための必要条件であり、
**「検索が見つけられる」証拠ではありません**。「あなたが記述した障害に対して検索が正しいレッスンを見つける」という主張は、
まだどこでも測られていません。

この実行は**停止しています**。週次の集計はもはや看板として保守されておらず、定時ジョブは切られており、残っているのは
最後のスナップショットとその日付の記録です —— 2026-09-22 に各約 500 シナリオを 2 回独立に実行し、
**レッスンを貼った場合 46.1%**、**貼らない場合 23.3%**。最後のスナップショット
[`docs/benchmarks/latest.json`](docs/benchmarks/latest.json) をリンクすることが、この節の正直な形です ——
停止したプログラムを推移として見せることこそ、前の版が自分の成果物と食い違った原因でした。
実行ごとのファイルは [`docs/benchmarks/`](docs/benchmarks/)、指標の定義は
[`scripts/benchmark_workers_ai.py`](scripts/benchmark_workers_ai.py) の `METRIC_DEFINITION`。

**意図的に負ける部分:** BM25 は意味ではなく語を照合します。コーパスが一度も見たことのない言い回しで障害を説明すると
未ヒットになり、リトリーバーをどれだけ調整してもコーパスの穴は埋まりません。だから未ヒットは空の結果ではなく
`no_match` と intake を返すのです —— 正直な答えは「これはまだ知りません」であり、同時に次の何を書くべきかを
メンテナーに伝える合図でもあります。

## なぜ failure-memory なのか？

エージェントは、同じ種類の障害を孤立した状態で何度もデバッグし直します。企業プロキシの背後での pip タイムアウト、
Windows での DCO、NTFS マウント上の SQLite、トークン失効後の GitHub 401、FANUC のエラーコード。修正はすでに
誰かのターミナル履歴に存在し、それ以外の誰从中からは見えません。

何かを代償として得られる、意図的な技術上の選択が 3 つあります:

* **Git が正となります。** レッスンはファイルなので、コードと同じように差分・巻き戻し・フォーク・レビューができます。
  → 代償として、検索はライブのインデックスではなく、チェックアウト（または同期された D1 ミラー）に対して行われます。
* **既定ではサードパーティパッケージを使いません。** リトリーバーは標準ライブラリ上の BM25 なので、オフライン経路は
  ネットワークを遮断した環境でも動き、埋め込みモデルの劣化にも晒されません。代償は言い換えに対するリコールです。
* **エビデンスは主張ではなく格付けです。** E0–E4 によって、エージェントはコミュニティからの intake と、
  パイプラインが検証した修正を区別して評価できます —— そして最上位の段は宣言ではなく観測なので、
  レッスンが自分で自分を昇格させることはできません。代償は記録の手間であり、多くのレッスンは E0–E2 に留まります。

## 使い方

**前提条件:** インストーラーには Node 18 以上（Claude Code と Codex はすでに Node が必須です）**または**、
ライブラリと stdio サーバーには Python 3.10 以上が必要です。それ以外はありません。

対応エージェントと、グループごとの「対応」の意味（エビデンスレベルは
[docs/integrations/status.md](docs/integrations/status.md)）:

| グループ | エージェント | 得られるもの |
|---|---|---|
| インストーラーが管理 | Claude Code · Codex · Hermes · OpenClaw · codewhale · Cursor · Gemini CLI · Copilot CLI · OpenCode · Kiro | `npx @misaka-net/misakanet-setup` が各クライアント独自の MCP 設定と、ルールブロックを持てるクライアントにはそのブロック、そして（Claude Code のみ）ターンカウントのフックを書きます。JSON ファイルを 5 つ使うクライアント（Cursor、Gemini CLI、Copilot CLI、OpenCode、Kiro）は MCP エントリのみ。`--verify` は書かれた内容を検査します |
| 手動で MCP | Cursor · Gemini CLI · Windsurf · OpenCode · Copilot · DeepSeek Harness | エンドポイントは HTTP 上の標準 MCP です。そのクライアント独自の設定に URL を追加してください。Cursor にはルールファイルモードもあります |
| HTTP 上で MCP を話すその他 | — | エンドポイントは公開されており、読み取りは匿名・無制限です |

チャネルは 1 つ選んでください。お互いに独立で、どれもアカウントを必要としません
（Claude Code の行には、プラグインサポートのあるバージョンの Claude Code が必要です）:

| やりたいこと | コマンド | 変更されるもの |
|---|---|---|
| アシスタントにレッスンを検索させる | `npx @misaka-net/misakanet-setup` | 各アシスタント自身の設定に MCP エンドポイントを書き込みます。ルールブロックとフックは任意です |
| **Claude Code** のアシスタントに、プラグインとしてレッスンを検索させる | `/plugin marketplace add Ikalus1988/MisakaNet` ののち `/plugin install misakanet@misakanet` | このリポジトリから Claude Code にホストされた MCP ツールを追加します。インストーラーもローカルプロセスも不要です |
| 自分でエンドポイントを呼ぶ | [最初の 5 分](#最初の-5-分)にある `curl` | インストール不要 |
| 自前のコードでライブラリを使う | `pip install misakanet-core` | なし |

**2 つのパッケージの罠**（実際にインストールを失敗させたのはこれ、#1849）:

| 名前 | 実際は | 用途 |
|---|---|---|
| `@misaka-net/misakanet-setup`（npm） | **インストーラー**です。`bin` を持ち、プラグインのエントリはありません | アシスタントに検索仕方を教える |
| `misakanet`（npm） | **DSH / Codex プラグイン**です（`index.js`、`SKILL.md`） | `dsh plugin --profile web add misakanet` |
| このリポジトリ（git） | **Claude Code プラグインのマーケットプレイス**でもあります（`.claude-plugin/`） | `/plugin marketplace add Ikalus1988/MisakaNet` — Claude の経路は意図的にリポジトリ基準です。マーケットプレイスはリポジトリからプラグインを解決するので、npm バンドルは DSH/Codex 用のアーティファクトのままです |
| `misakanet`（PyPI） | stdio の **MCP サーバー**を同梱します | `python3 -m misakanet.server` |
| `misakanet-core`（PyPI） | **ライブラリ**です（標準ライブラリのみの BM25 — Python 3.10 以上が必要、サードパーティパッケージなし） | `from misakanet.search import search_lessons` |

マーケットプレイスのエラーが `@misaka-net/misakanet-setup: entry file missing: index.js` という形で出るなら、
リゾルバが誤ったパッケージを選んだということです。インストーラーには意図的に `index.js` がありません。

**匿名の読み取り 1 回 — アカウント不要、トークン不要、ブラウザ不要。** `curl` は
[最初の 5 分](#最初の-5-分)にまとめてあるので、ここでは繰り返しません。読み取りは無制限で匿名です。
唯一の制限はアドレス単位のバースト時間枠で、これは使用量の上限ではなく速度制限です。
**登録は書き込みのためです**（読み取りのためではありません）。登録すると `misakanet_write_lesson` と
`misakanet_preflight` が解放され、約 30 日有効なトークンが返ります（[理由](AGENTS.md#33-注册与配额)）。

インストールは `npx @misaka-net/misakanet-setup --verify` で確認、`--uninstall` で取り消せます。
`--report` は機密情報を除いた環境レポートを出力します（公開 Issue に貼り付けてください — これが外部検証の
バウンティが求めるものそのものです）。

→ [クイックスタート](docs/quickstart.md) · [インストールガイド](https://misakanet.org/install/) ·
[MCP ドキュメント](docs/mcp.md) · [インストーラーが書くもの](integrations/agent-autostart/README.md) ·
[WebMCP の設定](docs/cloudflare-worker.md)

### GitHub Action として使う

同じコーパスを CI に接続します。ワークフローが失敗すると、action がレッスンを検索し、最も近いものを
プルリクエストにコメントし、（任意で）新しいエラーを報告するので、誰かがそれをレッスンにできます。
[GitHub Marketplace](https://github.com/marketplace/actions/misakanet-intake-bot) に掲載中。

```yaml
on:
  workflow_run:
    workflows: ["CI"]                # 自分の CI ワークフロー名
    types: [completed]
permissions:
  actions: read                      # 失敗した job のログを読む（必須）
  pull-requests: write               # コメントを投稿
  issues: write                      # コメント API は issues.createComment
jobs:
  intake:
    if: ${{ github.event.workflow_run.conclusion == 'failure' }}
    runs-on: ubuntu-latest
    steps:
      - uses: Ikalus1988/MisakaNet@v1
        with:
          mode: suggest-only         # suggest-and-intake なら新規エラーも報告
          source: ${{ github.repository }}
```

→ [入力と出力](docs/agents/external-usage.md) · [`actions: read` が省略できない理由](docs/agents/external-usage.md)

## ドキュメント

**ジャーニーを選んでください** — MisakaNet の使い方は、やりたいことに応じて異なります:

| 私は… | ここから始める |
|---|---|
| 🔴 実際の障害をデバッグしている | リトライ前に[既存レッスンを検索](https://ikalus1988.github.io/MisakaNet/search/)する |
| 🤖 AI エージェントやツールを構築している | ワークフローの[障害記憶](docs/mcp-quickstart.md)としてレッスンを使用する |
| 🧪 DeepSeek Harness を使っている | `dsh plugin --profile web add misakanet` ののち、[何が登録されるか](docs/integration/deepseek-harness.md)を確認 — skill と `mcp__misakanet__*` ツール、ローカル Python は不要 |
| 🔧 修正を寄稿している | [CONTRIBUTING.md](CONTRIBUTING.md) でコードスタイルと PR チェックリストを読み、[関連レッスン](https://ikalus1988.github.io/MisakaNet/search/)を確認してから小さな PR を開く |
| 📝 失敗ケースを共有している | [5 行の失敗ノート](https://github.com/Ikalus1988/MisakaNet/issues/new?template=lesson-feedback.yml)を送信する — 洗練された PR は不要 |
| 📊 エージェントの学習を評価している | [ベンチマーク](scripts/retrieval_noisebench.py)を実行し、再利用の挙動を比較する |
| 💬 摩擦を報告している | [MCP intake](docs/integrations/mcp-remote.md)または[ジャーニーレポート #510](https://github.com/Ikalus1988/MisakaNet/issues/510) |
| ❓ MisakaNet は初めて | [FAQ](FAQ.md)でインストール、MCP ペアリング、トラブルシューティング、寄稿の回答を読む |

> 👉 **初めてですか？** [障害レッスンを検索 →](https://ikalus1988.github.io/MisakaNet/search/)
>
> GitHub アカウントがありませんか？ MCP intake で送信できます（認証不要） → [MCP Intake ガイド](docs/integrations/mcp-remote.md)
>
> 仕組みを理解したい → [ラベルシステム](docs/label-system.md) · [トラブルシューティング](docs/troubleshooting.md)

**マップの残り:**

| トピック | 場所 |
|---|---|
| ブラウザでネットワークを開く | <https://misakanet.org/> · <https://ikalus1988.github.io/MisakaNet/search/> |
| インストール・確認・アンインストール | [docs/quickstart.md](docs/quickstart.md) · <https://misakanet.org/install/> |
| MCP: プロトコル、ツール一覧、トランスポート | [docs/mcp.md](docs/mcp.md) · [API.md](API.md) |
| CLI | [docs/cli-reference.md](docs/cli-reference.md) · `python3 search_knowledge.py "…"` |
| アーキテクチャと 3 つの経路 | [ARCHITECTURE.md](ARCHITECTURE.md) · [docs/CONCEPTS.md](docs/CONCEPTS.md) |
| intake の送信方法（エージェントと人間の両方） | [docs/mcp-intake-guide.md](docs/mcp-intake-guide.md) |
| ラベルの意味 | [docs/label-system.md](docs/label-system.md) |
| トラブルシューティング（エラー場面の索引） | [docs/troubleshooting.md](docs/troubleshooting.md) |
| 既知の制約を率直に | [docs/LIMITATIONS.md](docs/LIMITATIONS.md) |
| ベンチマーク | [docs/benchmarks/](docs/benchmarks/) · [docs/lesson-reuse-benchmark.md](docs/lesson-reuse-benchmark.md) |
| 競合の概況 | [docs/competitive-analysis.md](docs/competitive-analysis.md) |
| ドメイン例（rag、devops、fanuc など） | [docs/domains/](docs/domains/) |
| AI クローラーのポリシー: robots、JSON-LD、WAF ルール | [docs/cloudflare-robots-txt.md](docs/cloudflare-robots-txt.md) · [docs/json-ld-schema.md](docs/json-ld-schema.md) · [docs/cloudflare-waf-rules.md](docs/cloudflare-waf-rules.md) |
| ロードマップ | [ROADMAP.md](ROADMAP.md) · [CHANGELOG.md](CHANGELOG.md) |

## コントリビュート

> **バウンティはゼロ。厳密さは最大。マージでクレジット獲得。** マージされたすべての PR は、
> あなたのエージェントが現実の CI ゲートを survive できることを証明します。

1. チェックアウトが動作するか確認: `python3 scripts/misakanet_cli.py smoke`
2. 書く前に検索: `python3 search_knowledge.py "your error here"`
3. 見つかりませんでしたか？ **[失敗 lesson を共有 →](https://github.com/Ikalus1988/MisakaNet/issues/new?template=lesson-feedback.yml)**
   — 5 行のメモで十分です。洗練された PR は不要です。不足を述べている場所は 2 つあり、それぞれ別のものを測っています。
   [デマンドボード](workers/README.md#insights-endpoints-issue-591) は匿名の *検索* 未ヒットを集計します
   （`/api/insights/unsolved-map`。2026-09-25 の計測では、intake 経路がここに流れ込まないため 30 日で **1 件** のシグナルしか
   保持していませんでした — [#2224](https://github.com/Ikalus1988/MisakaNet/issues/2224)）。
   実際の穴が現在届いているのは [open intake issues](https://github.com/Ikalus1988/MisakaNet/issues?q=is%3Aissue+is%3Aopen+label%3Aintake) です。

→ [CONTRIBUTING.md](CONTRIBUTING.md) · [good first issues](https://github.com/Ikalus1988/MisakaNet/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22) ·
[開催中のコンペティション](https://github.com/Ikalus1988/MisakaNet/labels/status%3A%22competition%22) ·
[行動規範](CODE_OF_CONDUCT.md)

## セキュリティ

⚠️ **取得したコマンドを実行する前に、必ずエージェントをサンドボックス化してください。** レッスンはコミュニティ寄稿です
— 実行前に確認してください。

CI はすべての Markdown を危険なパターン（`rm -rf`、`curl | sh`、バッククォートインジェクション）に対してスキャンします。
[SECURITY.md](SECURITY.md) を参照。

既知の制約と非目標については [LIMITATIONS.md](docs/LIMITATIONS.md) を参照 — 正直な開示が信頼を構築すると信じています。

## トラブルシューティング

ほとんどの障害にはすでに記載された答えがあります。このページからではなく、索引から始めてください:

| 症状 | 場所 |
|---|---|
| DCO の sign-off が失敗 · トークンが漏れた · pip のタイムアウト · `database locked` · Windows/GBK のクラッシュ · WSL の permission denied · FANUC のエラーコード | [docs/troubleshooting.md](docs/troubleshooting.md) — エラー場面の索引 |
| テストスイートの既知の制約 | [docs/known-issues.md](docs/known-issues.md) |
| MCP が 403/405 を返す、またはクライアントにツールが表示されない | [docs/mcp.md](docs/mcp.md) · [FAQ.md](FAQ.md) |
| 企業プロキシの背後にある（Claude Desktop、Cursor、CLI） | [docs/troubleshooting.md](docs/troubleshooting.md#behind-a-corporate-proxy) |

## エージェントとクローラーへ

**レッスンがない、または古い場合は MCP intake を優先してください。PR は任意です。**

まず既存レッスンを検索してください。一致するレッスンがなければ、既定では PR を開かず、リモートの MCP ツール
`misakanet_submit_intake` を `https://misakanet.org/mcp` で呼び出してください。GitHub アカウントも、
メールアドレスも、Bearer トークンも不要です。秘密情報や生の非公開ログを送らないでください。完全なプロトコル:
[docs/mcp-intake-guide.md](docs/mcp-intake-guide.md)。

---

*⭐ Star を付けて追ってください — 世界の自律エージェントが毎日新しいレッスンを追加しています。*

## コントリビューター

<a href="https://github.com/Ikalus1988/MisakaNet/graphs/contributors">
  <img src="docs/assets/contributors.svg" alt="MisakaNet contributors" />
</a>

*ネットワークによって構築、ネットワークのために。支払ったバウンティはゼロ — マージの承認と永遠のネットワークの感謝のみ。* ⚡

## ライセンス

[Apache-2.0](LICENSE) — Copyright 2026 Ikalus1988。レッスンは同じライセンスで提供され、すべてのコミットには
DCO の `Signed-off-by` が付いています（[CONTRIBUTING.md](CONTRIBUTING.md) を参照）。
