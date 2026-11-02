---
title: "FANUC 报警代码索引：按子系统一次查全（MOTN/PROG/SYST/COMM/INTP/SRVO/MEMO）"
domain: "fanuc"
tags:
  - "fanuc"
  - "alarm"
  - "index"
  - "motn"
  - "prog"
  - "syst"
  - "comm"
  - "intp"
  - "srvo"
  - "severity"
status: "published"
evidence_level: "E0"
created: "2026-11-02"
updated: "2026-11-02"
source: "compiled from corpus lessons (per-row links)"
summary_plain: "现场来一条 FANUC 报警码：从这份索引按子系统查到它的含义、多严重、哪篇课讲过；每条注明依据，没有依据的标「未验证」。"
trigger: "FANUC alarm code lookup 报警代码 含义 严重等级 速查 索引 MOTN PROG SYST COMM INTP SRVO MEMO alarm severity"
verify: "python3 search_knowledge.py 'INTP-316 alarm' 能命中本索引或 INTP-316 课程；表中任取一码，其「依据」链接的文件存在且正文含该码"
provenance:
  issue: "#2628"
  source: "compiled from existing corpus lessons — every row links the lesson it comes from"
---

## Problem

检索的形态是「我手上有一条报警码，我要知道它意味着什么、有多严重、哪篇课讲过」。这些知识在 `fanuc` 域的
36+ 篇课程里都有，但散在各处：搜 `KAREL INTP-316` 能命中，是因为有人恰好把代码写进了正文；没有一份按
**子系统 + 代码**组织、一次可以查全的入口。现场工程师只能逐篇翻，或者去论坛找没有出处的代码表。

## Root Cause

报警代码是**短字符串**，语义检索对它的判别力弱（见
[rag-alarm-code-mandatory-recall](./rag-alarm-code-mandatory-recall.md)：查 `SRVO-023` 会返回无关文档），
命中与否取决于代码有没有被某篇课的正文或 tags 收录。而课程是按**故障故事**写的，不是按**代码**写的——
于是「输入一条报警 → 定位含义与课程」这条最短路径一直没有入口。

## Solution

下表每行三件事：**代码 → 典型含义 → 严重等级**，外加**依据**（本语料里讲它的那篇课，点开可核对）。
只收录有依据的代码；含义一律照抄来源，不补充来源没有写的解释。

### 严重等级怎么读

等级语义来自 [fanuc-alarm-severity-guide](./fanuc-alarm-severity-guide.md) 的级别表；没有逐码等级
来源的行标 **未验证**，不猜：

| 标记 | 级别 | 现场含义 |
|------|------|----------|
| **切伺服** | SERVO / SERVO2 / SYSTEM | 瞬停并**切断伺服电源**（红）——急停类属此列 |
| **停机器人** | PAUSE / STOP / ABORT | 减速停或动作锁定，伺服保持（黄/红） |
| **仅告警** | WARN / NONE / 信息 | 不停机（白/蓝） |
| **未验证** | —— | 来源没给等级，本表不猜 |

### MOTN — 运动控制

| 代码 | 典型含义 | 严重等级 | 依据 |
|------|----------|----------|------|
| MOTN-023 | 动作锁定（Motion Lock），机器人无法运动 | **停机器人** | [fanuc-karel-intp-316-call-error-motion-lock](./fanuc-karel-intp-316-call-error-motion-lock.md) |
| MOTN-018 | 位置不可达 | 未验证 | [fanuc-alarm-code-reference](./fanuc-alarm-code-reference.md) |
| MOTN-050 | 碰撞检测 | 未验证 | [fanuc-alarm-code-reference](./fanuc-alarm-code-reference.md) |

### PROG — 程序

| 代码 | 典型含义 | 严重等级 | 依据 |
|------|----------|----------|------|
| PROG-004 | 程序不存在 | 未验证 | [fanuc-alarm-code-reference](./fanuc-alarm-code-reference.md) |
| PROG-017 | 程序被保护 | 未验证 | [fanuc-alarm-code-reference](./fanuc-alarm-code-reference.md) |
| PROG-035 | 超出寄存器范围 | 未验证 | [fanuc-alarm-code-reference](./fanuc-alarm-code-reference.md) |

### SYST — 系统

| 代码 | 典型含义 | 严重等级 | 依据 |
|------|----------|----------|------|
| SYST-012 | 内存不足 | 未验证 | [fanuc-alarm-code-reference](./fanuc-alarm-code-reference.md) |
| SYST-026 | 系统正常启动 | **仅告警** | [fanuc-alarm-severity-guide](./fanuc-alarm-severity-guide.md) |
| SYST-039 | T2 操作模式被选中 | 未验证 | [fanuc-alarm-severity-guide](./fanuc-alarm-severity-guide.md) |
| SYST-044 | 控制器电池电压低 | 未验证 | [fanuc-alarm-code-reference](./fanuc-alarm-code-reference.md) |
| SYST-212 | DCS 参数需要 Apply | 未验证 | [fanuc-dcs-safety-configuration](./fanuc-dcs-safety-configuration.md) |
| SYST-218 | 该机型不支持 DCS 功能 | 未验证 | [fanuc-dcs-safety-configuration](./fanuc-dcs-safety-configuration.md) |
| SYST-302 | 请求断电状态（soft fault，现场实测 5 次、不抛异常） | 未验证 | [fix-acceptance-is-a-degradation-not-a-crash-count](./fix-acceptance-is-a-degradation-not-a-crash-count.md) |

