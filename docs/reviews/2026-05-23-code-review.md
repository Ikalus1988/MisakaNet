# MisakaNet 代码审查 + 新用户旅程评测报告

> 审查人：10年经验高级软件工程师（挑剔视角）
> 仓库：https://github.com/Ikalus1988/MisakaNet
> 日期：2026-05-23
> 统计：38个Python文件，7,288行代码，7个文件标记为DEAD CODE

---

## Part A — 代码审查问题清单

### 🔴 Critical

#### C1. GitHub PAT 明文硬编码在前端 HTML 中（docs/index.html:780,797,1538）

**文件**: `docs/index.html` 行 780, 797, 1538
**问题**: 一个完整的 GitHub Fine-grained PAT 以十六进制编码形式嵌入在公开的前端 HTML 中。任何访问网站的人都可以通过浏览器 DevTools 或直接解码 hex 字符串获取该 token。hex 前缀 `6769746875625f7061745f` 解码为 `github_pat_`，后面跟完整 token 值。该 token 被用于让新用户直接 curl 创建 Issue 加入网络——这意味着该 token 至少拥有 `issues:write` 权限。**这是公开仓库，全世界都能看到这个 token。**

**严重程度**: Critical
**影响**: 攻击者可利用该 token 对仓库执行其权限范围内的所有操作（创建/修改 Issue、可能更多），并可进一步枚举组织内其他仓库。
**修复建议**:
1. **立即撤销该 token**（GitHub Settings → Developer settings → Fine-grained tokens）
2. 改用 GitHub OAuth App 流程，让用户自己授权，token 不经过前端
3. 如果必须保持无认证加入，使用 `GITHUB_TOKEN` 在 GitHub Actions 中处理，绝不暴露到前端
4. 已泄露的 token 即使撤销也可能被缓存，需审计该 token 的访问日志

---

#### C2. register.yml 竞态条件 — counter.json 非原子更新（.github/workflows/register.yml:31-71）

**文件**: `.github/workflows/register.yml` 行 31-71
**问题**: 多个注册请求并发时，Workflow 各自读取 counter.json → +1 → 写入 → push。虽然用了 `git push --force` 失败重试（5次），但这不是真正的原子操作：
- 两次 push 之间可能已经生成了相同的头像文件
- `git push --force` 会覆盖其他并发注册的提交，导致头像或 counter 丢失
- 使用 `--force` 而非 `--force-with-lease` 更增加了覆盖风险

**严重程度**: Critical
**影响**: 并发注册时节点编号冲突、头像丢失、counter 回退。
**修复建议**:
1. 使用 GitHub API 的 `issues.createComment` 原子分配编号，或
2. 使用外部原子计数器（如 Redis、GitHub Actions 的 `concurrency: group` 串行化），或
3. 至少改用 `git push --force-with-lease` 并增加重试间隔

---

#### C3. pickle 反序列化漏洞 — 任意代码执行（storage/knowledge_graph.py:37）

**文件**: `storage/knowledge_graph.py` 行 37
**问题**: `pickle.load(f)` 直接从磁盘反序列化。如果攻击者能替换 `graph.gpickle` 文件（例如通过 git 供应链攻击或文件系统写入），则可实现任意代码执行。pickle 反序列化是 Python 中已知的最危险反模式之一。

```python
with open(self.persist_path, 'rb') as f:
    self.graph = pickle.load(f)  # 💀
```

**严重程度**: Critical
**影响**: 远程代码执行（如果攻击者能控制 .gpickle 文件）
**修复建议**:
1. 改用 JSON 序列化（NetworkX 支持 `node_link_data`/`adjacency_data`），或
2. 使用 `networkx.readwrite.json_graph` 模块
3. 如果必须用二进制格式，使用 `safen` / `dill` 并限制反序列化类白名单

---

#### C4. 3个脚本直接读取 ~/.git-credentials 明文 token（feedback_report.py:69, queue_hook_stats.py:179, queue_lesson.py:40）

