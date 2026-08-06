---
name: browser-harness
description: Use when you need to control a browser programmatically — scraping, automating web tasks, filling forms, taking screenshots, or bypassing anti-bot checks via CDP.
---

# browser-harness

AI 直连 Chrome 的薄 CDP 层。给 AI 一个 WebSocket，就能控制真实浏览器，AI 自己写辅助代码适应任何网站。

## 核心原则

- **AI 是用户，不是人** — 框架为 AI 设计，不是为人设计的 UI
- **缺失即创造** — 遇到不会的，AI 自己写 `agent_helpers.py` 学会
- **CDP 是接口** — 直接给模型 Chrome DevTools Protocol，不抽象掉

## 快速开始

### 安装

```bash
# clone 到持久目录
git clone https://github.com/browser-use/browser-harness ~/Developer/browser-harness
cd ~/Developer/browser-harness

# 创建虚拟环境
uv venv .venv && source .venv/bin/activate
uv pip install -e .

# 连接到 Chrome（方式一：已有的 Chrome 开了 remote-debugging）
BU_CDP_URL=http://127.0.0.1:9222 browser-harness -c 'print(page_info())'

# 方式二：让 harness 启动云浏览器（需 BROWSER_USE_API_KEY）
start_remote_daemon("work")
```

### 连接 Chrome

**方式 1 — 已有 Chrome 开 remote debugging（推荐）：**
Chrome 菜单 → chrome://inspect/#remote-debugging → 勾选 "Allow remote debugging"
```bash
BU_CDP_URL=http://127.0.0.1:9222 browser-harness -c 'print(page_info())'
```

**方式 2 — 隔离 profile：**
```bash
google-chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-harness
BU_CDP_URL=http://127.0.0.1:9222 browser-harness -c '...'
```

### 常用命令

```bash
browser-harness -c 'new_tab("https://example.com"); wait_for_load(); print(page_info())'
browser-harness -c 'capture_screenshot()'
browser-harness -c 'new_tab("https://example.com"); wait_for_load(); js("document.title")'
```

## 核心 API

| 函数 | 作用 |
|------|------|
| `new_tab(url)` | 新标签页打开 URL（不干扰当前页面） |
| `goto_url(url)` | 在当前标签页导航 |
| `wait_for_load()` | 等待页面加载完成 |
| `page_info()` | 返回 {url, title, w, h, sx, sy, pw, ph} |
| `capture_screenshot()` | 截图，返回文件路径 `/tmp/shot.png` |
| `js(expr)` | 在页面执行 JS 表达式 |
| `click_at_xy(x, y)` | 坐标点击（穿透 iframe/shadow DOM） |
| `scroll(dx, dy)` | 滚动页面 |
| `cdp(domain, method, **params)` | 直调 CDP |
| `list_tabs()` | 列出所有标签页 |

### 表单填写

```python
# 方式：js() 直接操作 DOM
browser-harness -c 'js(\'document.querySelector("input[name=custname]").value = "测试用户"\')'
# 验证
browser-harness -c 'js("return document.querySelector(\'input[name=custname]\').value")'
```

### CDP 直调

```python
# 任何 helper 没覆盖的，用 cdp()
cdp("Runtime.evaluate", expression="1+1", returnByValue=True)
# → {'result': {'type': 'number', 'value': 2}}
```

### Cloud Browser（需 API Key）

```bash
export BROWSER_USE_API_KEY=your_key_here
```

```python
start_remote_daemon("work")  # 清洁浏览器
start_remote_daemon("work", proxyCountryCode="cn")  # 中国住宅代理
start_remote_daemon("work", profileName="my-profile")  # 复用云 profile（已登录）
```

## 反爬对抗

| 场景 | 方案 |
|------|------|
| **微信文章验证墙** | profile-sync 同步真实 Chrome cookie；或 Browser Use Cloud + 住宅代理 |
| **小红书 IP 风险** | Browser Use Cloud 住宅代理（默认带 US 代理，可选 cn/de 等） |
| **CAPTCHA（Cloudflare/reCAPTCHA）** | Browser Use Stealth Browsers 自动破解（免费） |
| **需要登录的网站** | `profile-sync` 工具同步 Chrome 已登录 cookie |
| **反检测（DataDome/Kasada）** | Browser Use 自定义 Chromium 内核（ Stealth Browsers） |

### profile-sync（cookie 同步）

```bash
curl -fsSL https://browser-use.com/profile.sh | sh
# 然后在 browser-harness 中：
sync_local_profile("MyChromeProfile")
start_remote_daemon("work", profileId=uuid)
```

## domain-skills

社区维护的网站专项技能，位于 `agent-workspace/domain-skills/<site>/`。开启方式：

```bash
export BH_DOMAIN_SKILLS=1
```

已覆盖：Bilibili、GitHub、Amazon、LinkedIn 等。AI 访问这些站时会自动读对应 skill。

## 测试结果（WSL2 + OpenClaw Chromium）

| 场景 | 状态 | 说明 |
|------|------|------|
| 页面导航+info | ✅ | |
| 截图 | ✅ | /tmp/shot.png (~130KB) |
| DOM读取 | ✅ | js("document.body.innerText") |
| 表单填写+验证 | ✅ | 4字段全部成功 |
| 坐标点击 | ✅ | click_at_xy |
| 多标签页 | ✅ | new_tab + list_tabs |
| B站(Bilibili) | ✅ | 有 domain-skill |
| GitHub | ✅ | |
| 百度搜索 | ✅ | |
| CDP直调 | ✅ | |
| 微信文章 | ⚠️ | 触发验证墙，需 profile-sync |
| 小红书 | ⚠️ | 触发IP风险，需Cloud住宅代理 |

**结论：** WSL2 环境下微信/小红书不可用（数据中心 IP 被识别）。Windows/Mac 本机 Chrome 无此问题，或用 Browser Use Cloud 住宅代理解决。

## 已知问题

- **区域截图参数错误**：`capture_screenshot(crop={...})` 暂不可用
- **WSL2 IP 限制**：数据中心 IP 导致国内 App 拦截
- **BrowserHarness 不存在**：文档中的 `BrowserHarness` 是旧 API，实际用 `browser-harness` CLI
