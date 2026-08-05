---
{
  "domain": "contrib",
  "title": "lessons md fix heading block type",
  "verification": "metadata-normalized",
  "{\"title\"": "lessons.md 修正（4 处） 项目 旧结论 修正后 heading block（type=4\", \"domain\": \"rag\", \"source\": \"bootstrap\", \"status\": \"published\", \"confidence\": \"0.7\", \"created\": \"2026-04-01\", \"domain_expert\": \"bootstrap\", \"verified_date\": \"2026-04-01\"}",
  "created": "2026-07-06",
  "source": "unknown"
}
---


## 背景
[assistant] 还有一处需要修正：image block 的描述不准确——它返回了有效的 block_id（blocks_created=1），只是 token 被清空导致图片不显示。
[assistant] ---

## 实测结果汇总

```
文档共 24 个 block

=== 写入测试 ===
✅ paragraph (type=2, 字段text): code=0 block_id=doxcnuj1...  success
❌ heading1 (type=4, 字段heading1): code=1770001  invalid param
❌ heading2 (type=5, 字段h
## Verification

1. Follow the solution steps in order
2. Run any relevant commands or tests to confirm the fix
3. Verify the symptom no longer occurs
4. Check related logs or outputs for expected behavior


## 用户描述
lessons.md 修正（4 处）
项目
旧结论
修正后
heading block（type=4~6）
"heading1/2/3 不可用"（含糊）
全部 heading type 实测均为 1770001，全部不可用
heading2 block_type
type=5
修正为 type=5 但不可用，所有 heading 替代方案统一为粗体 paragraph
divider block
type=19 ✅ 可用
429 Rate Limit，非 API 限制，但实际使用中会触发
image block
"code=0 + blocks_created=0（静默失败）"
code=0 + block_id 正常返回，但 token 被静默清空，图片不显示
最终确认的可用子集
✅ paragraph type=2 字段 text
✅ bullet type=12 字段 bullet
✅ 批量追加 每批 ≤20 个，不加 index
✅ image type=27 API 成功，但 token 会被清空 → 实际不可用
❌ heading type=4/5/6 全部 1770001