**文件**: `misakanet/scripts/feedback_report.py` 行 69, `misakanet/scripts/queue_hook_stats.py` 行 179, `misakanet/scripts/queue_lesson.py` 行 40
**问题**: 三个脚本直接 `open("~/.git-credentials").read()` 提取 GitHub token。这有几个严重问题：
1. `.git-credentials` 文件包含所有 GitHub 账号的明文凭证
2. 读取整个文件而非只用 token，增加了泄露面
3. 没有文件权限检查——如果文件是 644，其他用户可读
4. AGENTS.md:58 还指导用户执行 `echo "https://username:TOKEN@github.com" >> ~/.git-credentials`，鼓励明文存储

```python
creds = open(GIT_CREDS_PATH).read().strip()
token = creds.split(':')[-1].split('@')[0]
```

**严重程度**: Critical
**影响**: Token 泄露、其他用户可读取凭证、违反最小权限原则
**修复建议**:
1. 使用 `git credential fill` 协议安全获取 token
2. 或使用环境变量 `GITHUB_TOKEN` / `MISAKANET_TOKEN`（hub_poller.py 已有此模式）
3. 或使用 `keyring` 库（已在 requirements.txt 中但未使用）
4. 删除 AGENTS.md 中的明文凭证指导

---

### 🟠 Major

#### M1. lesson-notify.yml Shell 注入 — Issue body 未转义直接嵌入 curl（.github/workflows/lesson-notify.yml:28-45）

**文件**: `.github/workflows/lesson-notify.yml` 行 28-45
**问题**: Issue 的 `title` 和 `body` 直接作为 shell 变量 `$TITLE`、`$USER`、`$SUMMARY` 嵌入 curl JSON payload。攻击者可以在 Issue 标题或正文中注入 shell 命令或 JSON 特殊字符，导致：
1. Shell 命令注入（通过 `$TITLE` 等）
2. JSON 注入（通过 `$(cat <<PAYLOAD ... PAYLOAD)` heredoc 中的变量展开）
3. 飞书 Webhook 被滥用发送任意消息

```yaml
TITLE: ${{ github.event.issue.title }}   # 直接展开到 shell
USER: ${{ github.event.issue.user.login }}
BODY: ${{ github.event.issue.body }}
```

**严重程度**: Major
**影响**: 任意 shell 命令在 CI 中执行，或飞书 Webhook 被劫持
**修复建议**:
1. 使用 `actions/github-script` 而非 shell 脚本，避免变量展开
2. 或使用 `jq` 构造 JSON payload 而非 heredoc
3. 对所有用户输入做 `printf '%s' "$VAR"` 处理

---

#### M2. torch/transformers 硬依赖但未列入 requirements.txt（orchestrator/skill_indexer.py:10-11）

**文件**: `orchestrator/skill_indexer.py` 行 10-11
**问题**: `import torch` 和 `from transformers import AutoModel, AutoTokenizer` 是顶层无条件导入。但 `requirements.txt` 中 `torch` 和 `transformers` 被注释为 `# Optional`。这意味着：
1. `pip install -r requirements.txt` 后导入 SkillIndexer 直接报 ImportError
2. BGE-m3 模型需要 ~2GB 磁盘空间和 CUDA，但文档未提及
3. 没有降级路径——虽然 `_init_embedding_model` 有 try/except，但顶层 `import torch` 在模块加载时就崩溃

```python
import torch                          # 顶层导入，无法降级
from transformers import AutoModel, AutoTokenizer
```

**严重程度**: Major
**影响**: 核心模块无法导入，安装后即崩溃
**修复建议**:
1. 将 `import torch` 和 `from transformers import ...` 移入 `_init_embedding_model()` 方法内部
2. 或在 requirements.txt 中取消注释并添加 `torch`、`transformers`
3. 添加清晰的安装说明：`pip install misakanet[embedding]` 可选依赖组

