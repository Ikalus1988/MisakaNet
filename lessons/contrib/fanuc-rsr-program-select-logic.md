{"id": "fanuc-rsr-program-select-logic", "title": "FANUC RSR Program with OFFSET and SELECT Logic Sharing", "domain": "fanuc", "subdomain": "tp-programming", "source": "bbs.gongkong.com/d/201302/481940", "status": "draft", "confidence": 0.7, "created": "2026-07-12", "tags": ["fanuc", "rsr", "tp-programming", "select", "offset", "register", "program-logic", "r-2000ib"], "quality_score": 70, "problem": "需要编写一个 FANUC 机器人 RSR 程序，实现多位置循环搬运，并通过寄存器索引和 SELECT 分支逻辑实现位置偏移选择，同时配合 PLC 信号实现自动化流程控制。", "root_cause": "FANUC TP 编程语言中，RSR 程序需要综合运用运动指令（J/L）、寄存器操作（R/PR）、I/O 信号（DO/DI/RO）、OFFSET 偏移功能和 SELECT 分支结构来实现复杂的搬运逻辑。缺乏对这些编程要素组合使用的理解是主要障碍。", "solution": "1. 使用 RSR 编号命名程序（如 RSR0112）\n2. 运动段使用 J（关节移动）和 L（直线移动）指令\n3. 用 R[n] 寄存器作为索引，通过 SELECT/LBL 实现多分支\n4. 用 PR[n] 位置寄存器存储偏移量，配合 OFFSET 实现可变定位\n5. 用 DO/DI 信号与 PLC 交互（如通知完成、等待许可）\n6. 循环逻辑：寄存器递增遍历位置，达到上限时通知 PLC", "verification": "1. 程序能通过 RSR 正常启动执行\n2. 运动轨迹符合预期，位置精度满足要求\n3. OFFSET 偏移量正确应用，不同分支到达不同位置\n4. DO/DI 信号时序与 PLC 配合正确\n5. 循环逻辑完整，达到上限后正确触发 PLC 信号"}

## FANUC RSR 程序的 OFFSET 与 SELECT 逻辑

### 问题描述

以 FANUC R-2000IB 机器人为例，分享一个使用 **RSR 启动模式** 的搬运程序示例。程序综合运用了运动指令、寄存器索引、OFFSET 偏移和 SELECT 分支逻辑，是 FANUC TP 编程的典型实践。

### 根因分析

此程序展示了 FANUC TP 编程的几个核心要素的组合使用：

| 编程要素 | 作用 | 典型应用 |
|----------|------|----------|
| RSR 编号 | 程序由 PLC 通过 RSR 信号启动 | 自动化产线 |
| J/L 指令 | 关节移动/直线移动 | 运动轨迹控制 |
| R[n] 寄存器 | 整数存储，用作索引 | 循环计数、分支选择 |
| PR[n] 位置寄存器 | 存储位置和偏移量 | OFFSET 可变定位 |
| SELECT/LBL | 多分支跳转 | 条件分发逻辑 |
| DO/DI/RO | 数字 I/O 信号 | PLC 交互 |
| OFFSET | 位置偏移 | 同一轨迹多位置复用 |

### 修复方法/技术要点

#### 程序结构解析（RSR0112）

```ls
/PROG RSR0112
/ATTR
/MN
1: J P[1] 100% FINE      ; 关节移动到 P[1]，100% 速度，FINE 终止
2: L P[2] 100mm/sec       ; 直线移动到 P[2]
3: L P[3] 100mm/sec       ; 直线移动到 P[3]
4: L P[4] 100mm/sec       ; 直线移动到 P[4]
5: RO[8]=ON               ; 设置输出 RO[8]=ON
6: L P[5] 100mm/sec       ; 直线移动到 P[5]
7: L P[6] 100mm/sec       ; 直线移动到 P[6]
; -- SELECT 分支逻辑 --
; R[1] 作为索引，选择位置寄存器 PR[10]
; 通过 LBL[10]~LBL[13] 进行分支
; 在 P[8] 应用 OFFSET.PR[10] 偏移量
; 每个周期 R[1] 递增
; 当 R[1]=4 时，设置 DO[1]=ON 并等待 DI[1]=ON
```

#### 关键编程模式

**1. OFFSET 偏移定位**
```
; 将偏移量存入位置寄存器
PR[10]=OFFSET.PR[n]    ; 选择不同的偏移量
L P[8] 100mm/sec       ; 在 P[8] 基础上应用偏移
```
OFFSET 功能允许在同一基准点上通过不同的位置寄存器偏移到达多个位置，大幅减少示教点数量。

**2. SELECT 分支逻辑**
```
SELECT R[1]=1,LBL[10]   ; R[1]=1 时跳转到 LBL[10]
       =2,LBL[11]       ; R[1]=2 时跳转到 LBL[11]
       =3,LBL[12]       ; R[1]=3 时跳转到 LBL[12]
       =4,LBL[13]       ; R[1]=4 时跳转到 LBL[13]
```
SELECT 类似于 C 语言的 switch-case，根据寄存器值跳转到不同标签。

**3. PLC 交互逻辑**
```
; 当 R[1] 达到上限 4 时：
DO[1]=ON               ; 通知 PLC 本轮完成
WAIT DI[1]=ON          ; 等待 PLC 确认
R[1]=1                 ; 重置索引，开始下一轮
```

#### 第二段程序片段

```ls
; 寄存器 R[1] 初始化
; 使用 SELECT 语句进行跳转标签选择
; 关节移动 + RO[1]=ON
; 50 秒等待命令
```

### 验证方式

1. **RSR 启动**：通过 PLC 发送 RSR 信号，确认程序 RSR0112 正常启动
2. **运动轨迹**：逐一验证 P[1]~P[8] 的运动路径和位置精度
3. **OFFSET 验证**：修改 PR[10] 的偏移量，确认到达位置相应变化
4. **分支验证**：修改 R[1] 的值，确认 SELECT 跳转到正确的 LBL
5. **PLC 交互**：确认 R[1]=4 时 DO[1] 正确输出，DI[1] 响应后程序继续
6. **循环验证**：完整运行多轮循环，确认逻辑无死循环或漏步骤

### 来源

- 帖子：[分享一小段FANUC机器人的程序](https://bbs.gongkong.com/d/201302/481940/481940_1.shtml)
- 作者：王者之师—广州@阿君（版主），2013-02-03
- 机器人型号：FANUC R-2000IB
- 说明：原帖声明非完整运行程序，仅供学习参考
