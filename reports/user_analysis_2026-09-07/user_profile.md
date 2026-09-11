# 用户画像分析报告

_报告生成于 2026-09-07T17:13:57.877681+00:00_

## 👤 身份识别

- **CF 账号**: Ikalus1988（来自 `intake` 中 jaco_sun 邮件正文）
- **邮箱**: ikalus1988@agent.qq.com → 节点 `Misaka10059`
- **项目**: MisakaNet（GitHub: Ikalus1988/MisakaNet，访问 https://github.com/Ikalus1988/MisakaNet/issues/*）
- **业务邮箱**: bot@misakanet.org → MisakaNet 系统的对外接收邮箱
- **OAuth scope**: 用了 wrangler 完整 scope（workers_kv:write, d1:write 等写权限），但实际只做读操作

## 🧠 技术栈画像（从 KV 数据推断）


### Agent / MCP 部署（19 种类型）

- `unknown`: 12 个 token
- `dsh`: 5 个 token
- `final-test`: 3 个 token
- `claude-code`: 3 个 token
- `deepseek-harness`: 2 个 token
- `hermes-agent`: 2 个 token
- `full-test`: 2 个 token
- `codex-issue-1240-smoke`: 2 个 token
- `kv-test`: 1 个 token
- `test-agent`: 1 个 token
- `deploy-test`: 1 个 token
- `codex-issue-1240-write-smoke`: 1 个 token
- `test-write`: 1 个 token
- `full-test-v2`: 1 个 token
- `dsh-test`: 1 个 token
- `smithery-test`: 1 个 token
- `dsh-plugin`: 1 个 token
- `analytics-test`: 1 个 token
- `antigravity-leonardo-39d2a3fd-5ff8-4168-ace6-c42395ae662b`: 1 个 token

**示例 token 类型**：`deepseek-harness` (1)、`kv-test` (1)、其他未知类型 (39)


### 关注的领域（从 gap 查询推断）

| 主题 | gap 数量 | 说明 |
|------|----------|------|
| Vertex AI / Gemini / Gemma | 13 | 多模 LLM 平台 + 嵌入 + 成本
| RAG / 检索 | 2 | RAG 性能优化（1）+ preset 模板（1）
| Embedding 迁移 | 2 | Vertex AI + Qwen 嵌入
| BigQuery 成本 | 5 | 账单聚合 + 成本分析
| Docker / DCO / SDK | 3 | 工程实践
| 安全/越狱 | 3 | ⚠️ gemini safety refusal bypass — 敏感主题

### 沟通偏好
- **中英混合**：邮件大部分是中文（和利时 / OpenClacky），少部分英文（Henrik MCPVault / OpenClacky）
- **技术导向**：Henrik 邮件确认 MisakaNet 的 MCP 设计，jaco_sun 注意到 Ikalus1988 在 MisakaNet 上的 mcp 实践
- **不喜欢噪音**：limit 邮件频次（rate:email:hello@trymcpvault.com）

## 🎯 业务模式
- **MisakaNet = 节点网络**：60 个节点 + 42 个 mcp_token = 一个分布式 agent 网络
- **GitHub 驱动**：13 条 intake_dedup 都指向 `Ikalus1988/MisakaNet/issues/*`，issue 系统是问题入口
- **邮件驱动**：5 封入站邮件被路由到不同节点处理
- **Search 驱动**：19 个 gap 表明用户（或访客）通过 search_knowledge.py 检索

## 🤝 对外联络

| 来源 | 节点 | 状态 |
|------|------|------|
| `bruce@sharky.gg` | `Misaka10061` | 邮件入站路由 |
| `eric_jia2008@foxmail.com` | `Misaka10059` | 邮件入站路由 |
| `hello@trymcpvault.com` | `Misaka10109` | 邮件入站路由 |
| `jaco_sun@163.com` | `Misaka10062` | 邮件入站路由 |
| `sheldonisspark@gmail.com` | `Misaka10060` | 邮件入站路由 |
| `yifan@dao42.com` | `Misaka10063` | 邮件入站路由 |

**互动密度**:
- `jaco_sun@163.com` (和利时) → 已发招聘 → Misaka10062 处理
- `hello@trymcpvault.com` → 3 封营销跟进 → Misaka10109 处理（被限频）
- `yifan@dao42.com` (OpenClacky) → 1 封 pitch → Misaka10063 处理

## 📊 活动热力图

```
Email-intake: 5 条 (按周)
  08-19 周: 1  (jaco_sun 招聘)
  08-31 周: 1  (Henrik 第1封)
  09-03 周: 1  (Henrik 第2封)
  09-07 周: 2  (Henrik 第3封 + 之前的)

MCP token 注册 (42 条):
  08-22 ~ 08-27: 早期注册
  09-26 前过期: 大部分

Traffic (最近 3 天):
  agent: {'2026-09-07': 5}
  crawler: {'2026-09-05': 1, '2026-09-06': 4, '2026-09-07': 8}
  mcp: {'2026-09-05': 430, '2026-09-06': 937, '2026-09-07': 781}
  pageview: {'2026-09-05': 9, '2026-09-06': 15, '2026-09-07': 70}
```