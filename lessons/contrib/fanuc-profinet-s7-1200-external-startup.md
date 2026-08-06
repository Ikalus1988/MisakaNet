{"id": "fanuc-profinet-s7-1200-external-startup", "title": "FANUC PROFINET Communication with Siemens S7-1200 and External Startup", "domain": "fanuc", "subdomain": "plc-communication", "source": "bbs.gongkong.com/d/202011/845226", "status": "draft", "confidence": 0.7, "created": "2026-07-12", "tags": ["fanuc", "profinet", "siemens", "s7-1200", "external-startup", "rsr", "pns", "plc-communication"], "quality_score": 60, "problem": "需要将 FANUC 机器人与 Siemens S7-1200 PLC 通过 PROFINET 协议建立通讯，并配置外部启动功能，使 PLC 能远程触发机器人程序执行。", "root_cause": "PROFINET 通讯配置涉及多个环节：S7-1200 作为 PROFINET Controller、FANUC 机器人装有 PROFINET 适配卡作为 Device、外部启动(RSR/PNS)模式需正确配置信号映射。任一环节配置错误都会导致通讯失败或无法远程启动。", "solution": "1. 硬件准备：FANUC 机器人需安装 PROFINET 适配卡（如 PCI 卡）\n2. S7-1200 侧：在 TIA Portal 中添加 FANUC GSD 文件，配置 PROFINET Device\n3. FANUC 侧：设置 PROFINET 通讯参数（IP 地址、设备名）\n4. 信号映射：配置 DI/DO 信号与 PLC 的对应关系\n5. 外部启动配置：设置 RSR（Robot Start Request）或 PNS（Program Number Select）启动模式\n6. RSR 模式：PLC 通过 DI 信号选择程序编号并触发启动\n7. PNS 模式：PLC 通过信号组选择程序号，FANUC 自动执行对应程序", "verification": "1. 在 TIA Portal 中确认 PROFINET 网络拓扑显示 FANUC Device 为绿色（在线）\n2. 手动触发 DI 信号，确认 FANUC 侧对应信号响应正确\n3. 通过 PLC 发送 RSR/PNS 启动信号，确认机器人自动执行目标程序\n4. 监控通讯状态无断线或超时报警"}

## FANUC PROFINET 通讯与 S7-1200 外部启动配置

### 问题描述

在汽车焊装产线中，需要将 FANUC 机器人与 Siemens S7-1200 PLC 通过 **PROFINET** 协议建立通讯，并配置外部启动功能，使 PLC 能够远程触发机器人程序执行。这是工业自动化中常见的集成场景：S7-1200 作为 PROFINET Controller，FANUC 机器人（配备 PROFINET 适配卡）作为 PROFINET Device。

### 根因分析

PROFINET 通讯及外部启动配置涉及以下关键环节，任一环节配置错误都会导致通讯失败或无法远程启动：

| 环节 | 说明 | 常见问题 |
|------|------|----------|
| 硬件适配 | FANUC 需安装 PROFINET 适配卡 | 未安装卡或卡型号不兼容 |
| 网络配置 | IP 地址、设备名需匹配 | IP 冲突、设备名拼写错误 |
| GSD 文件 | TIA Portal 需导入 FANUC GSD | GSD 版本与固件不匹配 |
| 信号映射 | DI/DO 信号与 PLC 地址对应 | 映射表错位导致信号混乱 |
| 启动模式 | RSR 或 PNS 模式配置 | 启动模式与信号设计不匹配 |

### 修复方法/技术要点

#### 1. 硬件准备与网络配置

- FANUC 机器人需安装 **PROFINET 适配卡**（如 A05B-2600 系列 PCI 卡）
- 配置 FANUC 侧 PROFINET 参数：
  - MENU → SETUP → Profinet → 设置 IP 地址和设备名
  - 确保与 S7-1200 在同一网段

#### 2. TIA Portal 侧配置

- 导入 FANUC GSD 文件（从 FANUC 官网获取对应版本）
- 在项目中添加 FANUC 作为 PROFINET Device
- 配置 IO 通讯区（Input/Output 模块）
- 下载硬件配置到 S7-1200

#### 3. 外部启动模式配置

**RSR（Robot Start Request）模式：**
- PLC 通过 DI 信号发送启动请求
- FANUC 通过信号组接收程序编号
- 适合需要灵活选择程序的场景

**PNS（Program Number Select）模式：**
- PLC 通过 8 位信号组选择程序号（PNS0001~PNS0256）
- FANUC 自动执行对应编号的程序
- 适合程序数量固定的标准化产线

#### 4. 信号映射要点

```
典型信号映射：
DI[1-8]   ← PLC 程序选择信号（PNS 编号）
DI[9]     ← 启动请求（RSR 触发）
DI[10]    ← 停止信号
DO[1]     → 程序运行中
DO[2]     → 程序完成
DO[3]     → 报警信号
```

### 验证方式

1. **通讯验证**：在 TIA Portal 中确认 PROFINET 网络拓扑显示 FANUC Device 为绿色在线状态
2. **信号验证**：手动触发 DI 信号，确认 FANUC 侧对应信号响应正确
3. **启动验证**：通过 PLC 发送 RSR/PNS 启动信号，确认机器人自动执行目标程序
4. **稳定性验证**：监控通讯状态无断线或超时报警，连续运行多个周期

### 来源

- 帖子：[FANUC机器人与S7-1200profinet通讯及外部启动配置](https://bbs.gongkong.com/d/202011/845226/845226_1.shtml)
- 作者：工控稔 (gongkongren)，2020-11-19
- 说明：原帖主要内容为附件下载（需积分），技术细节基于帖子主题和社区讨论整理
