# Scrapling 集成评估

> 评估日期：2026-06-15 | 评分时间
> 仓库：https://github.com/D4Vinci/Scrapling | 63.7k stars | BSD-3-Clause

---

## 一、Scrapling 是什么

一个自适应的 Web Scraping 框架，核心能力：

- **Parser** — CSS/XPath 选择器 + 自适应元素定位（网站改版后自动重定位）
- **Fetchers** — 多种请求引擎（StealthyFetcher 可绕过 Cloudflare Turnstile 等反爬）
- **Spiders** — 并发爬虫框架，支持暂停/恢复/代理轮换
- **MCP 服务** — 可通过 MCP 协议调用爬取能力
- **CLI** — `scrapling extract` 命令行工具

---

## 二、与 MisakaNet 的集成价值

| 集成场景 | 价值 | 优先级 | 说明 |
|---------|------|--------|------|
| **Web → Lesson 收割** | 🔴 高 | P0 | 从网页（文档/GitHub Issues/StackOverflow）提取内容自动生成 lesson |
| **Reference 自动采集** | 🟡 中 | P1 | 爬取文档站补充 reference/ 目录 |
| **Agent 在线检索增强** | 🟢 低 | P2 | 搜不到本地 lesson 时自动查网页 |
| **MCP 互联** | 🟢 低 | P2 | Scrapling 的 MCP 服务与 MisakaNet 的 MCP 生态互通 |

### 当前落地

已创建 `scripts/misaka_harvest.py`：
- `python3 scripts/misaka_harvest.py --url <URL> --domain <domain>`
- 自动提取标题、段落、代码块 → 生成标准 lesson markdown
- 输出到 `lessons/contrib/web-*.md`，带 frontmatter
- 可选依赖：`pip install "misakanet[harvest]"`
- 支持 `--body` 模式（无 fetcher 时手动传入内容）

---

## 三、使用门槛

| 方式 | 安装 | 首次使用耗时 |
|------|------|------------|
| 纯 parser 模式（解析已有 HTML） | `pip install scrapling` | < 30 秒 |
| 完整 fetcher 模式（含反爬绕过） | `pip install "scrapling[fetchers]"` + `scrapling install` | ~2-3 分钟（下载浏览器） |
| Docker | `docker pull pyd4vinci/scrapling` | ~30 秒 |

---

## 四、风险与限制

| 风险 | 说明 | 缓解 |
|------|------|------|
| 依赖体积大 | Fetcher 模式需下载 Chromium (~200MB) | 作为可选依赖，非核心路径 |
| 生成质量不稳定 | 自动提取的内容可能不完整 | 生成后标为 draft，需人工 review |
| 法律合规 | 爬取第三方网站需遵守 robots.txt | 工具本身不鼓励违规，用户自行负责 |

---

## 五、结论

**推荐集成级别：可选工具（optional tooling）**

Scrapling 作为 lesson 自动收割工具有明确价值，但不属于 MisakaNet 核心能力。当前集成状态：

- [x] `pyproject.toml` 添加 `harvest` 可选依赖
- [x] `scripts/misaka_harvest.py` 收割脚本
- [x] `misaka-harvest` CLI entry point
- [ ] 文档：待补充至 README / docs/
