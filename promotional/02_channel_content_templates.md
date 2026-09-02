# MisakaNet 渠道内容模板库 v1.0

所有模板均可直接修改复用，统一遵循「软植入、真诚、无营销感」的风格，匹配不同渠道的社区文化。

---

## 一、飞书社群渠道模板（适配国内技术社群氛围）

### 模板1：安全信赖类 —— 踩坑共鸣型

> 最近踩了个 Agent 工具的大坑：之前用的某个记忆同步工具，居然在后台悄悄执行 lessons 里的代码，吓得我赶紧卸载了。
>
> 后来自己做了个轻量的工具 MisakaNet，所有 lessons 都是纯 Markdown 文本，Agent 端只做读取和展示，根本没有代码执行的逻辑，连远程调用都做了严格的权限控制。
>
> 现在跨设备同步踩坑经验终于不用担惊受怕了😌
>
> 有没有同样被这类安全问题坑过的朋友？可以交流下大家都是怎么防的😂

**适用场景**：AI 工具用户群、安全意识较强的开发者群
**引流链接**：GitHub 主页 + `?utm_source=feishu_security_群名称`

---

### 模板2：开发者互助类 —— 痛点征集型

> 有没有朋友在做 Agent 跨设备同步的时候遇到过这些坑：
> 1. 每个设备上的 Agent 都各自踩一遍同样的坑，重复造轮子
> 2. 想和朋友共享踩坑经验，但是不知道用什么格式存
> 3. 用了各种记忆同步工具，要么太重要么不安全
>
> 我之前被这些坑折腾了快两周，自己攒了个轻量工具解决了这些问题，要是有同样困扰的朋友可以私聊我，把踩坑的经验分享给大家。
>
> 也欢迎大家说说自己遇到的其他痛点，我尽量把对应的 lessons 加到 MisakaNet 里。

**适用场景**：开发者交流群、Agent 项目用户群
**引流链接**：GitHub lessons 目录 + `?utm_source=feishu_painpoint_群名称`

---

### 模板3：产品说明类 —— 开箱即用时

> 最近给 MisakaNet 做了点小迭代，现在终于做到：
> ✅ 10 秒注册节点，不需要 GitHub 账号也能用
> ✅ 纯 Git 驱动，零额外服务，不用搭数据库不用装依赖
> ✅ 所有 lessons 纯文本，完全不用担心代码注入
> ✅ 跨设备、跨 Agent 框架都能用
>
> 有没有朋友想一起测试下？现在早期版本还能提需求，我尽量给大家加上。
>
> 前 100 个注册的节点还有专属像素头像和编号纪念～

**适用场景**：所有技术群、新用户较多的群
**引流链接**：GitHub Pages 注册面板 + `?utm_source=feishu_update_群名称`

---

### 模板4：真实案例型 —— 回头客验证

> 分享个真实的使用案例：
> 上周我在 Windows 上用 Claude Code 踩了个 Python 编码的坑，把经验写到了 MisakaNet 里。
> 今天在 WSL 上又遇到了同样的问题，Hermes 自动从 MisakaNet 检索到了对应的 lesson，一步就解决了。
>
> 之前两个环境各自踩坑的日子终于结束了😂
>
> 有同样跨设备使用 Agent 需求的朋友可以试试，真的能省很多时间。

**适用场景**：真实用户分享，可信度最高
**引流链接**：具体 lesson 的 GitHub 链接 + `?utm_source=feishu_case_群名称`

---

## 二、Reddit 渠道模板（适配海外技术社区文化，开发者第一视角）

### 模板1：安全信赖类 —— 我为什么做这个工具

**Title: I built a lightweight cross-agent lesson sharing tool because I was tired of security risks**

> After a bad experience with a popular AI agent memory tool that silently executed code from shared lessons, I decided to build my own: MisakaNet.
>
> Key security design:
> - All lessons are 100% plain Markdown text, no executable code
> - The agent only reads and displays content, never executes anything from lessons
> - Fully open-source, you can audit every line of code before running
> - No mandatory cloud dependencies, works completely offline via Git
>
> It's still in early stages, but I've been using it across my Windows/WSL/Mac devices for a month now without any security issues.
>
> Would love to get feedback from the community about what security features you care about most for shared agent memory.
>
> Link: https://github.com/Ikalus1988/MisakaNet