---

#### M3. SQLite 连接无上下文管理器 — 连接泄漏风险（arbitration_queue.py, subscription.py 全文件）

**文件**: `orchestrator/arbitration_queue.py` 全文件, `orchestrator/subscription.py` 全文件
**问题**: 所有 SQLite 操作使用 `conn = sqlite3.connect()` + 手动 `conn.close()`，而非 `with sqlite3.connect() as conn:`。如果操作中间抛异常，连接永远不会关闭。多个位置的模式：

```python
conn = sqlite3.connect(self.db_path)
cursor = conn.cursor()
cursor.execute(...)  # 如果这里抛异常，conn 永远不关闭
conn.commit()
conn.close()
```

**严重程度**: Major
**影响**: 连接泄漏导致 SQLite 锁定、资源耗尽
**修复建议**: 使用 `with sqlite3.connect(self.db_path) as conn:` 上下文管理器

---

#### M4. A2A 服务绑定 0.0.0.0 — 默认暴露到所有网络接口（sync/a2a_server.py:44）

**文件**: `sync/a2a_server.py` 行 44
**问题**: A2A server 默认绑定 `0.0.0.0:8081`，且无任何认证/授权机制。虽然标记为 DEAD CODE，但如果有人尝试使用它：

```python
def __init__(self, host: str = "0.0.0.0", port: int = 8081):
```

**严重程度**: Major
**影响**: 如果启用，任何网络可达的人都能访问 A2A API
**修复建议**: 默认绑定 `127.0.0.1`，添加 API key 认证

---

#### M5. 飞书 WebSocket Token 通过 URL Query 传递（sync/feishu_ws_client.py:85）

**文件**: `sync/feishu_ws_client.py` 行 85
**问题**: tenant_access_token 通过 URL query string 传递：`ws_url + f"?token={token}"`。这会导致 token 出现在：
1. 代理服务器日志
2. 浏览器历史（如果有）
3. 网络抓包

```python
ws_url = self._get_websocket_url() + f"?token={token}"
```

**严重程度**: Major
**影响**: Token 可被中间人或日志泄露
**修复建议**: 使用 WebSocket 协议的 `Sec-WebSocket-Protocol` header 传递 token，或使用飞书 SDK 推荐的认证方式

---

#### M6. 7/38 个文件标记为 DEAD CODE — 仓库 18% 是死代码

**文件**: `hermes_hub.py`, `master/command_handler.py`, `master/master_api.py`, `orchestrator/dedup_engine.py`, `storage/knowledge_graph.py`, `sync/a2a_server.py`, `sync/sync_scheduler.py`
**问题**: 7个文件（占代码库 18%）被标记为 DEAD CODE 或已废弃。这导致：
1. 新贡献者无法判断哪些代码在用
2. 依赖关系混乱（如 dedup_engine.py 导入 vector_store.py）
3. 测试覆盖死代码而非活代码
4. 维护负担——每次修改活代码时要考虑死代码是否受影响

**严重程度**: Major
**影响**: 项目可维护性严重下降
**修复建议**:
1. 将死代码移到 `archived/` 目录或单独分支
2. 或彻底删除（git history 保留记录）
3. 在 README 中明确标注哪些模块是活跃的

---

### 🟡 Minor

#### m1. 全局 print 替代结构化日志（全部文件）

所有模块使用 `print()` 输出日志，无日志级别控制，无格式化，无法在生产环境关闭 debug 输出。
**修复**: 使用 `logging` 模块。

#### m2. confidence.py 时区处理不一致（orchestrator/confidence.py:83-92）

`datetime.fromisoformat(indexed_at)` 解析的时间可能是本地时区，但 `datetime.now(timezone.utc)` 是 UTC。虽然后面做了 `replace(tzinfo=tz.utc)` 补偿，但这只是假设输入是 UTC，而非正确处理时区。

