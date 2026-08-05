# 示例功能计划

## 问题 / 目标

优化 RAG 检索性能，提高召回率和响应速度。

## 非目标

- 不改变现有 API 接口
- 不重构整个知识库架构

## 最小演示

用户输入查询关键词，系统在 2 秒内返回相关文档片段。

## 完整演示

1. 用户输入查询关键词
2. 系统进行语义检索 + 关键词检索
3. 返回 top-5 相关文档片段
4. 显示检索时间和相关性分数

## 验收标准

- [ ] 检索时间 < 2 秒
- [ ] 召回率 > 90%
- [ ] 支持中英文混合查询
- [ ] 返回结果包含相关性分数

## 垂直切片

1. **切片 1**: 优化语义检索模型
2. **切片 2**: 添加关键词检索 fallback
3. **切片 3**: 实现相关性评分
4. **切片 4**: 优化检索缓存

## GSD 手动触发

```bash
# 如果 phase 已存在
gsd-plan-phase rag-optimization --prd docs/plans/example-feature.md

# 如果 .planning/ 不存在
# 创建 manifest.yaml
cat > manifest.yaml << EOF
docs:
  - path: docs/plans/example-feature.md
    type: PRD
EOF

# 执行 ingest
gsd-ingest-docs --manifest manifest.yaml --mode new

# 然后创建 phase
gsd-plan-phase rag-optimization --prd docs/plans/example-feature.md
```