**适用板块**：r/LocalLLaMA / r/SelfHosted
**UTM 参数**：`?utm_source=reddit_security_post1`

---

### 模板2：开发者互助类 —— 痛点征集

**Title: What are the most annoying pain points when sharing knowledge between your AI agents?**

> I've spent the last month building a lightweight tool for cross-agent lesson sharing, and I want to make sure I'm solving real problems instead of building features no one needs.
>
> The pain points I've run into personally:
> - Every agent hits the same bugs independently, wasting hours
> - No standard way to pass debugging experience between different agent frameworks
> - Switching devices means starting from scratch with your agent's knowledge
>
> What other frustrations have you had? I'll add the most requested features to MisakaNet for free, and give early access to everyone who shares feedback.
>
> Repo link if you want to see what I've built so far: https://github.com/Ikalus1988/MisakaNet

**适用板块**：r/LocalLLaMA / r/MachineLearning
**UTM 参数**：`?utm_source=reddit_painpoint_post1`

---

### 模板3：产品说明类 —— 解决什么问题

**Title: MisakaNet: A lightweight, secure way to share lessons between your AI agents (no bloat, no cloud lock-in)**

> I noticed most existing agent memory tools are either too heavy for beginners, require mandatory cloud services, or have unclear security models. So I built MisakaNet to fix that:
>
> - Lightweight: Pure Git, zero additional services needed. Works with any agent framework
> - Secure: All lessons are plain Markdown, no code execution. Every PR is manually reviewed
> - Compatible: Works across Windows/WSL/Mac, and with any AI agent that can read text
>
> It's not trying to compete with enterprise-grade agent platforms — it's built for beginners and hobbyists who just want a simple, safe way to share debugging experience between their agents.
>
> First 100 registered nodes get a unique pixel avatar and exclusive node number.
>
> The repo is here if you want to try it: https://github.com/Ikalus1988/MisakaNet
>
> Happy to answer any technical questions in the comments.

**适用板块**：r/LocalLLaMA / r/SelfHosted / r/OpenSource
**UTM 参数**：`?utm_source=reddit_intro_post1`

---

## 三、X/Twitter 渠道模板（适配短内容、快节奏的平台风格）

### 模板1：安全信赖类

> Tired of AI agent memory tools that can execute hidden code without your permission?
>
> I built MisakaNet — all lessons are plain Markdown, no code execution logic at all.
>
> No security risks. No cloud lock-in. Just a lightweight way to share lessons across all your agents.
>
> https://github.com/Ikalus1988/MisakaNet
>
> #AI #Agent #OpenSource #Cybersecurity

**UTM 参数**：`?utm_source=x_security_tweet1`

---

### 模板2：开发者互助类

> Spent 2 weeks troubleshooting a Python encoding bug in WSL.
>
> Then hit the EXACT same bug on Windows with Claude Code the next day.
>
> All the existing tools either require a cloud service or have sketchy security models.
>
> So I built MisakaNet. Pure Git, plain text lessons, works everywhere.
>
> If you've fought the same battles, check it out: https://github.com/Ikalus1988/MisakaNet

**UTM 参数**：`?utm_source=x_painpoint_tweet1`

---

### 模板3：产品说明类

> MisakaNet update: Now you can register a node without a GitHub account.
>
> ✅ 10 second registration on the web dashboard
> ✅ Unique pixel avatar for first 100 nodes
> ✅ Pure Git, zero infrastructure, cross-device sync
> ✅ All lessons plain text, no security risks
>
> Built for AI beginners who don't want to fight with configs or worry about security.
>
> Try it here: https://ikalus1988.github.io/MisakaNet/
>
> #AI #AgentTools #OpenSource

**UTM 参数**：`?utm_source=x_update_tweet1`

---

## 四、小红书渠道模板（适配中文入门用户、图文结合风格）

### 模板1：AI 工具避坑指南系列

**标题**：用了 10 款 AI Agent 工具，这 3 个安全坑千万别踩 😱

