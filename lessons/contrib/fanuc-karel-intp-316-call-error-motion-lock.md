{
  "id": "fanuc-karel-intp-316-call-error-motion-lock",
  "title": "FANUC KAREL: INTP-316 调用TP程序触发动作锁定",
  "domain": "fanuc",
  "subdomain": "karel-programming",
  "source": "bbs.gongkong.com/d/202503/934119",
  "status": "draft",
  "confidence": 0.7,
  "created": "2026-07-12",
  "tags": ["fanuc", "karel", "tp-program", "intp-316", "motion-lock", "call-error"],
  "quality_score": 67,
  "problem": "从 KAREL 调用 TP 程序时触发 INTP-316（呼叫错误），同时动作锁定被激活，机器人无法运动。KAREL 程序本身可正常运行，仅调用 TP 程序时出错。",
  "root_cause": "INTP-316 是 KAREL 运行时的 CALL/RUN_TPP 呼叫错误。常见根因：1) 调用语法不正确（缺少单引号或 .TP 扩展名）；2) $KAREL_ENB 未启用；3) 目标 TP 程序缺少 CALL 权限或含冲突运动指令导致组锁定。",
  "solution": "1. 验证调用语法：CALL 'PROGRAM.TP'（单引号 + .TP 扩展名）\n2. 确认 $KAREL_ENB=1 已启用\n3. 检查目标 TP 程序的运动组配置是否与调用方一致\n4. 排查目标 TP 程序是否含冲突运动指令\n5. 确认 TP 程序属性中允许被 KAREL 调用",
  "verification": "在 KAREL 中执行 CALL 'TEST.TP'，确认无 INTP-316 报错且机器人正常运动。"
}

## FANUC KAREL: INTP-316 调用TP程序触发动作锁定

### 问题描述

从 KAREL 调用 TP 程序时触发 **INTP-316**（呼叫错误 / Call Error），同时动作锁定被激活。KAREL 程序本身可正常运行，仅在调用 TP 程序时出错。

### 根因分析

INTP-316 是 KAREL 运行时 `CALL` 或 `RUN_TPP` 的呼叫错误。常见根因：

| 根因 | 检查方法 |
|------|----------|
| 调用语法错误 | 程序名需用单引号括起并带 `.TP` 扩展名 |
| `$KAREL_ENB` 未启用 | 菜单 → 系统变量 → 确认值为 1 |
| 目标 TP 程序缺 CALL 权限 | 检查程序属性设置 |
| 运动组冲突 | 确认调用方与目标方的组配置一致 |
| 目标 TP 含冲突运动指令 | 检查 TP 程序中的运动语句 |

### 修复方法

1. **验证调用语法**：
   ```karel
   CALL 'PROGRAM.TP'   -- 正确：单引号 + .TP 扩展名
   CALL PROGRAM.TP     -- 错误：缺引号
   ```

2. **确认系统变量**：
   - `$KAREL_ENB = 1`（KAREL 使能）
   - 检查运动组配置是否匹配

3. **检查 TP 程序属性**：
   - 确保 TP 程序允许被外部调用
   - 排查程序内是否有冲突的运动指令或条件分支

4. **动作锁定排查**：
   - 如果调用后出现动作锁定，先 `ABORT` 所有任务
   - 检查 TP 程序是否在运动指令前有未满足的条件等待

### 验证方式

在 KAREL 中执行：
```karel
CALL 'TEST.TP'
```
确认无 INTP-316 报错且机器人正常运动。

### 关键区分

| 错误代码 | 含义 | 说明 |
|----------|------|------|
| INTP-316 | 呼叫错误 | CALL/RUN_TPP 调用失败 |
| INTP-1086 | 行号（非错误码） | KTRANS 编译输出的行号 |
| MOTN-023 | 动作锁定 | 运动组冲突或条件未满足 |

### 来源

- 帖子：[FANUC KAREL调用TP程序时就报错了INTP-316](https://bbs.gongkong.com/d/202503/934119/934119_1.shtml)
- 作者：monzer (2025-03-15)
- 回复：小肥猪123、默默言、Smile-lyc
