## 核心痛点：MisakaNet 需要怎样的成长治理？

### 痛点 1：push 前总要先 pull

只要有人上传了 lesson，其他人 push 之前就要 pull 一次。lesson 变更几乎不会产生真正的冲突（不同文件、不同知识点），但每次都要等 CI 跑完才能合。

建议方案：按 path 分流，lessons/ 下的 PR 走轻量 auto-merge（仅 schema + DCO），非 lessons/ 走完整 CI。

### 痛点 2：lesson 质量参差不齐

当前缺乏自动化质量门禁，只靠 Issue 慢慢优化效率太低。

建议方案：三层门禁 L1 Schema -> L2 质量分 (auto-tag needs-review) -> L3 同行评审。core/ 和 contrib/ 的准入标准拉开。

### 痛点 3：工程收敛到用户主动介绍新用户

技术收敛做得再好，如果用户没有主动传播的理由，增长就是零。

建议方案：
1. README 顶部 30 秒钩子
2. 每周自动更新的数据看板（lesson 数、搜索量、节点数）
3. 零门槛贡献模板

欢迎补充、反驳、细化。