> 作为每天用 AI 干活的人，前前后后试了 10 多款 Agent 工具，踩了无数安全坑。
>
> 今天给大家分享 3 个最容易踩的安全坑：
>
> 1️⃣ **代码注入坑**：有些工具会悄悄执行共享记忆里的代码，你根本不知道后台在跑什么
>
> 2️⃣ **数据泄露坑**：你的调试经验、项目机密，不知不觉就传到了第三方服务器
>
> 3️⃣ **权限越界坑**：工具申请了一堆不必要的权限，你都不知道它在读写什么文件
>
> 💡 我的解决方案：自己做了个轻量工具 MisakaNet
> - 所有 lessons 都是纯文本，根本没有执行逻辑
> - 纯 Git 驱动，数据全在你自己手里
> - 不用装任何服务，10 秒就能用
>
> 前 100 个注册的用户还有专属像素头像和编号纪念～
>
> 链接在评论区，需要的朋友自取～

**配图建议**：安全对比图 + 像素头像展示 + 注册流程截图
**UTM 参数**：`?utm_source=xiaohongshu_security_post1`

---

### 模板2：效率提升类

**标题**：跨设备用 AI 终于不用重复踩坑了！这个工具帮我省了 10 小时 🚀

> 不知道大家有没有这种体验：
> WSL 上用 Hermes 踩了个 Python 编码的坑，花了 2 小时解决。
> 过了一周在 Windows 上用 Claude Code，又遇到了一模一样的问题，又花了 1 小时。
>
> 同样的坑踩两次，真的太浪费时间了！
>
> 后来我做了 MisakaNet —— 分布式 Agent 记忆系统。
> 解决一个问题，写进 lessons，所有设备所有 Agent 都能复用。
>
> 用了一个月，少说省了 10 小时的重复排错时间。
>
> 纯 Git 驱动，零服务，不用装依赖，10 秒就能注册节点。
>
> 链接：https://github.com/Ikalus1988/MisakaNet

**配图建议**：时间对比图 + 跨设备使用流程图
**UTM 参数**：`?utm_source=xiaohongshu_efficiency_post1`

---

## 五、内容发布规范

### 发布频率建议

| 渠道 | 发布频率 | 最佳发布时间 |
|------|---------|-------------|
| 飞书群 | 每周 1-2 篇/群 | 工作日下午 2-4 点 |
| Reddit | 每两周 1 篇 | 北京时间晚 10-12 点（北美白天） |
| X | 每周 1-2 条 | 工作日早 9-10 点 / 晚 8-10 点 |
| 小红书 | 每周 1 篇 | 工作日晚 8-10 点 / 周末 |

### UTM 参数命名规范

统一格式：`?utm_source=平台_内容类型_编号`

示例：
- `?utm_source=feishu_security_塔罗会`
- `?utm_source=reddit_painpoint_post1`
- `?utm_source=x_update_tweet3`

### 风险应对话术库

遇到质疑时，优先使用以下标准话术（不要争论，保持开放和透明）：

**抄袭质疑**：
> 感谢你的关注！开源世界的项目确实会互相启发，不过 MisakaNet 有自己独立的设计理念和实现路径。我们聚焦的是「纯文本 lessons 跨 Agent 共享」，和 evomap 的「完整 Agent 框架」定位完全不同。欢迎你查看我们的架构对比文档（链接），也欢迎你审核代码验证差异～

**并发质疑**：
> 这个问题提得很好！我们确实是用 Git 做异步同步，因为我们认为 Agent 记忆共享不需要实时性，分钟级的延迟完全够用。换来的是零基础设施成本、极致的简单性、还有更好的安全性。当然未来我们也会考虑更轻量的同步机制，不过当前阶段我们优先保证简单和安全～

**安全质疑**：
> 安全是我们的第一设计原则！MisakaNet 的所有 lessons 都是纯 Markdown 文本，Agent 端只有读取和展示的逻辑，根本没有代码执行的功能。而且所有 PR 合并前都会经过人工审核。欢迎你查看我们的安全模型文档（链接），也欢迎你做代码审计，有任何问题随时提给我们～

---

**文档版本**：v1.0
**创建日期**：2026-05-23