### COMM — 通讯

| 代码 | 典型含义 | 严重等级 | 依据 |
|------|----------|----------|------|
| COMM-007 | PROFINET 通讯超时 | 未验证 | [fanuc-alarm-code-reference](./fanuc-alarm-code-reference.md) |
| COMM-013 | I/O 通讯断开 | 未验证 | [fanuc-alarm-code-reference](./fanuc-alarm-code-reference.md) |

### INTP — KAREL 解释器

| 代码 | 典型含义 | 严重等级 | 依据 |
|------|----------|----------|------|
| INTP-102 | Code format is not valid（OLP 生成的 `DETECT JOINT` 空白触发） | 未验证 | [fanuc-intp-102-detect-joint-olp-whitespace](./fanuc-intp-102-detect-joint-olp-whitespace.md) |
| INTP-127 | 检测到掉电（Power failure detected） | 未验证 | [fanuc-alarm-severity-guide](./fanuc-alarm-severity-guide.md) |
| INTP-224 | Cannot branch（无法跳转） | 未验证 | [fanuc-alarm-severity-guide](./fanuc-alarm-severity-guide.md) |
| INTP-316 | CALL/RUN_TPP 呼叫错误，常伴动作锁定 | **停机器人** | [fanuc-karel-intp-316-call-error-motion-lock](./fanuc-karel-intp-316-call-error-motion-lock.md) |
| INTP-1086 | 行号信息，**不是错误码**（KTRANS 编译输出） | **仅告警** | [fanuc-kl-1086-is-line-number-not-error-code](./fanuc-kl-1086-is-line-number-not-error-code.md) |

### SRVO — 伺服 / 安全

| 代码 | 典型含义 | 严重等级 | 依据 |
|------|----------|----------|------|
| SRVO-001 | 操作面板急停 | **切伺服** | [fanuc-alarm-severity-guide](./fanuc-alarm-severity-guide.md) |
| SRVO-002 | 示教器急停 | **切伺服** | [fanuc-alarm-severity-guide](./fanuc-alarm-severity-guide.md) |
| SRVO-007 | 外部急停 | **切伺服** | [fanuc-alarm-severity-guide](./fanuc-alarm-severity-guide.md) |
| SRVO-012 | 掉电恢复（Power failure recovery） | 未验证 | [fanuc-alarm-severity-guide](./fanuc-alarm-severity-guide.md) |
| SRVO-048 | DCS SSO 外部急停 | **切伺服** | [fanuc-dcs-safety-configuration](./fanuc-dcs-safety-configuration.md) |
| SRVO-049 | DCS SSO 切断伺服（servo disconnect） | **切伺服** | [fanuc-dcs-safety-configuration](./fanuc-dcs-safety-configuration.md) |
| SRVO-062 | DSP not running | 未验证 | [fanuc-alarm-severity-guide](./fanuc-alarm-severity-guide.md) |
| SRVO-223 | DCS SSO 错误 | 未验证 | [fanuc-dcs-safety-configuration](./fanuc-dcs-safety-configuration.md) |

### MEMO — 内存 / 文件

| 代码 | 典型含义 | 严重等级 | 依据 |
|------|----------|----------|------|
| MEMO-027 | 指定行未找到（Specified line not found） | 未验证 | [fanuc-alarm-severity-guide](./fanuc-alarm-severity-guide.md) |

### 已知缺口（本表刻意留白的）

- **SRVO-023** —— 在语料里只作为检索样例出现过
  （[rag-alarm-code-mandatory-recall](./rag-alarm-code-mandatory-recall.md)），没有任何来源给出它的含义，
  所以本表不收。补充条件同上：一条现场记录或一篇讲它的课程，两者其一。
- 等级列大量「未验证」是如实反映：来源给了含义的多数没给逐码等级。补齐的办法是现场按
  [fanuc-alarm-severity-guide](./fanuc-alarm-severity-guide.md) 的颜色/级别观察后回填，而不是照抄
  论坛代码表（本语料的 [fanuc-alarm-code-reference](./fanuc-alarm-code-reference.md) 自述「基于通用报警
  体系整理，非原帖附件内容的直接复制」，它的含义列可用，等级列不可引用）。

### 查到代码之后

1. 按 [fanuc-alarm-severity-guide](./fanuc-alarm-severity-guide.md) 的恢复流程走：记录 → 查历史
   （MENU → Status → Alarm）→ 根因 → RESET → 复验；**先修根因再按 RESET**。
2. 红色（切伺服/系统级）先查安全回路与 DCS 配置
   （[fanuc-dcs-safety-configuration](./fanuc-dcs-safety-configuration.md)）。
3. DCS 参数改动要 4 位密码，改完必须 Apply（SYST-212 就是没 Apply）。

## Verification

1. 本索引能被检索到（AC：「把代码写进正文与 tags」）：

   ```bash
   python3 search_knowledge.py "INTP-316 alarm"
   ```

   预期：结果里出现本索引或 `fanuc-karel-intp-316-call-error-motion-lock`。

2. 每行依据可核对（任取一码，如 SRVO-049）：

   ```bash
   grep "SRVO-049" lessons/contrib/fanuc-dcs-safety-configuration.md
   ```

   预期：打印出含 `SRVO-049` 的那一行（退出码 0）—— 表里的每个码都能在它「依据」列指向的文件里找到。