#### m3. 测试仅覆盖导入（tests/test_imports.py）

77行测试全部是 `__import__` 测试，零功能测试、零集成测试、零边界测试。没有 pytest 框架，没有断言逻辑。

#### m4. vector_store.py 多处 bare except 吞掉异常（storage/vector_store.py:25,65）

`except Exception:` 和 `except Exception:` 吞掉所有异常返回 None/False，调试时无法定位问题。

#### m5. skill_indexer.py 模块级类变量共享状态（orchestrator/skill_indexer.py:21-24）

`_embedding_model = None` 等类变量在多实例场景下共享，可能导致意外状态共享。

---

## Part B — 新用户旅程评测

### 1. 安装体验 — 6/10

**卡点记录**:
- README 写了 `pip install -r requirements.txt`，但核心依赖 `torch`、`transformers` 被注释掉了
- 安装后 `import SkillIndexer` 直接报 ImportError（M2）
- 没有 `setup.py` / `pyproject.toml`，无法 `pip install misakanet`
- AGENTS.md 指导用户明文存储 GitHub token（C4）
- `config.yaml.example` 存在但无说明如何配置

**改进建议**:
- 添加 `pyproject.toml`，提供 `[embedding]` 可选依赖组
- 安装文档明确说明：最小安装 vs 完整安装
- 移除明文 token 指导

### 2. 首次运行 — 5/10

**卡点记录**:
- 无 `__main__.py` 入口，无 CLI 命令，新用户不知道该运行哪个文件
- `hermes_hub.py` 是核心入口但标记为 DEAD CODE
- 没有任何示例脚本或 quickstart 命令
- `test_imports.py` 是唯一可运行的脚本，但那只是测试

**改进建议**:
- 添加 `misakanet` CLI 入口（`python -m misakanet`）
- 提供一个 `examples/quickstart.py`
- README 添加 "30秒上手" 区块

### 3. 功能探索 — 6/10

**卡点记录**:
- 7个核心文件是 DEAD CODE，功能列表与实际可用代码严重不符
- 知识图谱存储用 pickle，不可人工检查
- Skill 索引需要 BGE-m3 模型（2GB+），但文档未提及下载方式
- 仲裁队列、订阅系统看起来完整但无法端到端验证

**改进建议**:
- 每个模块提供最小可运行示例
- 清晰标注"已实现" vs "设计中"
- 提供 mock 模式绕过 GPU 依赖

### 4. 文档质量 — 5/10

**卡点记录**:
- 信息散落 5 处：README、JOIN.md、AGENTS.md、CLAUDE.md、docs/wiki/
- 没有统一的 API 文档
- 架构图仅在 CLAUDE.md 中用文字描述
- docs/index.html 是精美的展示页，但"如何使用"信息为零
- `skills/SKILL.md` 内容与项目无关（引用了 Hermes Agent 的 skill）
- `reference/` 目录为空
- 仓库 URL 占位符 `your-org` 未替换

**改进建议**:
- 合并所有文档到 docs/ 目录，README 只保留入口链接
- 添加架构图（Mermaid/ASCII）
- 清理无关内容

### 5. 社区支持 — 7/10

**优点**:
- GitHub Issues 模板设计良好（registration、new-lesson、usage）
- 飞书群通知自动化
- 节点注册流程有 GitHub Actions 自动化

**不足**:
- 没有讨论区/Discussions
- 没有 FAQ 或 Troubleshooting 文档
- 遇到 ImportError 只能看源码

---

## Part C — 给开发团队的公开信

---

**致 MisakaNet 开发团队：**

我用了两个小时深入阅读了你们仓库的每一行代码。说结论：这个项目的**愿景比工程水平领先了两个身位**。

御坂网络的架构设计——Hub + Node 异步通信、知识图谱仲裁、置信度衰减、语义去重——这些概念写在 PPT 上能拿到 A+。但代码层面，现实很骨感。

