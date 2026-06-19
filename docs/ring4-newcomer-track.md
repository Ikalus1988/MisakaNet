# Ring-4: 新手友好赛道

> 目标：每周 2-3 个新手 PR 合并
> 状态：2026-06-19 启动

## 什么是 Ring-4？

Ring-4 是 MisakaNet 贡献体系中最轻量的赛道，专为**首次贡献者**和**低时间投入**的贡献者设计。

不需要写代码、不需要理解 BM25 或 RRF，只需要选择下面任一任务类型即可参与。

---

## 可用任务

### 1. 翻译一个 Lesson 到中文/日文/韩文

从 `lessons/` 中选择一个**已验证的英文 Lesson**，将其翻译为目标语言。

**步骤：**
1. 选择一个英文 Lesson（如 `lessons/contrib/slugify-path-traversal-deep-coverage.md`）
2. 在 `lessons/locales/{lang}/` 下创建对应文件
3. 保留 frontmatter 不变，只翻译正文内容
4. 在 tags 中添加 `"locale:{lang}"`
5. 提交 PR

**奖励：** 0.5 分 / 篇

### 2. 补全一个 Lesson 的 Verify 段落

选择一个缺少 `## Verification` 章节的 Lesson，补充可执行的验证步骤。

**步骤：**
1. 用 `grep -L "^## Verification" lessons/contrib/*.md` 找到缺 verify 的 Lesson
2. 阅读内容，理解问题和解决方案
3. 补充 `## Verification` 段落（包含具体命令和预期输出）
4. 提交 PR

**奖励：** 0.5 分 / 篇

### 3. 添加 English Title（中文标题 Lesson）

部分 Lesson 标题仍为中文，需要添加英文标题。

**步骤：**
1. 用 `grep -l "title.*[\u4e00-\u9fff]" lessons/contrib/*.md` 找到中文标题
2. 阅读内容，将 frontmatter 的 `title` 改为英文
3. 在内容第一行保留中文标题作为副标题：`# English Title\n\n> 中文标题`
4. 提交 PR

**奖励：** 0.3 分 / 篇

### 4. 为 Lesson 添加 Domain 标签

部分 Lesson 的 `tags` 列表为空或缺失 domain 信息。

**步骤：**
1. 用 `grep -l '"tags": \[\]' lessons/*.md lessons/contrib/*.md lessons/core/*.md 2>/dev/null` 找到空 tags 的 lesson
2. 根据内容添加 2-5 个相关 tags
3. 确保第一个 tag 是 domain 名称
4. 提交 PR

**奖励：** 0.3 分 / 篇

### 5. 修正文件名：中文 → 英文 kebab-case

部分文件名仍包含中文字符，需要改为英文 kebab-case。

**步骤：**
1. 用 `find lessons -name '*[\u4e00-\u9fff]*'` 找到中文文件名
2. 重命名为英文 kebab-case（如 `chromadb-不能放在-ntfs-文件系统.md` → `chromadb-ntfs-incompatibility.md`）
3. 更新 `lessons/index.md` 中的引用路径
4. 提交 PR

**奖励：** 0.5 分 / 篇

---

## 奖励与积分

| 任务类型 | 积分 | 难度 | 平均耗时 |
|---------|------|------|---------|
| 翻译 Lesson | 0.5 | ⭐ | 15-30 min |
| 补 Verify 段落 | 0.5 | ⭐ | 10-20 min |
| 英文化标题 | 0.3 | ⭐ | 5-10 min |
| 补 Tags | 0.3 | ⭐ | 5-10 min |
| 修正文件名 | 0.5 | ⭐⭐ | 10-20 min |

> Ring-4 的积分是**独占的**——不会与 Ring-1/2/3 的贡献者竞争。每项任务仅限 Ring-4 参与者认领。

## 如何参与

1. Fork [Ikalus1988/MisakaNet](https://github.com/Ikalus1988/MisakaNet)
2. 选择一个任务类型（见上表）
3. 完成任务并提交 PR，标题格式：`ring4: <任务描述>`
4. 等待 review
5. 合并后自动计入积分

## 新手向导

如果你完全不知道怎么开始，运行以下命令启动交互式向导：

```bash
python3 scripts/contribute.py --wizard
```

## 相关文档

- [Lesson Checklist](../docs/lesson-checklist.md) — 质量标准
- [TEMPLATE.md](../lessons/TEMPLATE.md) — Lesson 模板
- [CONTRIBUTING.md](../CONTRIBUTING.md) — 贡献指南
