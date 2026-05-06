## 跨节点 Lessons (来自 MisakaNet)

> 每次有价值的对话结束时，自问"有什么值得跨节点共享？"
> 如果有，运行: `python3 misakanet/scripts/queue_lesson.py --title "..." --domain "..." --content "问题/修复/验证"`
> 或告诉用户："要把这个经验写成 lesson 吗？"

<!-- MISAKANET_LESSONS_START -->

<!-- 在这里，inject_to_claude.py 会自动注入 lessons/ 目录下的知识索引。
     当节点积累了自己的 lessons 后，运行：
     python3 misakanet/scripts/inject_to_claude.py
     即可将 lessons 标题摘要注入到下方区块。 -->

<!-- MISAKANET_LESSONS_END -->

## 行为规则

当你执行任务时，请遵循：

1. **先检索，后执行** — 遇到问题或开始新任务前，先搜索 `lessons/` 和 `reference/` 目录
2. **Output Gate** — 检索结果必须输出显式摘要，不能跳过
3. **知识共享** — 解决新问题后，把经验写成 lesson