**第一，你们把 GitHub PAT 烤在了蛋糕上。**

不是藏在蛋糕里，是烤在了最外层。docs/index.html 里明晃晃的 hex 编码 token，任何会用 DevTools 的人 30 秒提取。这是公开仓库，全世界都是你的攻击面。这不是"隐蔽编码"——hex encoding 不叫加密，叫自欺。**请现在、立刻、马上撤销那个 token。**

**第二，18% 的代码是尸体。**

7 个文件标着 DEAD CODE，但还躺在主干里。新贡献者打开 `command_handler.py`，168 行全是死代码——你们在浪费每一个认真阅读代码的人的时间。Git history 会记住它们，别让 main 分支变成墓地。

**第三，你们的"安装"是个谎言。**

`pip install -r requirements.txt` 装完后，`import SkillIndexer` 直接炸。因为 `torch` 和 `transformers` 被注释掉了，但代码里无条件顶层导入。这不是"optional dependency"，这是"装了也跑不起来"。要么放到函数内延迟导入，要么老老实实写进 requirements。

**第四，安全不是装饰品。**

pickle 反序列化、~/.git-credentials 明文读取、Shell 注入式的 CI workflow、0.0.0.0 默认绑定——你们在 requirements.txt 里加了 `keyring`，但三个脚本直接 `open()` 读 git-credentials。买了灭火器不用，火灾时还在用嘴吹。

**最后，说句公道话。**

项目的 CI 自动化做得不错——register.yml 的节点编号分配、avatar 生成、飞书通知，这条链路是想清楚了的。仲裁队列和置信度模型的设计也是认真的。问题不是你们不会写代码，是你们在"造概念"和"写生产代码"之间选了前者，然后给后者打了折。

产品经理写的架构图，需要工程师来落地。现在这个仓库，是架构师的草稿，不是工程师的交付物。

**优先级排序：C1 撤销 token → C4 凭证读取 → C3 pickle → M2 依赖修复 → M6 清理死代码 → 其余。**

一个不安全的 demo，不如一个安全但简陋的 MVP。

—— 一个读了每一行代码的人

---

## 附录：问题汇总表

| ID | 严重度 | 文件 | 行号 | 问题 |
|----|--------|------|------|------|
| C1 | Critical | docs/index.html | 780,797,1538 | GitHub PAT hex 编码暴露在公开前端 |
| C2 | Critical | .github/workflows/register.yml | 31-71 | counter.json 非原子更新 + force push |
| C3 | Critical | storage/knowledge_graph.py | 37 | pickle 反序列化任意代码执行 |
| C4 | Critical | misakanet/scripts/*.py | 69,179,40 | ~/.git-credentials 明文读取 |
| M1 | Major | .github/workflows/lesson-notify.yml | 28-45 | Shell 注入（Issue body 未转义） |
| M2 | Major | orchestrator/skill_indexer.py | 10-11 | torch/transformers 顶层导入但不在 requirements |
| M3 | Major | orchestrator/arbitration_queue.py, subscription.py | 全文件 | SQLite 连接无上下文管理器 |
| M4 | Major | sync/a2a_server.py | 44 | 默认绑定 0.0.0.0 无认证 |
| M5 | Major | sync/feishu_ws_client.py | 85 | Token 通过 URL query 传递 |
| M6 | Major | 7个文件 | — | 18% 代码为 DEAD CODE |
| m1 | Minor | 全文件 | — | print 替代结构化日志 |
| m2 | Minor | orchestrator/confidence.py | 83-92 | 时区处理不一致 |
| m3 | Minor | tests/test_imports.py | — | 零功能测试 |
| m4 | Minor | storage/vector_store.py | 25,65 | bare except 吞异常 |
| m5 | Minor | orchestrator/skill_indexer.py | 21-24 | 类变量共享状态 |

**Critical: 4 | Major: 6 | Minor: 5 | 总计: 15**
