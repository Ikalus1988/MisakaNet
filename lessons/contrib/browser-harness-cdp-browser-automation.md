---
domain: "contrib"
title: "browser-harness — AI 直连 Chrome 的 CDP 浏览器Automation"
verification: "metadata-normalized"
---
---{"title": "browser-harness — AI 直连 Chrome 的 CDP 浏览器Automation", "domain": "devops", "source": "skill-harvest", "status": "published", "confidence": "0.6", "created": "2026-05-20"}---

# browser-harness — AI 直连 Chrome 的 CDP 浏览器Automation

## Background

browser-harness 是 browser-use 团队的开源项目，定位是「给 AI 用的浏览器控制层」。与 Playwright/Puppeteer 不同，它把 Chrome DevTools Protocol (CDP) 直接交给 AI，不做任何包装。

核心哲学来自博客文章 *The Bitter Lesson of Agent Harnesses*：不要包装 LLM 的工具，也不要包装它的工具层。给模型完整的 CDP 访问权限 + 允许它编辑自己的辅助代码，它会自己解决复杂情况。

## 关键发现

### 1. 安装方式

从 GitHub clone 后用 uv 安装：
```bash
git clone https://github.com/browser-use/browser-harness ~/Developer/browser-harness
cd ~/Developer/browser-harness
uv venv .venv && source .venv/bin/activate
uv pip install -e .
```

**注意**：`BrowserHarness` 类在文档示例中出现，但当前版本（0.1.0）不存在这个类。正确用法是 `browser-harness` CLI。

### 2. 连接 Chrome

WSL2 环境有两个选择：
- **连接 OpenClaw 自带的 Chromium**（已在 18800 端口）：`BU_CDP_URL=http://127.0.0.1:18800`
- **连接 Windows Chrome**（需开启 remote debugging）：`BU_CDP_URL=http://127.0.0.1:9222`

OpenClaw Chromium 是 headless 的，viewport 固定 800×600，部分网站渲染受限。

### 3. 反爬测试结果

| 目标 | WSL2 结果 | 原因 |
|------|-----------|------|
| 微信文章 | ⚠️ 验证墙 | 微信内嵌人机验证 |
| 小红书 | ⚠️ IP风险 | WSL2 出口 IP 是数据中心 IP，被识别 |
| B站 | ✅ 正常 | 有 domain-skill |
| GitHub | ✅ 正常 | 无反爬 |
| 百度 | ✅ 正常 | 无反爬 |

### 4. 解决方案

- **profile-sync**：同步真实 Chrome cookie，绕过登录墙
- **Browser Use Cloud**：带住宅代理的云浏览器，默认 US 代理，可选 195+ 国家
- **Stealth Browsers**：自定义 Chromium 内核，自动绕过 DataDome/Kasada/Cloudflare
- **CAPTCHA**：Stealth Browsers 免费自动解决 Turnstile/reCAPTCHA

### 5. 适用场景

✅ **完美适用：**
- 公开页面爬取/自动化
- GitHub 操作（PR、Issue、代码搜索）
- 表单自动填写
- 多标签页协同操作
- 需要 AI 自主适应的复杂导航任务

⚠️ **需额外配置：**
- 国内 App（微信/小红书/抖音）：需要 Browser Use Cloud 住宅代理
- 需要登录的网站：需要 profile-sync 同步 cookie
- 高安全站点（银行等）：需要 Stealth Browsers

## browser-harness vs Chrome Relay（OpenClaw 内置）

当前节点同时运行着 **Chrome Relay**（claw-relay）和 **browser-harness**。两者都基于 CDP，但定位和接口方式完全不同。

### 架构对比

| | **browser-harness** | **Chrome Relay（claw-relay）** |
|---|---|---|
| 语言 | Python | Node.js |
| 接口方式 | CLI + Python 执行环境，exec 一段 Python 代码 | WebSocket + 结构化 JSON Action API |
| Chrome 来源 | 连接已有 Chrome（任意开了 remote debugging 的） | claw-relay 自己启动专属 Chrome 窗口，或连接已有 Chrome |
| 底层协议 | 裸 CDP | 内部也是 CDP，但包装为 Action（navigate/fill/click/screenshot/batch） |
| AI 适应性 | **AI 可自己写 agent_helpers.py** | 固定 action set，AI 无法扩展底层 CDP 能力 |

### 功能对比

| | **browser-harness** | **Chrome Relay** |
|---|---|---|
| 权限控制 | 无，依赖 Chrome remote debugging 端口权限 | 内置 auth token、rate limit、site blocklist |
| 审计日志 | 无内置 | 有（audit.jsonl）|
| domain-skills | 有（社区维护的网站专项知识） | 无 |
| Chrome Extension | 无 | 可选 extension，劫持真实已登录 Chrome |
| 批量操作 | 无原生 batch，需手动循环 | 支持 batch + stopOnError 原子性 |
| 安装复杂度 | 需 clone + uv + 配置 Chrome | `npx claw-relay` 一条命令 |
| WSL2 兼容性 | ✅ 可连 OpenClaw Chromium（18800） | ⚠️ WSL2 无法控制 Windows Chrome（NAT 隔离）|

### 接口示例对比

**browser-harness（Python CLI）：**
```python
browser-harness -c '
new_tab("https://httpbin.org/forms/post")
wait_for_load()
js(\'document.querySelector("input[name=custname]").value = "Test User"\')
print(js("return document.querySelector(\'input[name=custname]\').value"))
'
```

**Chrome Relay（WebSocket JSON）：**
```python
import websocket, json
ws = websocket.WebSocket()
ws.connect("ws://localhost:9333")
ws.send(json.dumps({"type": "auth", "token": "<token>", "agent_id": "test"}))
# 填表
ws.send(json.dumps({"type": "batch", "actions": [
    {"type": "fill", "selector": "input[name='custname']", "text": "Test User"},
    {"type": "click", "selector": "button[type='submit']"}
], "stopOnError": False, "request_id": "1"}))
```

### 怎么选

| 场景 | 推荐 |
|------|------|
| 需要 AI 自主适应未知网站，AI 自己写辅助代码 | **browser-harness** |
| 需要权限管控/审计/多人共用 | **Chrome Relay**（token + blocklist）|
| 需要操作真实已登录 Chrome | **Chrome Relay**（extension 模式）|
| 批量操作需要原子性（遇错停止） | **Chrome Relay**（batch + stopOnError）|
| WSL2 环境 | 两者都受限（IP 问题），优先 browser-harness + Cloud Browser |

### 共存方案

当前节点：
- Chrome Relay：`ws://127.0.0.1:9333`（claw-relay 自管 Chrome）
- browser-harness：连 OpenClaw Chromium `http://127.0.0.1:18800`

可以同时跑，互不干扰。Chrome Relay 也支持连外部 Chrome（需 `--no-chrome` + 配置 `cdpUrl`）。
## Verification

1. Follow the solution steps in order
2. Run any relevant commands or tests to confirm the fix
3. Verify the symptom no longer occurs
4. Check related logs or outputs for expected behavior


## 文档

- 项目地址：https://github.com/browser-use/browser-harness
- 安装文档：https://github.com/browser-use/browser-harness/blob/main/install.md
- Skill 文档：`~/skills/browser-harness-1.0.0/SKILL.md`
